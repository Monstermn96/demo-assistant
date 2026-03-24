import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { Send, Loader2, Bot, User, ChevronDown, ChevronRight, Brain, Volume2, Square, Wrench, Cpu } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import type { ChatMessage, AgentEvent, ToolCallEvent } from '../hooks/useChat';
import { api } from '../services/api';
import { MobileHeader } from '../components/MobileHeader';

interface ParsedContent {
  thinking: string | null;
  content: string;
  thinkingComplete: boolean;
}

function parseThinkTags(raw: string): ParsedContent {
  const openTag = '<think>';
  const closeTag = '</think>';

  const openIdx = raw.indexOf(openTag);
  if (openIdx === -1) {
    return { thinking: null, content: raw.trim(), thinkingComplete: false };
  }

  const thinkStart = openIdx + openTag.length;
  const closeIdx = raw.indexOf(closeTag, thinkStart);

  if (closeIdx === -1) {
    const thinking = raw.slice(thinkStart).trim();
    const before = raw.slice(0, openIdx).trim();
    return { thinking: thinking || null, content: before, thinkingComplete: false };
  }

  const thinking = raw.slice(thinkStart, closeIdx).trim();
  const before = raw.slice(0, openIdx);
  const after = raw.slice(closeIdx + closeTag.length);
  const remaining = (before + after).trim();

  const further = parseThinkTags(remaining);
  const combinedThinking = [thinking, further.thinking].filter(Boolean).join('\n\n');

  return {
    thinking: combinedThinking || null,
    content: further.content,
    thinkingComplete: true,
  };
}

function ThinkBlock({ thinking, isComplete, isStreaming }: { thinking: string; isComplete: boolean; isStreaming: boolean }) {
  const [userToggled, setUserToggled] = useState(false);
  const [userExpanded, setUserExpanded] = useState(false);

  const autoExpanded = isStreaming && !isComplete;
  const expanded = userToggled ? userExpanded : autoExpanded;

  const handleToggle = () => {
    setUserToggled(true);
    setUserExpanded(!expanded);
  };

  return (
    <div className="mb-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] overflow-hidden text-sm">
      <button
        onClick={handleToggle}
        className="flex items-center gap-2 w-full px-2.5 py-2 text-left text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] transition-colors min-w-0"
      >
        {expanded ? <ChevronDown className="w-3.5 h-3.5 shrink-0" /> : <ChevronRight className="w-3.5 h-3.5 shrink-0" />}
        <Brain className="w-3.5 h-3.5 shrink-0" />
        <span className="font-medium truncate">
          {isStreaming && !isComplete ? 'Thinking...' : 'Thought process'}
        </span>
        {isStreaming && !isComplete && (
          <span className="inline-block w-1.5 h-3.5 bg-[var(--color-primary)] animate-pulse ml-1 rounded-sm shrink-0" />
        )}
      </button>
      {expanded && (
        <div className="px-2.5 py-2 border-t border-[var(--color-border)] text-[var(--color-text-secondary)] whitespace-pre-wrap break-words text-xs leading-relaxed max-h-60 overflow-y-auto overscroll-contain">
          {thinking}
        </div>
      )}
    </div>
  );
}

function TTSButton({ text }: { text: string }) {
  const [state, setState] = useState<'idle' | 'loading' | 'playing'>('idle');
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const handleClick = useCallback(async () => {
    if (state === 'playing') {
      audioRef.current?.pause();
      setState('idle');
      return;
    }
    setState('loading');
    try {
      const blob = await api.tts(text);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => { setState('idle'); URL.revokeObjectURL(url); };
      audio.onerror = () => { setState('idle'); URL.revokeObjectURL(url); };
      await audio.play();
      setState('playing');
    } catch {
      setState('idle');
    }
  }, [text, state]);

  return (
    <button
      onClick={handleClick}
      className="p-1 rounded hover:bg-[var(--color-surface-hover)] text-[var(--color-text-secondary)] transition-colors"
      title={state === 'playing' ? 'Stop' : 'Read aloud'}
    >
      {state === 'loading' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> :
       state === 'playing' ? <Square className="w-3.5 h-3.5" /> :
       <Volume2 className="w-3.5 h-3.5" />}
    </button>
  );
}

