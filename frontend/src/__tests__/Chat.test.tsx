import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Chat } from '../pages/Chat';
import type { ChatMessage, AgentEvent, ToolCallEvent } from '../hooks/useChat';

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

vi.mock('../components/MobileHeader', () => ({ MobileHeader: () => null }));
vi.mock('../services/api', () => ({
  api: { tts: vi.fn(), getToken: vi.fn().mockReturnValue('mock-token') },
}));

function renderChat(props?: Partial<React.ComponentProps<typeof Chat>>) {
  const defaultProps = {
    messages: [] as ChatMessage[],
    isStreaming: false,
    onSend: vi.fn(),
    verbosity: 'standard' as const,
    chatStyle: 'bubbles' as const,
    ttsEnabled: false,
  };
  return render(
    <MemoryRouter>
      <Chat {...defaultProps} {...props} />
    </MemoryRouter>
  );
}

const thinkingContent = '<think>I should look up the weather first.</think>The weather in NYC is 72°F and sunny.';
const plainContent = 'The weather in NYC is 72°F and sunny.';

const sampleAgentEvents: AgentEvent[] = [
  { agent: 'weather_agent', label: 'Weather Agent', content: 'Looking up current conditions for NYC...', streaming: false },
  { agent: 'research_agent', label: 'Research Agent', content: 'Gathering supplementary data from cache...', streaming: false },
];

const sampleToolCalls: ToolCallEvent[] = [
  { tool: 'weather', agent: 'weather_agent', args: { location: 'New York, NY' }, result: '72°F, sunny', status: 'done' },
  { tool: 'web_search', agent: 'research_agent', args: { query: 'NYC weather forecast' }, result: 'Forecast: clear skies all week', status: 'done' },
];

const streamingToolCalls: ToolCallEvent[] = [
  { tool: 'weather', agent: 'orchestrator', args: { location: 'San Francisco' }, status: 'running' },
];

const streamingAgentEvents: AgentEvent[] = [
  { agent: 'analysis_agent', label: 'Analysis Agent', content: 'Processing request...', streaming: true },
];

function buildMessages(overrides?: Partial<ChatMessage>): ChatMessage[] {
  return [
    { role: 'user', content: "What's the weather in NYC?" },
    {
      role: 'assistant',
      content: thinkingContent,
      model: 'mistralai/magistral-small-2509',
      agentEvents: sampleAgentEvents,
      toolCalls: sampleToolCalls,
      ...overrides,
    },
  ];
}

describe('Chat component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders empty state with suggestions when no messages', () => {
    renderChat();
    expect(screen.getByText('How can I help you?')).toBeDefined();
    expect(screen.getByText('What can you do?')).toBeDefined();
    expect(screen.getByText('Search the web for me')).toBeDefined();
    expect(screen.getByText('Create a note')).toBeDefined();
  });

  it('renders user messages', () => {
    renderChat({ messages: [{ role: 'user', content: 'Hello ARIM' }] });
    expect(screen.getByText('Hello ARIM')).toBeDefined();
  });

  it('renders assistant plain text', () => {
    renderChat({
      messages: [
        { role: 'user', content: 'Hi' },
        { role: 'assistant', content: plainContent },
      ],
    });
    expect(screen.getByText(/72°F and sunny/)).toBeDefined();
  });

  it('submits message on form submit', () => {
    const onSend = vi.fn();
    renderChat({ onSend });
    const textarea = screen.getByPlaceholderText('Message DemoAssistant...');
    fireEvent.change(textarea, { target: { value: 'Test message' } });
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
    expect(onSend).toHaveBeenCalledWith('Test message');
  });

  it('does not submit empty messages', () => {
    const onSend = vi.fn();
    renderChat({ onSend });
    const textarea = screen.getByPlaceholderText('Message DemoAssistant...');
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
    expect(onSend).not.toHaveBeenCalled();
  });

  it('disables send while streaming', () => {
    renderChat({ isStreaming: true });
    const buttons = screen.getAllByRole('button');
    const submitBtn = buttons.find(b => b.getAttribute('type') === 'submit');
    expect(submitBtn?.hasAttribute('disabled')).toBe(true);
  });
});

