type MessageHandler = (data: {
  type: string;
  content?: string;
  conversation_id?: number;
  model?: string;
  agent?: string;
  label?: string;
  tool?: string;
  args?: Record<string, unknown>;
  result?: string;
}) => void;

const MAX_RECONNECT_ATTEMPTS = 3;
const STABLE_THRESHOLD_MS = 5000;

export class ChatWebSocket {
  private ws: WebSocket | null = null;
  private handlers: MessageHandler[] = [];
  private closeHandlers: (() => void)[] = [];
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private url: string;
  private token: string = '';
  private attempts = 0;
  private connectedAt = 0;
  private _usable = false;

  constructor() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    this.url = `${proto}//${location.host}/api/chat/ws`;
  }

  get isUsable() {
    return this._usable && this.ws?.readyState === WebSocket.OPEN;
  }

  connect(token: string) {
    this.token = token;
    if (this.ws?.readyState === WebSocket.OPEN) return;
    if (this.attempts >= MAX_RECONNECT_ATTEMPTS) return;

    this.ws = new WebSocket(`${this.url}?token=${token}`);

    this.ws.onopen = () => {
      this.connectedAt = Date.now();
      this._usable = true;
      this.attempts = 0;
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.handlers.forEach((h) => h(data));
      } catch { /* ignore parse errors */ }
    };

    this.ws.onclose = () => {
      const wasStable = Date.now() - this.connectedAt > STABLE_THRESHOLD_MS;
      if (!wasStable) {
        this.attempts++;
      } else {
        this.attempts = 0;
      }
      this._usable = false;
      this.closeHandlers.forEach((h) => h());

      if (this.attempts < MAX_RECONNECT_ATTEMPTS) {
        const delay = Math.min(3000 * Math.pow(2, this.attempts), 15000);
        this.reconnectTimer = setTimeout(() => this.connect(this.token), delay);
      }
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  send(message: string, conversationId?: number, model?: string) {
    if (this.ws?.readyState !== WebSocket.OPEN) return false;
    this.ws.send(JSON.stringify({ message, conversation_id: conversationId, model }));
    return true;
  }

  onMessage(handler: MessageHandler) {
    this.handlers.push(handler);
    return () => {
      this.handlers = this.handlers.filter((h) => h !== handler);
    };
  }

  onClose(handler: () => void) {
    this.closeHandlers.push(handler);
    return () => {
      this.closeHandlers = this.closeHandlers.filter((h) => h !== handler);
    };
  }

  disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.attempts = MAX_RECONNECT_ATTEMPTS;
    this.ws?.close();
    this.ws = null;
    this._usable = false;
  }
}
