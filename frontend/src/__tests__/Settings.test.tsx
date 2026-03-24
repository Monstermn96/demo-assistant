import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Settings } from '../pages/Settings';

vi.mock('../components/MobileHeader', () => ({ MobileHeader: () => null }));

// Mock the api module
vi.mock('../services/api', () => ({
  api: {
    getModels: vi.fn().mockResolvedValue({
      models: [
        { id: 'mistralai/magistral-small-2509', owned_by: 'mistralai' },
        { id: 'meta-llama/llama-3-8b', owned_by: 'meta-llama' },
      ],
    }),
    health: vi.fn().mockResolvedValue({ status: 'ok', name: 'ARIM' }),
    getSettings: vi.fn().mockResolvedValue({
      default_model: 'mistralai/magistral-small-2509',
      temperature: 0.7,
      max_tokens: -1,
      top_p: 1.0,
      context_length: null,
      chat_verbosity: 'standard',
      chat_style: 'bubbles',
    }),
    updateSettings: vi.fn().mockResolvedValue({
      default_model: 'mistralai/magistral-small-2509',
      temperature: 0.7,
      max_tokens: -1,
      top_p: 1.0,
      context_length: null,
      chat_verbosity: 'standard',
      chat_style: 'bubbles',
    }),
    getApiKeys: vi.fn().mockResolvedValue([]),
    getPrompts: vi.fn().mockResolvedValue([]),
    getToken: vi.fn().mockReturnValue('mock-token'),
  },
}));

function renderSettings(props?: Partial<React.ComponentProps<typeof Settings>>) {
  const defaultProps = {
    currentModel: 'mistralai/magistral-small-2509',
    onModelChange: vi.fn(),
    dark: true,
    toggleTheme: vi.fn(),
    appSettings: {
      default_model: 'mistralai/magistral-small-2509',
      temperature: 0.7,
      max_tokens: -1,
      top_p: 1.0,
      context_length: null,
      chat_verbosity: 'standard',
      chat_style: 'bubbles',
      timezone: null,
      tts_enabled: false,
    },
    onUpdateSettings: vi.fn().mockResolvedValue(undefined),
  };
  return render(
    <MemoryRouter>
      <Settings {...defaultProps} {...props} />
    </MemoryRouter>
  );
}

describe('Settings page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the Settings heading', () => {
    renderSettings();
    expect(screen.getByText('Settings')).toBeDefined();
  });

  it('renders System Status section', () => {
    renderSettings();
    expect(screen.getByText('System Status')).toBeDefined();
  });

  it('renders Model section heading', () => {
    renderSettings();
    expect(screen.getByText('Model')).toBeDefined();
  });

  it('renders Appearance section with dark mode toggle', () => {
    renderSettings();
    expect(screen.getByText('Appearance')).toBeDefined();
    expect(screen.getByText('Dark Mode')).toBeDefined();
  });

  it('renders Model Configuration section after settings load', async () => {
    renderSettings();
    // Model Configuration appears after async settings load
    const heading = await screen.findByText('Model Configuration');
    expect(heading).toBeDefined();
  });

  it('renders temperature and top p labels', async () => {
    renderSettings();
    const tempLabel = await screen.findByText('Temperature');
    expect(tempLabel).toBeDefined();
    const topPLabel = await screen.findByText('Top P');
    expect(topPLabel).toBeDefined();
  });

  it('renders max tokens and context length fields', async () => {
    renderSettings();
    const maxTokens = await screen.findByText('Max Tokens');
    expect(maxTokens).toBeDefined();
    const ctxLength = await screen.findByText('Context Length');
    expect(ctxLength).toBeDefined();
  });

  it('renders Save Configuration button', async () => {
    renderSettings();
    const saveBtn = await screen.findByText('Save Configuration');
    expect(saveBtn).toBeDefined();
  });

  it('shows model cards when models are loaded', async () => {
    renderSettings();
    const model1 = await screen.findByText('magistral-small-2509');
    expect(model1).toBeDefined();
    const model2 = await screen.findByText('llama-3-8b');
    expect(model2).toBeDefined();
  });
});