describe('Chat verbosity levels', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('minimal', () => {
    it('hides thinking blocks', () => {
      renderChat({ messages: buildMessages(), verbosity: 'minimal' });
      expect(screen.queryByText('Thought process')).toBeNull();
    });

    it('hides agent activity blocks', () => {
      renderChat({ messages: buildMessages(), verbosity: 'minimal' });
      expect(screen.queryByText('Weather Agent')).toBeNull();
      expect(screen.queryByText('Research Agent')).toBeNull();
    });

    it('hides tool call blocks', () => {
      renderChat({ messages: buildMessages(), verbosity: 'minimal' });
      expect(screen.queryByText('weather')).toBeNull();
      expect(screen.queryByText('web_search')).toBeNull();
    });

    it('still shows the final assistant response', () => {
      renderChat({ messages: buildMessages(), verbosity: 'minimal' });
      expect(screen.getByText(/72°F and sunny/)).toBeDefined();
    });

    it('shows user message alongside assistant', () => {
      renderChat({ messages: buildMessages(), verbosity: 'minimal' });
      expect(screen.getByText("What's the weather in NYC?")).toBeDefined();
    });
  });

  describe('standard', () => {
    it('shows thinking blocks', () => {
      renderChat({ messages: buildMessages(), verbosity: 'standard' });
      expect(screen.getByText('Thought process')).toBeDefined();
    });

    it('hides agent activity blocks', () => {
      renderChat({ messages: buildMessages(), verbosity: 'standard' });
      expect(screen.queryByText('Weather Agent')).toBeNull();
      expect(screen.queryByText('Research Agent')).toBeNull();
    });

    it('hides tool call blocks', () => {
      renderChat({ messages: buildMessages(), verbosity: 'standard' });
      expect(screen.queryByText(/^weather$/)).toBeNull();
    });

    it('shows the final assistant response', () => {
      renderChat({ messages: buildMessages(), verbosity: 'standard' });
      expect(screen.getByText(/72°F and sunny/)).toBeDefined();
    });
  });

  describe('detailed', () => {
    it('shows thinking blocks', () => {
      renderChat({ messages: buildMessages(), verbosity: 'detailed' });
      expect(screen.getByText('Thought process')).toBeDefined();
    });

    it('hides agent activity blocks', () => {
      renderChat({ messages: buildMessages(), verbosity: 'detailed' });
      expect(screen.queryByText('Weather Agent')).toBeNull();
      expect(screen.queryByText('Research Agent')).toBeNull();
    });

    it('shows tool call blocks', () => {
      renderChat({ messages: buildMessages(), verbosity: 'detailed' });
      expect(screen.getByText(/^weather/)).toBeDefined();
      expect(screen.getByText(/^web_search/)).toBeDefined();
    });

    it('shows tool call status', () => {
      renderChat({ messages: buildMessages(), verbosity: 'detailed' });
      const doneLabels = screen.getAllByText('done');
      expect(doneLabels.length).toBe(2);
    });

    it('shows the final assistant response', () => {
      renderChat({ messages: buildMessages(), verbosity: 'detailed' });
      expect(screen.getByText(/72°F and sunny/)).toBeDefined();
    });
  });

  describe('developer', () => {
    it('shows thinking blocks', () => {
      renderChat({ messages: buildMessages(), verbosity: 'developer' });
      expect(screen.getByText('Thought process')).toBeDefined();
    });

    it('shows agent activity blocks', () => {
      renderChat({ messages: buildMessages(), verbosity: 'developer' });
      expect(screen.getByText('Weather Agent')).toBeDefined();
      expect(screen.getByText('Research Agent')).toBeDefined();
    });

    it('shows tool call blocks', () => {
      renderChat({ messages: buildMessages(), verbosity: 'developer' });
      expect(screen.getByText(/^weather/)).toBeDefined();
      expect(screen.getByText(/^web_search/)).toBeDefined();
    });

    it('shows tool call status', () => {
      renderChat({ messages: buildMessages(), verbosity: 'developer' });
      const doneLabels = screen.getAllByText('done');
      expect(doneLabels.length).toBe(2);
    });

    it('shows the final assistant response', () => {
      renderChat({ messages: buildMessages(), verbosity: 'developer' });
      expect(screen.getByText(/72°F and sunny/)).toBeDefined();
    });
  });
});

