import { useState, useEffect, useCallback } from 'react';
import {
  Settings as SettingsIcon, Cpu, Check, Loader2, SlidersHorizontal, Save, Star,
  Key, Plus, Copy, Trash2, Eye, EyeOff, RefreshCw, MessageSquare, Download,
  RotateCcw, FileText, ChevronDown, ChevronRight, Clock,
} from 'lucide-react';
import { api } from '../services/api';
import type { AppSettings } from '../hooks/useSettings';
import { MobileHeader } from '../components/MobileHeader';

interface LoadConfigSchema {
  context_length?: { min?: number; max?: number };
  eval_batch_size?: boolean;
  flash_attention?: boolean;
  num_experts?: boolean;
  offload_kv_cache_to_gpu?: boolean;
}

/** Instance from API: legacy has context_length at top level; native has id + config. */
type LoadedInstance = {
  id?: string;
  config?: Record<string, unknown> & { context_length?: number };
  context_length?: number;
};

interface Model {
  id: string;
  owned_by?: string;
  publisher?: string;
  display_name?: string;
  type?: string;
  max_context_length?: number;
  loaded_instances?: LoadedInstance[];
  load_config_schema?: LoadConfigSchema;
}

interface ApiKey {
  id: string;
  key_prefix: string;
  label: string;
  created_at: string;
  last_used_at: string | null;
}

interface PromptSummary {
  id: string;
  name: string;
  description: string;
  agent: string;
  updated_at: string;
}

interface SettingsProps {
  currentModel: string | null;
  onModelChange: (model: string) => void;
  dark: boolean;
  toggleTheme: () => void;
  appSettings: AppSettings;
  onUpdateSettings: (partial: Partial<AppSettings>) => Promise<void>;
  onRefreshTts?: () => Promise<void>;
}

const VERBOSITY_OPTIONS = [
  { value: 'minimal', label: 'Minimal', desc: 'Final response only' },
  { value: 'standard', label: 'Standard', desc: 'Response + thinking blocks' },
  { value: 'detailed', label: 'Detailed', desc: 'Standard + tool call summaries' },
  { value: 'developer', label: 'Developer', desc: 'Everything including agent activity' },
];

const STYLE_OPTIONS = [
  { value: 'bubbles', label: 'Bubbles', desc: 'Chat bubble layout' },
  { value: 'flat', label: 'Flat', desc: 'Full-width, no bubbles' },
  { value: 'compact', label: 'Compact', desc: 'Reduced spacing' },
];

const TIMEZONE_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'Not set (use UTC)' },
  { value: '__browser__', label: 'Use my local timezone' },
  { value: 'America/New_York', label: 'Eastern (America/New_York)' },
  { value: 'America/Chicago', label: 'Central (America/Chicago)' },
  { value: 'America/Denver', label: 'Mountain (America/Denver)' },
  { value: 'America/Los_Angeles', label: 'Pacific (America/Los_Angeles)' },
  { value: 'Europe/London', label: 'Europe/London' },
  { value: 'Europe/Paris', label: 'Europe/Paris' },
  { value: 'Europe/Berlin', label: 'Europe/Berlin' },
  { value: 'Asia/Tokyo', label: 'Asia/Tokyo' },
  { value: 'Australia/Sydney', label: 'Australia/Sydney' },
  { value: 'UTC', label: 'UTC' },
];

