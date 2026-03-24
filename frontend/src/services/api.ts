const BASE_URL = '/api';

function getToken(): string | null {
  return localStorage.getItem('access_token');
}

function setTokens(access: string, refresh: string) {
  localStorage.setItem('access_token', access);
  localStorage.setItem('refresh_token', refresh);
}

function clearTokens() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (res.status === 401) {
    const refreshed = await tryRefresh();
    if (refreshed) return request(path, options);
    clearTokens();
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }

  return res.json();
}

// --- Calendar events (shared types for list / get / create response / update response) ---
export interface CalendarEvent {
  id: number;
  user_id?: number;
  title: string;
  description?: string;
  start_time: string;
  end_time?: string;
  all_day: boolean;
  recurrence?: string;
  created_at?: string;
}

export interface CalendarEventCreate {
  title: string;
  description?: string;
  start_time: string;
  end_time?: string;
  all_day?: boolean;
  recurrence?: string;
}

export interface CalendarEventUpdate {
  title?: string;
  description?: string;
  start_time?: string;
  end_time?: string;
  all_day?: boolean;
  recurrence?: string;
}

export interface ModelLoadConfig {
  context_length?: number | null;
  num_experts?: number | null;
  flash_attention?: boolean | null;
  eval_batch_size?: number | null;
  offload_kv_cache_to_gpu?: boolean | null;
  reasoning_effort?: string | null;
  keep_alive_interval_seconds?: number | null;
  max_concurrent_predictions?: number | null;
}

export interface ModelLoadConfigUpdate {
  context_length?: number | null;
  num_experts?: number | null;
  flash_attention?: boolean | null;
  eval_batch_size?: number | null;
  offload_kv_cache_to_gpu?: boolean | null;
  reasoning_effort?: string | null;
  keep_alive_interval_seconds?: number | null;
  max_concurrent_predictions?: number | null;
}