describe('Chat with streaming agent activity', () => {
  it('shows streaming agent events in developer mode', () => {
    const messages: ChatMessage[] = [
      { role: 'user', content: 'Analyze this' },
      {
        role: 'assistant',
        content: '',
        streaming: true,
        agentEvents: streamingAgentEvents,
        toolCalls: [],
      },
    ];
    renderChat({ messages, verbosity: 'developer', isStreaming: true });
    expect(screen.getByText('Analysis Agent')).toBeDefined();
  });

  it('hides streaming agent events in minimal mode', () => {
    const messages: ChatMessage[] = [
      { role: 'user', content: 'Analyze this' },
      {
        role: 'assistant',
        content: '',
        streaming: true,
        agentEvents: streamingAgentEvents,
        toolCalls: [],
      },
    ];
    renderChat({ messages, verbosity: 'minimal', isStreaming: true });
    expect(screen.queryByText('Analysis Agent')).toBeNull();
  });

  it('shows streaming tool calls with running status in detailed mode', () => {
    const messages: ChatMessage[] = [
      { role: 'user', content: 'Check SF weather' },
      {
        role: 'assistant',
        content: '',
        streaming: true,
        agentEvents: [],
        toolCalls: streamingToolCalls,
      },
    ];
    renderChat({ messages, verbosity: 'detailed', isStreaming: true });
    const weatherTools = screen.getAllByText('weather');
    expect(weatherTools.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('running')).toBeDefined();
  });

  it('hides streaming tool calls in standard mode', () => {
    const messages: ChatMessage[] = [
      { role: 'user', content: 'Check SF weather' },
      {
        role: 'assistant',
        content: '',
        streaming: true,
        agentEvents: [],
        toolCalls: streamingToolCalls,
      },
    ];
    renderChat({ messages, verbosity: 'standard', isStreaming: true });
    expect(screen.queryByText('running')).toBeNull();
  });

  it('shows thinking animation during streaming think block', () => {
    const messages: ChatMessage[] = [
      { role: 'user', content: 'Think about this' },
      {
        role: 'assistant',
        content: '<think>Let me consider...',
        streaming: true,
      },
    ];
    renderChat({ messages, verbosity: 'standard', isStreaming: true });
    expect(screen.getByText('Thinking...')).toBeDefined();
  });
});

describe('Chat styles', () => {
  it('renders flat style with role labels', () => {
    const messages: ChatMessage[] = [
      { role: 'user', content: 'Hello' },
      { role: 'assistant', content: 'Hi there!' },
    ];
    renderChat({ messages, chatStyle: 'flat' });
    expect(screen.getByText('DemoAssistant')).toBeDefined();
    expect(screen.getByText('You')).toBeDefined();
  });

  it('renders all three styles without errors', () => {
    const messages: ChatMessage[] = [
      { role: 'user', content: 'Test message' },
      { role: 'assistant', content: 'Test response', model: 'test/model' },
    ];

    for (const style of ['bubbles', 'flat', 'compact'] as const) {
      const { unmount } = renderChat({ messages, chatStyle: style });
      expect(screen.getByText('Test message')).toBeDefined();
      expect(screen.getByText('Test response')).toBeDefined();
      unmount();
    }
  });
});

