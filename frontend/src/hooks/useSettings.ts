import { useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';
import type { ModelLoadConfig } from '../services/api';

export interface AppSettings {
  default_model: string | null;
  temperature: number;
  max_tokens: number;
  top_p: number;
  context_length: number | null;
  chat_verbosity: string;
  chat_style: string;
  timezone: string | null;
  tts_enabled: boolean;
  model_load_config?: ModelLoadConfig | null;
}

const DEFAULTS: AppSettings = {
  default_model: null,
  temperature: 0.7,
  max_tokens: -1,
  top_p: 1.0,
  context_length: null,
  chat_verbosity: 'standard',
  chat_style: 'bubbles',
  timezone: null,
  tts_enabled: false,
  model_load_config: null,
};

export function useSettings() {
  const [settings, setSettings] = useState<AppSettings>(DEFAULTS);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api.getSettings()
      .then((s) => {
        setSettings({ ...DEFAULTS, ...s });
        setLoaded(true);
      })
      .catch(() => setLoaded(true));

    api.ttsStatus()
      .then((s) => setSettings((prev) => ({ ...prev, tts_enabled: s.enabled && s.available })))
      .catch(() => {});
  }, []);

  const updateSettings = useCallback(async (partial: Partial<AppSettings>) => {
    setSettings((prev) => ({ ...prev, ...partial }));
    try {
      const updated = await api.updateSettings(partial);
      setSettings((prev) => ({ ...prev, ...updated }));
    } catch { /* ignore */ }
  }, []);

  const refreshTts = useCallback(async () => {
    try {
      const s = await api.ttsStatus();
      setSettings((prev) => ({ ...prev, tts_enabled: s.enabled && s.available }));
    } catch { /* ignore */ }
  }, []);

  return { settings, loaded, updateSettings, refreshTts };
}