export function Settings({ currentModel, onModelChange, dark, toggleTheme, appSettings, onUpdateSettings }: SettingsProps) {
  const [models, setModels] = useState<Model[]>([]);
  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState<{ status: string; name: string } | null>(null);
  const [temperature, setTemperature] = useState(appSettings.temperature);
  const [maxTokens, setMaxTokens] = useState(appSettings.max_tokens);
  const [topP, setTopP] = useState(appSettings.top_p);
  const [contextLength, setContextLength] = useState(appSettings.context_length);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [dirty, setDirty] = useState(false);

  const [loadConfigContextLength, setLoadConfigContextLength] = useState<number | null>(null);
  const [loadConfigNumExperts, setLoadConfigNumExperts] = useState<number | null>(null);
  const [loadConfigFlashAttention, setLoadConfigFlashAttention] = useState<boolean | null>(null);
  const [loadConfigEvalBatchSize, setLoadConfigEvalBatchSize] = useState<number | null>(null);
  const [loadConfigOffloadKv, setLoadConfigOffloadKv] = useState<boolean | null>(null);
  const [loadConfigReasoningEffort, setLoadConfigReasoningEffort] = useState<string | null>(null);
  const [loadConfigKeepAliveInterval, setLoadConfigKeepAliveInterval] = useState<number | null>(null);
  const [loadConfigMaxConcurrentPredictions, setLoadConfigMaxConcurrentPredictions] = useState<number | null>(null);

  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [keysLoading, setKeysLoading] = useState(true);
  const [showKeyForm, setShowKeyForm] = useState(false);
  const [keyLabel, setKeyLabel] = useState('Siri Shortcut');
  const [useCustomKey, setUseCustomKey] = useState(false);
  const [customKeyValue, setCustomKeyValue] = useState('');
  const [creatingKey, setCreatingKey] = useState(false);
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<string | null>(null);
  const [showNewKey, setShowNewKey] = useState(false);
  const [keyError, setKeyError] = useState('');
  const [copiedKeyId, setCopiedKeyId] = useState<string | null>(null);
  const [revokingKeyId, setRevokingKeyId] = useState<string | null>(null);

  const [prompts, setPrompts] = useState<PromptSummary[]>([]);
  const [promptsLoading, setPromptsLoading] = useState(true);
  const [expandedPrompt, setExpandedPrompt] = useState<string | null>(null);
  const [promptContent, setPromptContent] = useState('');
  const [promptDirty, setPromptDirty] = useState(false);
  const [promptSaving, setPromptSaving] = useState(false);

  useEffect(() => {
    setTemperature(appSettings.temperature);
    setMaxTokens(appSettings.max_tokens);
    setTopP(appSettings.top_p);
    setContextLength(appSettings.context_length);
    const lc = appSettings.model_load_config;
    if (lc) {
      setLoadConfigContextLength(lc.context_length ?? null);
      setLoadConfigNumExperts(lc.num_experts ?? null);
      setLoadConfigFlashAttention(lc.flash_attention ?? null);
      setLoadConfigEvalBatchSize(lc.eval_batch_size ?? null);
      setLoadConfigOffloadKv(lc.offload_kv_cache_to_gpu ?? null);
      setLoadConfigReasoningEffort(lc.reasoning_effort ?? null);
      setLoadConfigKeepAliveInterval(lc.keep_alive_interval_seconds ?? null);
      setLoadConfigMaxConcurrentPredictions(lc.max_concurrent_predictions ?? null);
    }
  }, [appSettings]);

  useEffect(() => {
    Promise.all([
      api.getModels().then((r) => setModels(r.models)).catch(() => {}),
      api.health().then(setHealth).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  const handleSetDefault = useCallback(async (modelId: string) => {
    onModelChange(modelId);
    setSaving(true);
    try {
      await onUpdateSettings({ default_model: modelId });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2000);
    } catch { /* ignore */ }
    setSaving(false);
  }, [onModelChange, onUpdateSettings]);

  const selectedModelId = currentModel || appSettings.default_model;
  const selectedModel = models.find((m) => m.id === selectedModelId);
  const loadSchema = selectedModel?.load_config_schema;

  const handleSaveModelConfig = useCallback(async () => {
    setSaving(true);
    try {
      const payload: Parameters<typeof onUpdateSettings>[0] = {
        temperature,
        max_tokens: maxTokens,
        top_p: topP,
        context_length: contextLength,
      };
      const loadConfig: Record<string, unknown> = {};
      if (loadConfigContextLength != null) loadConfig.context_length = loadConfigContextLength;
      if (loadConfigNumExperts != null) loadConfig.num_experts = loadConfigNumExperts;
      if (loadConfigFlashAttention != null) loadConfig.flash_attention = loadConfigFlashAttention;
      if (loadConfigEvalBatchSize != null) loadConfig.eval_batch_size = loadConfigEvalBatchSize;
      if (loadConfigOffloadKv != null) loadConfig.offload_kv_cache_to_gpu = loadConfigOffloadKv;
      if (loadConfigReasoningEffort != null) loadConfig.reasoning_effort = loadConfigReasoningEffort;
      if (loadConfigKeepAliveInterval != null) loadConfig.keep_alive_interval_seconds = loadConfigKeepAliveInterval;
      if (loadConfigMaxConcurrentPredictions != null) loadConfig.max_concurrent_predictions = loadConfigMaxConcurrentPredictions;
      if (Object.keys(loadConfig).length > 0) payload.model_load_config = loadConfig;
      await onUpdateSettings(payload);
      setDirty(false);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2000);
    } catch { /* ignore */ }
    setSaving(false);
  }, [temperature, maxTokens, topP, contextLength, onUpdateSettings, loadConfigContextLength, loadConfigNumExperts, loadConfigFlashAttention, loadConfigEvalBatchSize, loadConfigOffloadKv, loadConfigReasoningEffort, loadConfigKeepAliveInterval, loadConfigMaxConcurrentPredictions]);

  const loadApiKeys = useCallback(async () => {
    setKeysLoading(true);
    try { setApiKeys(await api.getApiKeys()); } catch { /* ignore */ }
    setKeysLoading(false);
  }, []);

  useEffect(() => { loadApiKeys(); }, [loadApiKeys]);

  const handleCreateKey = useCallback(async () => {
    setKeyError('');
    if (!keyLabel.trim()) { setKeyError('Label is required'); return; }
    if (useCustomKey && customKeyValue.length < 16) { setKeyError('Custom key must be at least 16 characters'); return; }
    setCreatingKey(true);
    try {
      const result = await api.createApiKey(keyLabel.trim(), useCustomKey ? customKeyValue : undefined);
      setNewlyCreatedKey(result.api_key);
      setShowNewKey(true);
      setShowKeyForm(false);
      setKeyLabel('Siri Shortcut');
      setCustomKeyValue('');
      setUseCustomKey(false);
      await loadApiKeys();
    } catch (e) { setKeyError(e instanceof Error ? e.message : 'Failed to create key'); }
    setCreatingKey(false);
  }, [keyLabel, useCustomKey, customKeyValue, loadApiKeys]);

  const handleRevokeKey = useCallback(async (keyId: string) => {
    setRevokingKeyId(keyId);
    try {
      await api.revokeApiKey(keyId);
      setApiKeys((prev) => prev.filter((k) => k.id !== keyId));
      if (newlyCreatedKey) setNewlyCreatedKey(null);
    } catch { /* ignore */ }
    setRevokingKeyId(null);
  }, [newlyCreatedKey]);

  const handleCopyKey = useCallback(async (text: string, id: string) => {
    await navigator.clipboard.writeText(text);
    setCopiedKeyId(id);
    setTimeout(() => setCopiedKeyId(null), 2000);
  }, []);

  // Prompts
  const loadPrompts = useCallback(async () => {
    setPromptsLoading(true);
    try { setPrompts(await api.getPrompts()); } catch { /* ignore */ }
    setPromptsLoading(false);
  }, []);

  useEffect(() => { loadPrompts(); }, [loadPrompts]);

  const handleExpandPrompt = useCallback(async (id: string) => {
    if (expandedPrompt === id) { setExpandedPrompt(null); return; }
    try {
      const p = await api.getPrompt(id);
      setPromptContent(p.content);
      setExpandedPrompt(id);
      setPromptDirty(false);
    } catch { /* ignore */ }
  }, [expandedPrompt]);

  const handleSavePrompt = useCallback(async () => {
    if (!expandedPrompt) return;
    setPromptSaving(true);
    try {
      await api.updatePrompt(expandedPrompt, promptContent);
      setPromptDirty(false);
      await loadPrompts();
    } catch { /* ignore */ }
    setPromptSaving(false);
  }, [expandedPrompt, promptContent, loadPrompts]);

  const handleResetPrompt = useCallback(async (id: string) => {
    if (!confirm('Reset this prompt to its default? This cannot be undone.')) return;
    try {
      const p = await api.resetPrompt(id);
      if (expandedPrompt === id) { setPromptContent(p.content); setPromptDirty(false); }
      await loadPrompts();
    } catch { /* ignore */ }
  }, [expandedPrompt, loadPrompts]);

  const handleDownloadPrompt = useCallback(async (id: string) => {
    try {
      await api.downloadPrompt(id, `${id}.md`);
    } catch { /* ignore */ }
  }, []);

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <MobileHeader title="Settings" />
      <div className="p-4 md:p-6 max-w-2xl mx-auto flex-1 w-full">
      <div className="hidden md:flex items-center gap-3 mb-6">
        <SettingsIcon className="w-6 h-6 text-[var(--color-primary)]" />
        <h1 className="text-xl font-bold">Settings</h1>
      </div>

      <div className="space-y-6">
        {/* Status */}
        <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-5">
          <h2 className="font-semibold text-sm mb-3">System Status</h2>
          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-[var(--color-text-secondary)]">Backend</span>
              <span className={`flex items-center gap-1.5 ${health ? 'text-green-400' : 'text-red-400'}`}>
                <span className={`w-2 h-2 rounded-full ${health ? 'bg-green-400' : 'bg-red-400'}`} />
                {health ? 'Connected' : 'Offline'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[var(--color-text-secondary)]">LM Studio Models</span>
              <span className="text-[var(--color-text-secondary)]">{models.length} available</span>
            </div>
          </div>
        </div>

        {/* Chat Experience */}
        <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-5">
          <h2 className="font-semibold text-sm mb-4 flex items-center gap-2">
            <MessageSquare className="w-4 h-4" />
            Chat Experience
          </h2>
          <div className="space-y-4">
            <div>
              <label className="text-sm text-[var(--color-text-secondary)] mb-2 block">Verbosity Level</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {VERBOSITY_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => onUpdateSettings({ chat_verbosity: opt.value })}
                    className={`text-left px-3 py-2 rounded-lg text-sm transition-colors border ${
                      appSettings.chat_verbosity === opt.value
                        ? 'bg-[var(--color-primary)]/10 border-[var(--color-primary)]/30 text-[var(--color-primary)]'
                        : 'border-transparent hover:bg-[var(--color-surface-hover)]'
                    }`}
                  >
                    <span className="font-medium block">{opt.label}</span>
                    <span className="text-xs opacity-60">{opt.desc}</span>
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-sm text-[var(--color-text-secondary)] mb-2 block">Chat Style</label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                {STYLE_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => onUpdateSettings({ chat_style: opt.value })}
                    className={`text-left px-3 py-2 rounded-lg text-sm transition-colors border ${
                      appSettings.chat_style === opt.value
                        ? 'bg-[var(--color-primary)]/10 border-[var(--color-primary)]/30 text-[var(--color-primary)]'
                        : 'border-transparent hover:bg-[var(--color-surface-hover)]'
                    }`}
                  >
                    <span className="font-medium block">{opt.label}</span>
                    <span className="text-xs opacity-60">{opt.desc}</span>
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-sm text-[var(--color-text-secondary)] mb-2 block flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5" />
                Time zone
              </label>
              <p className="text-xs text-[var(--color-text-secondary)] mb-2 opacity-80">
                Used when ARIM answers &quot;what time is it?&quot; and for relative times. Set to your local zone for accurate times.
              </p>
              <select
                value={
                  appSettings.timezone === null || appSettings.timezone === undefined
                    ? ''
                    : appSettings.timezone === (typeof Intl !== 'undefined' ? Intl.DateTimeFormat().resolvedOptions().timeZone : '')
                    ? '__browser__'
                    : TIMEZONE_OPTIONS.some((o) => o.value === appSettings.timezone)
                    ? appSettings.timezone
                    : '__custom__'
                }
                onChange={(e) => {
                  const v = e.target.value;
                  if (v === '') onUpdateSettings({ timezone: null });
                  else if (v === '__browser__') onUpdateSettings({ timezone: typeof Intl !== 'undefined' ? Intl.DateTimeFormat().resolvedOptions().timeZone : null });
                  else if (v !== '__custom__') onUpdateSettings({ timezone: v });
                }}
                className="w-full max-w-md px-3 py-2 rounded-lg text-sm bg-[var(--color-surface-elevated)] border border-[var(--color-border)] text-[var(--color-text)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50"
              >
                {TIMEZONE_OPTIONS.map((opt) => (
                  <option key={opt.value || 'none'} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
                {appSettings.timezone && appSettings.timezone !== (typeof Intl !== 'undefined' ? Intl.DateTimeFormat().resolvedOptions().timeZone : '') && !TIMEZONE_OPTIONS.some((o) => o.value === appSettings.timezone) && (
                  <option value="__custom__">{appSettings.timezone}</option>
                )}
              </select>
            </div>
          </div>
        </div>

        {/* Model selection */}
        <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-5">
          <h2 className="font-semibold text-sm mb-3 flex items-center gap-2">
            <Cpu className="w-4 h-4" />
            Model
          </h2>
          {loading ? (
            <Loader2 className="w-5 h-5 animate-spin text-[var(--color-text-secondary)]" />
          ) : models.length === 0 ? (
            <p className="text-sm text-[var(--color-text-secondary)]">No models found. Is LM Studio running?</p>
          ) : (
            <div className="space-y-2">
              {models.map((m) => {
                const isSessionModel = currentModel === m.id;
                const isDefault = appSettings.default_model === m.id;
                const inst = m.loaded_instances?.[0];
                const loadedCtx = inst?.context_length ?? (inst?.config?.context_length);
                return (
                  <div
                    key={m.id}
                    className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm text-left transition-colors ${
                      isSessionModel
                        ? 'bg-[var(--color-primary)]/10 border border-[var(--color-primary)]/30 text-[var(--color-primary)]'
                        : 'hover:bg-[var(--color-surface-hover)] border border-transparent'
                    }`}
                  >
                    <button onClick={() => onModelChange(m.id)} className="flex-1 min-w-0 text-left">
                      <div className="flex items-center gap-2 min-w-0">
                        <p className="font-medium truncate">{m.id.split('/').pop()}</p>
                        {isDefault && (
                          <span className="inline-flex items-center gap-1 text-xs bg-[var(--color-primary)]/15 text-[var(--color-primary)] px-1.5 py-0.5 rounded-full">
                            <Star className="w-3 h-3" /> Default
                          </span>
                        )}
                      </div>
                      <p className="text-xs opacity-60">{m.id}</p>
                      {(loadedCtx || m.max_context_length) && (
                        <p className="text-xs opacity-50 mt-0.5">Context: {loadedCtx || m.max_context_length} tokens</p>
                      )}
                    </button>
                    <div className="flex items-center gap-2 shrink-0">
                      {isSessionModel && <Check className="w-4 h-4" />}
                      {!isDefault && (
                        <button onClick={() => handleSetDefault(m.id)} disabled={saving}
                          className="text-xs px-2 py-1 rounded-md bg-[var(--color-surface-hover)] hover:bg-[var(--color-primary)]/10 hover:text-[var(--color-primary)] transition-colors"
                          title="Set as default model"
                        >Set Default</button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Model Configuration */}
        <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-5">
          <h2 className="font-semibold text-sm mb-4 flex items-center gap-2">
            <SlidersHorizontal className="w-4 h-4" />
            Model Configuration
          </h2>
          <div className="space-y-5">
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm text-[var(--color-text-secondary)]">Temperature</label>
                <span className="text-sm font-mono tabular-nums bg-[var(--color-bg)] px-2 py-0.5 rounded-md border border-[var(--color-border)]">
                  {temperature.toFixed(1)}
                </span>
              </div>
              <input type="range" min="0" max="2" step="0.1" value={temperature}
                onChange={(e) => { setTemperature(parseFloat(e.target.value)); setDirty(true); setSaveSuccess(false); }}
                className="w-full accent-[var(--color-primary)] h-2 rounded-full"
              />
              <div className="flex justify-between text-xs text-[var(--color-text-secondary)] opacity-50 mt-1">
                <span>Precise</span><span>Creative</span>
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm text-[var(--color-text-secondary)]">Top P</label>
                <span className="text-sm font-mono tabular-nums bg-[var(--color-bg)] px-2 py-0.5 rounded-md border border-[var(--color-border)]">
                  {topP.toFixed(2)}
                </span>
              </div>
              <input type="range" min="0" max="1" step="0.05" value={topP}
                onChange={(e) => { setTopP(parseFloat(e.target.value)); setDirty(true); setSaveSuccess(false); }}
                className="w-full accent-[var(--color-primary)] h-2 rounded-full"
              />
              <div className="flex justify-between text-xs text-[var(--color-text-secondary)] opacity-50 mt-1">
                <span>Focused</span><span>Diverse</span>
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm text-[var(--color-text-secondary)]">Max Tokens</label>
                <span className="text-xs text-[var(--color-text-secondary)] opacity-60">-1 = unlimited</span>
              </div>
              <input type="number" value={maxTokens} min={-1}
                onChange={(e) => { setMaxTokens(parseInt(e.target.value) || -1); setDirty(true); setSaveSuccess(false); }}
                className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50 focus:border-[var(--color-primary)]"
                placeholder="-1"
              />
            </div>
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm text-[var(--color-text-secondary)]">Context Length</label>
                <span className="text-xs text-[var(--color-text-secondary)] opacity-60">blank = model default</span>
              </div>
              <input type="number" value={contextLength ?? ''} min={256} step={256}
                onChange={(e) => { const v = e.target.value; setContextLength(v === '' ? null : parseInt(v) || null); setDirty(true); setSaveSuccess(false); }}
                className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50 focus:border-[var(--color-primary)]"
                placeholder="e.g. 8192"
              />
            </div>

            {loadSchema && selectedModelId && (
              <>
                <p className="text-xs text-[var(--color-text-secondary)] font-medium">LM Studio load options (for {selectedModel?.display_name || selectedModelId})</p>
                {'context_length' in loadSchema && (
                  <div>
                    <label className="text-sm text-[var(--color-text-secondary)] mb-2 block">Load context length</label>
                    <input type="number" value={loadConfigContextLength ?? ''} min={loadSchema.context_length?.min ?? 256} max={loadSchema.context_length?.max ?? 128000} step={256}
                      onChange={(e) => { const v = e.target.value; setLoadConfigContextLength(v === '' ? null : parseInt(v) || null); setDirty(true); setSaveSuccess(false); }}
                      className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50"
                      placeholder="optional"
                    />
                  </div>
                )}
                {'num_experts' in loadSchema && (
                  <div>
                    <label className="text-sm text-[var(--color-text-secondary)] mb-2 block">Number of experts (MoE)</label>
                    <input type="number" value={loadConfigNumExperts ?? ''} min={0}
                      onChange={(e) => { const v = e.target.value; setLoadConfigNumExperts(v === '' ? null : parseInt(v) || null); setDirty(true); setSaveSuccess(false); }}
                      className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50"
                      placeholder="optional"
                    />
                    <p className="text-xs text-[var(--color-text-secondary)] opacity-60 mt-1">Only applies to MoE models on LM Studio&apos;s llama.cpp engine. Check backend logs for applied load_config.</p>
                  </div>
                )}
                {'flash_attention' in loadSchema && (
                  <div className="flex items-center justify-between">
                    <label className="text-sm text-[var(--color-text-secondary)]">Flash attention</label>
                    <button type="button" onClick={() => { setLoadConfigFlashAttention(loadConfigFlashAttention !== true); setDirty(true); setSaveSuccess(false); }}
                      className={`px-3 py-1.5 rounded-lg text-sm ${loadConfigFlashAttention ? 'bg-[var(--color-primary)]/20 text-[var(--color-primary)]' : 'bg-[var(--color-surface-hover)]'}`}
                    >
                      {loadConfigFlashAttention ? 'On' : 'Off'}
                    </button>
                  </div>
                )}
                {'eval_batch_size' in loadSchema && (
                  <div>
                    <label className="text-sm text-[var(--color-text-secondary)] mb-2 block">Eval batch size</label>
                    <input type="number" value={loadConfigEvalBatchSize ?? ''} min={1}
                      onChange={(e) => { const v = e.target.value; setLoadConfigEvalBatchSize(v === '' ? null : parseInt(v) || null); setDirty(true); setSaveSuccess(false); }}
                      className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50"
                      placeholder="optional"
                    />
                  </div>
                )}
                {'offload_kv_cache_to_gpu' in loadSchema && (
                  <div className="flex items-center justify-between">
                    <label className="text-sm text-[var(--color-text-secondary)]">Offload KV cache to GPU</label>
                    <button type="button" onClick={() => { setLoadConfigOffloadKv(loadConfigOffloadKv !== true); setDirty(true); setSaveSuccess(false); }}
                      className={`px-3 py-1.5 rounded-lg text-sm ${loadConfigOffloadKv !== false ? 'bg-[var(--color-primary)]/20 text-[var(--color-primary)]' : 'bg-[var(--color-surface-hover)]'}`}
                    >
                      {loadConfigOffloadKv !== false ? 'On' : 'Off'}
                    </button>
                  </div>
                )}
                <div>
                  <label className="text-sm text-[var(--color-text-secondary)] mb-2 block">Reasoning effort</label>
                  <select value={loadConfigReasoningEffort ?? ''} onChange={(e) => { setLoadConfigReasoningEffort(e.target.value || null); setDirty(true); setSaveSuccess(false); }}
                    className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50"
                  >
                    <option value="">Default</option>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                  </select>
                </div>
                <div>
                  <label className="text-sm text-[var(--color-text-secondary)] mb-2 block">Keep-alive interval (seconds)</label>
                  <input type="number" value={loadConfigKeepAliveInterval ?? ''} min={0} step={60}
                    onChange={(e) => { const v = e.target.value; setLoadConfigKeepAliveInterval(v === '' ? null : parseInt(v) || null); setDirty(true); setSaveSuccess(false); }}
                    className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50"
                    placeholder="0 = disabled, e.g. 1800"
                  />
                  <p className="text-xs text-[var(--color-text-secondary)] opacity-60 mt-1">0 = off; e.g. 1800 = ping every 30 min to avoid idle unload</p>
                </div>
                <div>
                  <label className="text-sm text-[var(--color-text-secondary)] mb-2 block">Max concurrent predictions</label>
                  <input type="number" value={loadConfigMaxConcurrentPredictions ?? ''} min={1}
                    onChange={(e) => { const v = e.target.value; setLoadConfigMaxConcurrentPredictions(v === '' ? null : parseInt(v) || null); setDirty(true); setSaveSuccess(false); }}
                    className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50"
                    placeholder="e.g. 4"
                  />
                  <p className="text-xs text-[var(--color-text-secondary)] opacity-60 mt-1">Not supported by LM Studio REST load API yet. Set in LM Studio app: Developer tab → Server Settings.</p>
                </div>
              </>
            )}

            <button onClick={handleSaveModelConfig} disabled={saving || !dirty}
              className={`flex items-center justify-center gap-2 w-full px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                saveSuccess ? 'bg-green-500/10 text-green-400 border border-green-500/30'
                  : dirty ? 'bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] text-white'
                  : 'bg-[var(--color-surface-hover)] text-[var(--color-text-secondary)] cursor-not-allowed'
              }`}
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : saveSuccess ? <><Check className="w-4 h-4" /> Saved</> : <><Save className="w-4 h-4" /> Save Configuration</>}
            </button>
          </div>
        </div>

        {/* Prompts */}
        <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-5">
          <h2 className="font-semibold text-sm mb-4 flex items-center gap-2">
            <FileText className="w-4 h-4" />
            System Prompts
          </h2>
          <p className="text-xs text-[var(--color-text-secondary)] mb-4">
            View and edit the prompts that control ARIM's behavior. Changes take effect immediately.
          </p>
          {promptsLoading ? (
            <div className="flex justify-center py-4"><Loader2 className="w-5 h-5 animate-spin text-[var(--color-text-secondary)]" /></div>
          ) : prompts.length === 0 ? (
            <p className="text-sm text-[var(--color-text-secondary)] text-center py-4">No prompts configured.</p>
          ) : (
            <div className="space-y-2">
              {prompts.map((p) => (
                <div key={p.id} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] overflow-hidden">
                  <button
                    onClick={() => handleExpandPrompt(p.id)}
                    className="flex items-center gap-2 w-full px-3 py-2.5 text-left hover:bg-[var(--color-surface-hover)] transition-colors"
                  >
                    {expandedPrompt === p.id ? <ChevronDown className="w-3.5 h-3.5 shrink-0" /> : <ChevronRight className="w-3.5 h-3.5 shrink-0" />}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">{p.name}</span>
                        {p.agent && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-primary)]/10 text-[var(--color-primary)]">{p.agent}</span>
                        )}
                      </div>
                      {p.description && <p className="text-xs text-[var(--color-text-secondary)] opacity-70 truncate">{p.description}</p>}
                    </div>
                    <span className="text-[10px] text-[var(--color-text-secondary)] opacity-50 shrink-0">
                      {new Date(p.updated_at).toLocaleDateString()}
                    </span>
                  </button>
                  {expandedPrompt === p.id && (
                    <div className="border-t border-[var(--color-border)] p-3 space-y-3">
                      <textarea
                        value={promptContent}
                        onChange={(e) => { setPromptContent(e.target.value); setPromptDirty(true); }}
                        className="w-full h-64 px-3 py-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-sm font-mono resize-y focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50 focus:border-[var(--color-primary)]"
                      />
                      <div className="flex items-center gap-2">
                        <button onClick={handleSavePrompt} disabled={promptSaving || !promptDirty}
                          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                            promptDirty ? 'bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] text-white' : 'bg-[var(--color-surface-hover)] text-[var(--color-text-secondary)] cursor-not-allowed'
                          }`}
                        >
                          {promptSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                          Save
                        </button>
                        <button onClick={() => handleDownloadPrompt(p.id)}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-[var(--color-surface-hover)] hover:bg-[var(--color-primary)]/10 hover:text-[var(--color-primary)] transition-colors"
                        >
                          <Download className="w-3.5 h-3.5" /> Download .md
                        </button>
                        <button onClick={() => handleResetPrompt(p.id)}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-red-400 hover:bg-red-500/10 transition-colors ml-auto"
                        >
                          <RotateCcw className="w-3.5 h-3.5" /> Reset
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* API Keys */}
        <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-sm flex items-center gap-2">
              <Key className="w-4 h-4" />
              Webhook API Keys
            </h2>
            {!showKeyForm && (
              <button onClick={() => { setShowKeyForm(true); setKeyError(''); setNewlyCreatedKey(null); }}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] text-white transition-colors"
              >
                <Plus className="w-3.5 h-3.5" /> New Key
              </button>
            )}
          </div>
          <p className="text-xs text-[var(--color-text-secondary)] mb-4">
            API keys authenticate your Siri Shortcuts and external tools with the webhook endpoint.
          </p>
          {newlyCreatedKey && (
            <div className="mb-4 p-3 rounded-lg bg-green-500/10 border border-green-500/30">
              <p className="text-xs text-green-400 font-medium mb-2">Key created — copy it now, it won't be shown again.</p>
              <div className="flex items-center gap-2 min-w-0">
                <code className="flex-1 min-w-0 max-w-full text-sm font-mono bg-[var(--color-bg)] px-3 py-2 rounded-md border border-[var(--color-border)] break-all select-all overflow-x-auto">
                  {showNewKey ? newlyCreatedKey : '\u2022'.repeat(32)}
                </code>
                <button onClick={() => setShowNewKey(!showNewKey)} className="p-2 rounded-md hover:bg-[var(--color-surface-hover)] text-[var(--color-text-secondary)] transition-colors" title={showNewKey ? 'Hide' : 'Show'}>
                  {showNewKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
                <button onClick={() => handleCopyKey(newlyCreatedKey, 'new')} className="p-2 rounded-md hover:bg-[var(--color-surface-hover)] text-[var(--color-text-secondary)] transition-colors" title="Copy to clipboard">
                  {copiedKeyId === 'new' ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
                </button>
              </div>
            </div>
          )}
          {showKeyForm && (
            <div className="mb-4 p-4 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-[var(--color-text-secondary)] mb-1 block">Label</label>
                  <input type="text" value={keyLabel} onChange={(e) => setKeyLabel(e.target.value)} placeholder="e.g. Siri Shortcut, Home Automation"
                    className="w-full px-3 py-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50 focus:border-[var(--color-primary)]"
                  />
                </div>
                <div>
                  <button onClick={() => setUseCustomKey(!useCustomKey)} className="flex items-center gap-2 text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text)] transition-colors">
                    <div className={`w-8 h-5 rounded-full transition-colors relative ${useCustomKey ? 'bg-[var(--color-primary)]' : 'bg-[var(--color-border)]'}`}>
                      <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${useCustomKey ? 'left-3.5' : 'left-0.5'}`} />
                    </div>
                    Use custom key
                  </button>
                </div>
                {useCustomKey && (
                  <div>
                    <label className="text-xs text-[var(--color-text-secondary)] mb-1 block">Custom Key <span className="opacity-60">(min 16 characters)</span></label>
                    <input type="text" value={customKeyValue} onChange={(e) => setCustomKeyValue(e.target.value)} placeholder="Enter your own key string..."
                      className="w-full px-3 py-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50 focus:border-[var(--color-primary)]"
                    />
                    {customKeyValue.length > 0 && customKeyValue.length < 16 && (
                      <p className="text-xs text-amber-400 mt-1">{16 - customKeyValue.length} more characters needed</p>
                    )}
                  </div>
                )}
                {keyError && <p className="text-xs text-red-400">{keyError}</p>}
                <div className="flex gap-2 pt-1">
                  <button onClick={handleCreateKey} disabled={creatingKey}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] text-white transition-colors disabled:opacity-50"
                  >
                    {creatingKey ? <Loader2 className="w-4 h-4 animate-spin" /> : useCustomKey ? <Key className="w-4 h-4" /> : <RefreshCw className="w-4 h-4" />}
                    {useCustomKey ? 'Save Key' : 'Generate Key'}
                  </button>
                  <button onClick={() => { setShowKeyForm(false); setKeyError(''); }}
                    className="px-4 py-2 rounded-lg text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] transition-colors"
                  >Cancel</button>
                </div>
              </div>
            </div>
          )}
          {keysLoading ? (
            <div className="flex justify-center py-4"><Loader2 className="w-5 h-5 animate-spin text-[var(--color-text-secondary)]" /></div>
          ) : apiKeys.length === 0 ? (
            <p className="text-sm text-[var(--color-text-secondary)] text-center py-4">No API keys yet. Create one to use with Siri Shortcuts.</p>
          ) : (
            <div className="space-y-2">
              {apiKeys.map((key) => (
                <div key={key.id} className="flex items-center justify-between px-3 py-2.5 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium truncate">{key.label}</span>
                      <code className="text-xs font-mono text-[var(--color-text-secondary)] bg-[var(--color-surface-hover)] px-1.5 py-0.5 rounded">{key.key_prefix}...</code>
                    </div>
                    <p className="text-xs text-[var(--color-text-secondary)] mt-0.5">
                      Created {new Date(key.created_at).toLocaleDateString()}
                      {key.last_used_at && <> · Last used {new Date(key.last_used_at).toLocaleDateString()}</>}
                    </p>
                  </div>
                  <button onClick={() => handleRevokeKey(key.id)} disabled={revokingKeyId === key.id}
                    className="p-2 rounded-md hover:bg-red-500/10 text-[var(--color-text-secondary)] hover:text-red-400 transition-colors" title="Revoke key"
                  >
                    {revokingKeyId === key.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                  </button>
                </div>
              ))}
            </div>
          )}
          {apiKeys.length > 0 && (
            <div className="mt-4 p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
              <p className="text-xs text-[var(--color-text-secondary)] font-medium mb-1">Using with Siri Shortcuts</p>
              <p className="text-xs text-[var(--color-text-secondary)] opacity-70">
                In your shortcut, set the Authorization header to{' '}
                <code className="bg-[var(--color-surface-hover)] px-1 py-0.5 rounded">Bearer &lt;your-key&gt;</code>{' '}
                when calling{' '}
                <code className="bg-[var(--color-surface-hover)] px-1 py-0.5 rounded">POST /webhook</code>
              </p>
            </div>
          )}
        </div>

        {/* Appearance */}
        <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-5">
          <h2 className="font-semibold text-sm mb-3">Appearance</h2>
          <button onClick={toggleTheme} className="flex items-center justify-between w-full px-3 py-2.5 rounded-lg hover:bg-[var(--color-surface-hover)] text-sm">
            <span>Dark Mode</span>
            <div className={`w-10 h-6 rounded-full transition-colors relative ${dark ? 'bg-[var(--color-primary)]' : 'bg-[var(--color-border)]'}`}>
              <div className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${dark ? 'left-5' : 'left-1'}`} />
            </div>
          </button>
        </div>
      </div>
      </div>
    </div>
  );
}
