import { useState, useCallback, useRef, useEffect } from 'react';
import { ChatWebSocket } from '../services/websocket';
import { api } from '../services/api';

export interface AgentEvent {
  agent: string;
  label: string;
  content: string;
  streaming: boolean;
}

export interface ToolCallEvent {
  tool: string;
  agent: string;
  args: Record<string, unknown>;
  result?: string;
  status: 'running' | 'done';
}

export interface ChatMessage {
  id?: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  model?: string;
  streaming?: boolean;
  agentEvents?: AgentEvent[];
  toolCalls?: ToolCallEvent[];
}

function reconstructEvents(rawEvents: any[]): { agentEvents: AgentEvent[]; toolCalls: ToolCallEvent[] } {
  const agentEvents: AgentEvent[] = [];
  const toolCalls: ToolCallEvent[] = [];

  for (const ev of rawEvents) {
    if (ev.type === 'agent_start') {
      agentEvents.push({
        agent: ev.agent || '',
        label: ev.label || ev.agent || '',
        content: '',
        streaming: false,
      });
    } else if (ev.type === 'agent_token') {
      const existing = [...agentEvents].reverse().find((a) => a.agent === (ev.agent || ''));
      if (existing) {
        existing.content += ev.content || '';
      }
    } else if (ev.type === 'agent_done') {
      const existing = [...agentEvents].reverse().find((a) => a.agent === (ev.agent || ''));
      if (existing) {
        if (ev.content) existing.content = ev.content;
      } else {
        agentEvents.push({
          agent: ev.agent || '',
          label: ev.agent || '',
          content: ev.content || '',
          streaming: false,
        });
      }
    } else if (ev.type === 'tool_start') {
      toolCalls.push({
        tool: ev.tool || '',
        agent: ev.agent || '',
        args: ev.args || {},
        status: 'running',
      });
    } else if (ev.type === 'tool_done') {
      const existing = [...toolCalls].reverse().find(
        (t) => t.tool === (ev.tool || '') && t.agent === (ev.agent || '') && t.status === 'running'
      );
      if (existing) {
        existing.result = ev.result || '';
        existing.status = 'done';
      }
    }
  }

  return { agentEvents, toolCalls };
}