async function tryRefresh(): Promise<boolean> {
  const refreshToken = localStorage.getItem('refresh_token');
  if (!refreshToken) return false;

  try {
    const res = await fetch(`${BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    setTokens(data.access_token, data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

export const api = {
  login: async (username: string, password: string) => {
    const data = await request<{ access_token: string; refresh_token: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    setTokens(data.access_token, data.refresh_token);
    return data;
  },

  register: async (username: string, password: string) => {
    const data = await request<{ access_token: string; refresh_token: string }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    setTokens(data.access_token, data.refresh_token);
    return data;
  },

  guestLogin: async () => {
    const data = await request<{ access_token: string; refresh_token: string }>('/auth/guest', {
      method: 'POST',
    });
    setTokens(data.access_token, data.refresh_token);
    return data;
  },

  logout: () => {
    clearTokens();
    window.location.href = '/login';
  },

  isAuthenticated: () => !!getToken(),

  chat: (message: string, conversationId?: number, model?: string) =>
    request<{ conversation_id: number; message: string; model: string }>('/chat', {
      method: 'POST',
      body: JSON.stringify({ message, conversation_id: conversationId, model }),
    }),

  getConversations: () =>
    request<{ id: number; title: string; created_at: string; updated_at: string }[]>('/chat/conversations'),

  getMessages: (conversationId: number) =>
    request<{ id: number; role: string; content: string; model: string; agent_events?: any[]; created_at: string }[]>(
      `/chat/conversations/${conversationId}/messages`
    ),

  deleteConversation: (conversationId: number) =>
    request(`/chat/conversations/${conversationId}`, { method: 'DELETE' }),

  getModels: () =>
    request<{
      models: Array<{
        id: string;
        owned_by?: string;
        publisher?: string;
        display_name?: string;
        type?: string;
        max_context_length?: number;
        loaded_instances?: Array<{ id?: string; config?: Record<string, unknown>; context_length?: number }>;
        load_config_schema?: Record<string, unknown>;
      }>;
    }>('/models'),

  health: () => request<{ status: string; name: string }>('/health'),

  getSettings: () =>
    request<{
      default_model: string | null;
      temperature: number;
      max_tokens: number;
      top_p: number;
      context_length: number | null;
      chat_verbosity: string;
      chat_style: string;
      timezone: string | null;
      model_load_config?: ModelLoadConfig | null;
    }>('/settings'),

  updateSettings: (settings: {
    default_model?: string | null;
    temperature?: number;
    max_tokens?: number;
    top_p?: number;
    context_length?: number | null;
    chat_verbosity?: string;
    chat_style?: string;
    timezone?: string | null;
    model_load_config?: ModelLoadConfigUpdate | null;
  }) =>
    request<{
      default_model: string | null;
      temperature: number;
      max_tokens: number;
      top_p: number;
      context_length: number | null;
      chat_verbosity: string;
      chat_style: string;
      timezone: string | null;
      model_load_config?: ModelLoadConfig | null;
    }>('/settings', {
      method: 'PUT',
      body: JSON.stringify(settings),
    }),

  getNotes: () =>
    request<{ id: number; title: string; content: string; created_at: string; updated_at: string }[]>('/notes'),

  createNote: (title: string, content: string) =>
    request<{ id: number; title: string; content: string; created_at: string; updated_at: string }>('/notes', {
      method: 'POST',
      body: JSON.stringify({ title, content }),
    }),

  getNote: (noteId: number) =>
    request<{ id: number; title: string; content: string; created_at: string; updated_at: string }>(
      `/notes/${noteId}`
    ),

  updateNote: (noteId: number, data: { title?: string; content?: string }) =>
    request<{ id: number; title: string; content: string; created_at: string; updated_at: string }>(
      `/notes/${noteId}`,
      { method: 'PUT', body: JSON.stringify(data) }
    ),

  deleteNote: (noteId: number) =>
    request<{ success: boolean; deleted_id: number }>(`/notes/${noteId}`, { method: 'DELETE' }),

  searchNotes: (query: string, limit = 10) =>
    request<{ id: number; title: string; content: string; created_at: string; updated_at: string }[]>(
      '/notes/search',
      { method: 'POST', body: JSON.stringify({ query, limit }) }
    ),

  getCalendarEvents: (options?: { start?: string; end?: string }) => {
    const params: Record<string, string> = {};
    if (options?.start != null) params.start = options.start;
    if (options?.end != null) params.end = options.end;
    const qs = Object.keys(params).length ? '?' + new URLSearchParams(params).toString() : '';
    return request<CalendarEvent[]>(`/calendar/events${qs}`);
  },
  createCalendarEvent: (payload: CalendarEventCreate) =>
    request<CalendarEvent>('/calendar/events', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getCalendarEvent: (id: number) => request<CalendarEvent>(`/calendar/events/${id}`),
  updateCalendarEvent: (id: number, payload: CalendarEventUpdate) =>
    request<CalendarEvent>(`/calendar/events/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  deleteCalendarEvent: (id: number) => request<void>(`/calendar/events/${id}`, { method: 'DELETE' }),

  getApiKeys: () =>
    request<{ id: string; key_prefix: string; label: string; created_at: string; last_used_at: string | null }[]>(
      '/account/api-keys'
    ),

  createApiKey: (label: string, customKey?: string) =>
    request<{ id: string; api_key: string; key_prefix: string; label: string }>('/account/api-keys', {
      method: 'POST',
      body: JSON.stringify({ label, ...(customKey ? { custom_key: customKey } : {}) }),
    }),

  revokeApiKey: (keyId: string) =>
    request<void>(`/account/api-keys/${keyId}`, { method: 'DELETE' }),

  tts: async (text: string, voice?: string): Promise<Blob> => {
    const token = getToken();
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/tts`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ text, voice }),
    });
    if (!res.ok) throw new Error('TTS failed');
    return res.blob();
  },

  ttsStatus: () =>
    request<{ enabled: boolean; available: boolean }>('/tts/status'),

  getPrompts: () =>
    request<{ id: string; name: string; description: string; agent: string; updated_at: string }[]>('/prompts'),

  getPrompt: (id: string) =>
    request<{ id: string; name: string; description: string; agent: string; content: string; updated_at: string }>(`/prompts/${id}`),

  updatePrompt: (id: string, content: string) =>
    request<{ id: string; name: string; content: string; updated_at: string }>(`/prompts/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ content }),
    }),

  resetPrompt: (id: string) =>
    request<{ id: string; name: string; content: string; updated_at: string }>(`/prompts/${id}/reset`, {
      method: 'POST',
    }),

  downloadPrompt: async (id: string, filename: string) => {
    const token = getToken();
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(`${BASE_URL}/prompts/${id}/download`, { headers });
    if (!res.ok) throw new Error('Download failed');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || `${id}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },

  getToken,
};