describe('Chat verbosity transition - no content loss', () => {
  it('retains message content across all verbosity levels', () => {
    const messages = buildMessages();

    for (const verbosity of ['minimal', 'standard', 'detailed', 'developer'] as const) {
      const { unmount } = renderChat({ messages, verbosity });
      expect(screen.getByText(/72°F and sunny/)).toBeDefined();
      expect(screen.getByText("What's the weather in NYC?")).toBeDefined();
      unmount();
    }
  });

  it('progressively reveals more info from minimal to developer', () => {
    const messages = buildMessages();

    const { unmount: u1 } = renderChat({ messages, verbosity: 'minimal' });
    expect(screen.queryByText('Thought process')).toBeNull();
    expect(screen.queryByText('Weather Agent')).toBeNull();
    expect(screen.queryByText(/^web_search/)).toBeNull();
    u1();

    const { unmount: u2 } = renderChat({ messages, verbosity: 'standard' });
    expect(screen.getByText('Thought process')).toBeDefined();
    expect(screen.queryByText('Weather Agent')).toBeNull();
    expect(screen.queryByText(/^web_search/)).toBeNull();
    u2();

    const { unmount: u3 } = renderChat({ messages, verbosity: 'detailed' });
    expect(screen.getByText('Thought process')).toBeDefined();
    expect(screen.queryByText('Weather Agent')).toBeNull();
    expect(screen.getByText(/^web_search/)).toBeDefined();
    u3();

    const { unmount: u4 } = renderChat({ messages, verbosity: 'developer' });
    expect(screen.getByText('Thought process')).toBeDefined();
    expect(screen.getByText('Weather Agent')).toBeDefined();
    expect(screen.getByText(/^web_search/)).toBeDefined();
    u4();
  });
});

describe('Chat with multiple simultaneous agents', () => {
  const multiAgentMessages: ChatMessage[] = [
    { role: 'user', content: 'Complex query' },
    {
      role: 'assistant',
      content: 'Here is the combined result from multiple agents.',
      agentEvents: [
        { agent: 'planner', label: 'Planner', content: 'Breaking down the task into subtasks...', streaming: false },
        { agent: 'executor_1', label: 'Executor 1', content: 'Running subtask A...', streaming: false },
        { agent: 'executor_2', label: 'Executor 2', content: 'Running subtask B...', streaming: false },
        { agent: 'summarizer', label: 'Summarizer', content: 'Combining results...', streaming: false },
      ],
      toolCalls: [
        { tool: 'database_query', agent: 'executor_1', args: { sql: 'SELECT * FROM users' }, result: '42 rows', status: 'done' },
        { tool: 'api_call', agent: 'executor_2', args: { url: '/api/data' }, result: '{"ok": true}', status: 'done' },
        { tool: 'web_search', agent: 'executor_1', args: { query: 'latest news' }, result: 'Headlines...', status: 'done' },
      ],
    },
  ];

  it('developer mode shows all agents and tools', () => {
    renderChat({ messages: multiAgentMessages, verbosity: 'developer' });
    expect(screen.getByText('Planner')).toBeDefined();
    expect(screen.getByText('Executor 1')).toBeDefined();
    expect(screen.getByText('Executor 2')).toBeDefined();
    expect(screen.getByText('Summarizer')).toBeDefined();
    expect(screen.getByText(/^database_query/)).toBeDefined();
    expect(screen.getByText(/^api_call/)).toBeDefined();
    expect(screen.getByText(/^web_search/)).toBeDefined();
  });

  it('detailed mode shows only tools, not agents', () => {
    renderChat({ messages: multiAgentMessages, verbosity: 'detailed' });
    expect(screen.queryByText('Planner')).toBeNull();
    expect(screen.queryByText('Summarizer')).toBeNull();
    expect(screen.getByText(/^database_query/)).toBeDefined();
    expect(screen.getByText(/^api_call/)).toBeDefined();
  });

  it('standard mode hides all agents and tools', () => {
    renderChat({ messages: multiAgentMessages, verbosity: 'standard' });
    expect(screen.queryByText('Planner')).toBeNull();
    expect(screen.queryByText(/^database_query/)).toBeNull();
  });

  it('minimal mode shows only the final response', () => {
    renderChat({ messages: multiAgentMessages, verbosity: 'minimal' });
    expect(screen.queryByText('Planner')).toBeNull();
    expect(screen.queryByText(/^database_query/)).toBeNull();
    expect(screen.getByText('Here is the combined result from multiple agents.')).toBeDefined();
  });

  it('tool calls show agent attribution in developer mode', () => {
    renderChat({ messages: multiAgentMessages, verbosity: 'developer' });
    expect(screen.getAllByText(/\(executor_1\)/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/\(executor_2\)/).length).toBeGreaterThanOrEqual(1);
  });
});