const STORAGE_KEY = 'arim.selected_model';

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [model, setModelState] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(STORAGE_KEY);
  });
  const wsRef = useRef<ChatWebSocket | null>(null);
  const streamBufferRef = useRef('');
  const agentEventsRef = useRef<AgentEvent[]>([]);
  const toolCallsRef = useRef<ToolCallEvent[]>([]);

  const setModel = useCallback((id: string | null) => {
    setModelState(id);
    if (typeof window !== 'undefined') {
      if (id != null) localStorage.setItem(STORAGE_KEY, id);
      else localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    api.getSettings()
      .then((s) => {
        const next = s.default_model || (typeof window !== 'undefined' ? localStorage.getItem(STORAGE_KEY) : null) || null;
        setModelState(next);
        if (typeof window !== 'undefined' && next) localStorage.setItem(STORAGE_KEY, next);
      })
      .catch(() => {});
  }, []);

  function updateStreamingMessage() {
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (last?.streaming) {
        return [...prev.slice(0, -1), {
          ...last,
          agentEvents: [...agentEventsRef.current],
          toolCalls: [...toolCallsRef.current],
        }];
      }
      if (agentEventsRef.current.length > 0 || toolCallsRef.current.length > 0) {
        return [...prev, {
          role: 'assistant' as const,
          content: '',
          streaming: true,
          agentEvents: [...agentEventsRef.current],
          toolCalls: [...toolCallsRef.current],
        }];
      }
      return prev;
    });
  }

  function handleStreamEvent(data: Record<string, any>) {
    if (data.type === 'token') {
      streamBufferRef.current += data.content || '';
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.streaming) {
          return [...prev.slice(0, -1), {
            ...last,
            content: streamBufferRef.current,
            agentEvents: [...agentEventsRef.current],
            toolCalls: [...toolCallsRef.current],
          }];
        }
        return [...prev, {
          role: 'assistant',
          content: streamBufferRef.current,
          streaming: true,
          agentEvents: [...agentEventsRef.current],
          toolCalls: [...toolCallsRef.current],
        }];
      });
      if (data.conversation_id) setConversationId(data.conversation_id);
    } else if (data.type === 'agent_start') {
      agentEventsRef.current = [...agentEventsRef.current, {
        agent: data.agent || '',
        label: data.label || data.agent || '',
        content: '',
        streaming: true,
      }];
      updateStreamingMessage();
    } else if (data.type === 'agent_token') {
      const agent = data.agent || '';
      const hasEntry = agentEventsRef.current.some((ev) => ev.agent === agent && ev.streaming);
      if (hasEntry) {
        agentEventsRef.current = agentEventsRef.current.map((ev) =>
          ev.agent === agent && ev.streaming
            ? { ...ev, content: ev.content + (data.content || '') }
            : ev
        );
      } else {
        agentEventsRef.current = [...agentEventsRef.current, {
          agent,
          label: agent,
          content: data.content || '',
          streaming: true,
        }];
      }
      updateStreamingMessage();
    } else if (data.type === 'agent_done') {
      const agent = data.agent || '';
      agentEventsRef.current = agentEventsRef.current.map((ev) =>
        ev.agent === agent && ev.streaming
          ? { ...ev, content: data.content || ev.content, streaming: false }
          : ev
      );
      updateStreamingMessage();
    } else if (data.type === 'tool_start') {
      toolCallsRef.current = [...toolCallsRef.current, {
        tool: data.tool || '',
        agent: data.agent || '',
        args: data.args || {},
        status: 'running',
      }];
      updateStreamingMessage();
    } else if (data.type === 'tool_done') {
      const tool = data.tool || '';
      const agent = data.agent || '';
      toolCallsRef.current = toolCallsRef.current.map((ev) =>
        ev.tool === tool && ev.agent === agent && ev.status === 'running'
          ? { ...ev, result: data.result || '', status: 'done' as const }
          : ev
      );
      updateStreamingMessage();
    } else if (data.type === 'error') {
      const errorContent = data.content ? `\n\n*Error: ${data.content}*` : '';
      if (errorContent) {
        streamBufferRef.current += errorContent;
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.streaming) {
            return [...prev.slice(0, -1), { ...last, content: streamBufferRef.current }];
          }
          return [...prev, { role: 'assistant', content: streamBufferRef.current, streaming: true }];
        });
      }
    } else if (data.type === 'done') {
      const finalAgentEvents = [...agentEventsRef.current];
      const finalToolCalls = [...toolCallsRef.current];
      streamBufferRef.current = '';
      agentEventsRef.current = [];
      toolCallsRef.current = [];
      setIsStreaming(false);
      setMessages((prev) =>
        prev.map((m) => (m.streaming ? {
          ...m,
          streaming: false,
          model: data.model,
          agentEvents: finalAgentEvents,
          toolCalls: finalToolCalls,
        } : m))
      );
      if (data.conversation_id) setConversationId(data.conversation_id);
    }
  }

  useEffect(() => {
    const ws = new ChatWebSocket();
    const token = api.getToken();
    if (token) ws.connect(token);
    wsRef.current = ws;

    const unsub = ws.onMessage(handleStreamEvent);

    const unsubClose = ws.onClose(() => {
      if (streamBufferRef.current) {
        const finalAgentEvents = [...agentEventsRef.current];
        const finalToolCalls = [...toolCallsRef.current];
        streamBufferRef.current = '';
        agentEventsRef.current = [];
        toolCallsRef.current = [];
        setIsStreaming(false);
        setMessages((prev) =>
          prev.map((m) => (m.streaming ? {
            ...m,
            streaming: false,
            agentEvents: finalAgentEvents,
            toolCalls: finalToolCalls,
          } : m))
        );
      }
    });

    return () => {
      unsub();
      unsubClose();
      ws.disconnect();
    };
  }, []);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim()) return;

      setMessages((prev) => [...prev, { role: 'user', content }]);

      const ws = wsRef.current;
      if (ws?.isUsable) {
        setIsStreaming(true);
        streamBufferRef.current = '';
        agentEventsRef.current = [];
        toolCallsRef.current = [];
        const sent = ws.send(content, conversationId ?? undefined, model ?? undefined);
        if (sent) return;
        setIsStreaming(false);
      }

      try {
        setIsStreaming(true);
        streamBufferRef.current = '';
        agentEventsRef.current = [];
        toolCallsRef.current = [];

        const token = api.getToken();
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        };
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const res = await fetch('/api/chat', {
          method: 'POST',
          headers,
          body: JSON.stringify({ message: content, conversation_id: conversationId, model }),
        });

        if (!res.ok) throw new Error('Chat request failed');

        const reader = res.body?.getReader();
        if (!reader) throw new Error('No stream');
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            try {
              const data = JSON.parse(line.slice(6));
              handleStreamEvent(data);
            } catch { /* ignore parse errors */ }
          }
        }
      } catch (err: any) {
        setMessages((prev) => [...prev, { role: 'assistant', content: `Error: ${err.message}` }]);
      } finally {
        const finalAgentEvents = [...agentEventsRef.current];
        const finalToolCalls = [...toolCallsRef.current];
        streamBufferRef.current = '';
        agentEventsRef.current = [];
        toolCallsRef.current = [];
        setIsStreaming(false);
        setMessages((prev) =>
          prev.map((m) => (m.streaming ? {
            ...m,
            streaming: false,
            agentEvents: finalAgentEvents,
            toolCalls: finalToolCalls,
          } : m))
        );
      }
    },
    [conversationId, model]
  );

  const loadConversation = useCallback(async (id: number) => {
    const msgs = await api.getMessages(id);
    setConversationId(id);
    setMessages(
      msgs
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .map((m) => {
          const events = m.agent_events?.length ? reconstructEvents(m.agent_events) : undefined;
          return {
            id: m.id,
            role: m.role as 'user' | 'assistant',
            content: m.content || '',
            model: m.model,
            agentEvents: events?.agentEvents,
            toolCalls: events?.toolCalls,
          };
        })
    );
  }, []);

  const newConversation = useCallback(() => {
    setConversationId(null);
    setMessages([]);
  }, []);

  return {
    messages,
    conversationId,
    isStreaming,
    model,
    setModel,
    sendMessage,
    loadConversation,
    newConversation,
  };
}
