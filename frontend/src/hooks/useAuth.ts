import { useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';

export function useAuth() {
  const [isAuthenticated, setIsAuthenticated] = useState(api.isAuthenticated());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const check = async () => {
      if (api.isAuthenticated()) {
        try {
          await api.health();
          setIsAuthenticated(true);
        } catch {
          setIsAuthenticated(false);
        }
      }
      setLoading(false);
    };
    check();
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    await api.login(username, password);
    setIsAuthenticated(true);
  }, []);

  const register = useCallback(async (username: string, password: string) => {
    await api.register(username, password);
    setIsAuthenticated(true);
  }, []);

  const guestLogin = useCallback(async () => {
    await api.guestLogin();
    setIsAuthenticated(true);
  }, []);

  const logout = useCallback(() => {
    api.logout();
    setIsAuthenticated(false);
  }, []);

  return { isAuthenticated, loading, login, register, guestLogin, logout };
}