function AgentActivityBlock({ event }: { event: AgentEvent }) {
  const [expanded, setExpanded] = useState(false);
  const showContent = expanded || event.streaming;

  return (
    <div className="mb-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] overflow-hidden text-sm">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full px-2.5 py-1.5 text-left text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] transition-colors min-w-0"
      >
        {showContent ? <ChevronDown className="w-3 h-3 shrink-0" /> : <ChevronRight className="w-3 h-3 shrink-0" />}
        <Cpu className="w-3 h-3 shrink-0" />
        <span className="font-medium text-xs truncate">{event.label}</span>
        {event.streaming && <span className="inline-block w-1.5 h-3 bg-[var(--color-primary)] animate-pulse ml-1 rounded-sm shrink-0" />}
      </button>
      {showContent && event.content && (
        <div className="px-2.5 py-2 border-t border-[var(--color-border)] text-[var(--color-text-secondary)] whitespace-pre-wrap break-words text-xs leading-relaxed max-h-48 overflow-y-auto overscroll-contain">
          {event.content}
        </div>
      )}
    </div>
  );
}

function ToolCallBlock({ event }: { event: ToolCallEvent }) {
  const [expanded, setExpanded] = useState(false);
  const agentLabel = event.agent && event.agent !== 'orchestrator' ? ` (${event.agent})` : '';

  return (
    <div className="mb-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] overflow-hidden text-sm">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full px-2.5 py-1.5 text-left text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] transition-colors min-w-0"
      >
        {expanded ? <ChevronDown className="w-3 h-3 shrink-0" /> : <ChevronRight className="w-3 h-3 shrink-0" />}
        <Wrench className="w-3 h-3 shrink-0" />
        <span className="font-medium text-xs truncate">{event.tool}{agentLabel}</span>
        <span className={`text-xs px-1.5 py-0.5 rounded shrink-0 ${event.status === 'running' ? 'bg-amber-500/10 text-amber-400' : 'bg-green-500/10 text-green-400'}`}>
          {event.status === 'running' ? 'running' : 'done'}
        </span>
      </button>
      {expanded && (
        <div className="px-2.5 py-2 border-t border-[var(--color-border)] text-[var(--color-text-secondary)] text-xs leading-relaxed max-h-48 overflow-y-auto overscroll-contain space-y-1">
          <div className="font-mono whitespace-pre-wrap break-all">{JSON.stringify(event.args, null, 2)}</div>
          {event.result && (
            <>
              <div className="border-t border-[var(--color-border)] pt-1 mt-1 font-mono whitespace-pre-wrap break-all">{event.result}</div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

type Verbosity = 'minimal' | 'standard' | 'detailed' | 'developer';

function AssistantContent({
  content,
  streaming,
  agentEvents,
  toolCalls,
  verbosity,
}: {
  content: string;
  streaming: boolean;
  agentEvents?: AgentEvent[];
  toolCalls?: ToolCallEvent[];
  verbosity: Verbosity;
}) {
  const parsed = useMemo(() => parseThinkTags(content), [content]);

  return (
    <div>
      {verbosity === 'developer' && agentEvents?.map((ev, i) => (
        <AgentActivityBlock key={`agent-${i}`} event={ev} />
      ))}
      {(verbosity === 'detailed' || verbosity === 'developer') && toolCalls?.map((ev, i) => (
        <ToolCallBlock key={`tool-${i}`} event={ev} />
      ))}
      {parsed.thinking && verbosity !== 'minimal' && (
        <ThinkBlock
          thinking={parsed.thinking}
          isComplete={parsed.thinkingComplete}
          isStreaming={streaming}
        />
      )}
      {(parsed.content || (!parsed.thinking && !streaming)) && (
        <div className="prose prose-sm dark:prose-invert max-w-none break-words [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&_pre]:overflow-x-auto [&_pre]:max-w-full [&_code]:break-all">
          <ReactMarkdown>{parsed.content}</ReactMarkdown>
          {streaming && <span className="inline-block w-2 h-4 bg-[var(--color-primary)] animate-pulse ml-0.5 rounded-sm" />}
        </div>
      )}
      {!parsed.content && streaming && !parsed.thinking && (
        <span className="inline-block w-2 h-4 bg-[var(--color-primary)] animate-pulse ml-0.5 rounded-sm" />
      )}
    </div>
  );
}

export type ChatStyle = 'bubbles' | 'flat' | 'compact';

interface ChatProps {
  messages: ChatMessage[];
  isStreaming: boolean;
  onSend: (message: string) => void;
  verbosity?: Verbosity;
  chatStyle?: ChatStyle;
  ttsEnabled?: boolean;
}

export function Chat({ messages, isStreaming, onSend, verbosity = 'standard', chatStyle = 'bubbles', ttsEnabled = false }: ChatProps) {
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    onSend(input.trim());
    setInput('');
    if (inputRef.current) inputRef.current.style.height = 'auto';
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px';
  };

  const isFlat = chatStyle === 'flat';
  const isCompact = chatStyle === 'compact';
  const spacing = isCompact ? 'space-y-2' : 'space-y-6';
  const padding = isCompact ? 'px-3 py-1.5' : 'px-4 py-3';
  const textSize = isCompact ? 'text-xs' : 'text-sm';

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <MobileHeader title="Chat" />
      <div className="flex flex-col flex-1 min-h-0">
        <div className={`flex-1 overflow-y-auto overscroll-contain px-3 md:px-4 ${isCompact ? 'py-3' : 'py-4 md:py-6'} ${spacing}`}>
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center px-2">
              <Bot className="w-12 h-12 md:w-16 md:h-16 text-[var(--color-primary)] opacity-30 mb-3 md:mb-4" />
              <h2 className="text-lg md:text-xl font-semibold mb-2">How can I help you?</h2>
              <p className="text-[var(--color-text-secondary)] text-sm max-w-md mb-4 md:mb-6">
                Ask me anything, manage notes and calendar, check weather, search the web, or just have a conversation.
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {['What can you do?', 'Search the web for me', 'Create a note'].map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => onSend(suggestion)}
                    disabled={isStreaming}
                    className="px-3 md:px-4 py-2 rounded-full text-sm bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors active:scale-[0.98] disabled:opacity-50"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => {
            if (msg.role === 'assistant' && !msg.streaming && !msg.content) {
              const hasVisibleAgentEvents = verbosity === 'developer' && !!msg.agentEvents?.length;
              const hasVisibleToolCalls = (verbosity === 'detailed' || verbosity === 'developer') && !!msg.toolCalls?.length;
              if (!hasVisibleAgentEvents && !hasVisibleToolCalls) return null;
            }

            if (isFlat) {
              return (
                <div key={i} className="max-w-3xl mx-auto min-w-0">
                  <div className={`flex items-center gap-2 mb-1 ${textSize} min-w-0`}>
                    {msg.role === 'assistant' ? (
                      <Bot className="w-4 h-4 text-[var(--color-primary)] shrink-0" />
                    ) : (
                      <User className="w-4 h-4 text-[var(--color-text-secondary)] shrink-0" />
                    )}
                    <span className="font-medium text-[var(--color-text-secondary)]">
                      {msg.role === 'assistant' ? 'DemoAssistant' : 'You'}
                    </span>
                    {msg.model && !msg.streaming && (
                      <span className="text-xs opacity-40 ml-auto truncate">{msg.model.split('/').pop()}</span>
                    )}
                    {ttsEnabled && msg.role === 'assistant' && !msg.streaming && msg.content && (
                      <TTSButton text={msg.content} />
                    )}
                  </div>
                  <div className="pl-6 min-w-0 overflow-hidden">
                    {msg.role === 'assistant' ? (
                      <AssistantContent
                        content={msg.content || ''}
                        streaming={!!msg.streaming}
                        agentEvents={msg.agentEvents}
                        toolCalls={msg.toolCalls}
                        verbosity={verbosity}
                      />
                    ) : (
                      <p className={`${textSize} whitespace-pre-wrap break-words`}>{msg.content}</p>
                    )}
                  </div>
                  <div className="border-b border-[var(--color-border)] mt-3 opacity-30" />
                </div>
              );
            }

            return (
              <div key={i} className={`flex gap-2 md:gap-3 max-w-3xl mx-auto min-w-0 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                {msg.role === 'assistant' && (
                  <div className={`${isCompact ? 'w-6 h-6' : 'w-7 h-7 md:w-8 md:h-8'} rounded-lg bg-[var(--color-primary)]/10 flex items-center justify-center shrink-0 mt-0.5`}>
                    <Bot className={`${isCompact ? 'w-3.5 h-3.5' : 'w-4 h-4 md:w-4.5 md:h-4.5'} text-[var(--color-primary)]`} />
                  </div>
                )}
                <div
                  className={`rounded-2xl ${padding} max-w-[85%] md:max-w-[80%] min-w-0 ${
                    msg.role === 'user'
                      ? 'bg-[var(--color-primary)] text-white'
                      : 'bg-[var(--color-surface)] border border-[var(--color-border)]'
                  }`}
                >
                  {msg.role === 'assistant' ? (
                    <AssistantContent
                      content={msg.content || ''}
                      streaming={!!msg.streaming}
                      agentEvents={msg.agentEvents}
                      toolCalls={msg.toolCalls}
                      verbosity={verbosity}
                    />
                  ) : (
                    <p className={`${textSize} whitespace-pre-wrap break-words`}>{msg.content}</p>
                  )}
                  <div className="flex items-center gap-1 mt-1">
                    {msg.model && !msg.streaming && (
                      <p className={`${isCompact ? 'text-[10px]' : 'text-xs'} opacity-50 truncate`}>{msg.model.split('/').pop()}</p>
                    )}
                    {ttsEnabled && msg.role === 'assistant' && !msg.streaming && msg.content && (
                      <TTSButton text={msg.content} />
                    )}
                  </div>
                </div>
                {msg.role === 'user' && (
                  <div className={`${isCompact ? 'w-6 h-6' : 'w-7 h-7 md:w-8 md:h-8'} rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] flex items-center justify-center shrink-0 mt-0.5`}>
                    <User className={`${isCompact ? 'w-3.5 h-3.5' : 'w-4 h-4 md:w-4.5 md:h-4.5'} text-[var(--color-text-secondary)]`} />
                  </div>
                )}
              </div>
            );
          })}
          <div ref={bottomRef} />
        </div>

        <div className="border-t border-[var(--color-border)] bg-[var(--color-surface)]/95 backdrop-blur-sm px-3 py-3 md:p-4 safe-bottom shrink-0">
          <form onSubmit={handleSubmit} className="max-w-3xl mx-auto flex gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              placeholder="Message DemoAssistant..."
              rows={1}
              className="flex-1 min-w-0 px-3 md:px-4 py-2.5 md:py-3 rounded-xl bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] resize-none focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50 focus:border-[var(--color-primary)] text-sm"
            />
            <button
              type="submit"
              disabled={!input.trim() || isStreaming}
              className="px-3 md:px-4 py-2.5 md:py-3 rounded-xl bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] text-white transition-colors disabled:opacity-40 shrink-0 active:scale-[0.98]"
            >
              {isStreaming ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
