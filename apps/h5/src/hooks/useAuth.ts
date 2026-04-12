import { useState, useEffect, useCallback } from 'react';
import { authStore } from '../store/auth';
import { authApi } from '../api/auth';
import type { User } from '../types';

export function useAuth() {
  const [user, setUser] = useState<User | null>(authStore.getUser());
  const [loading, setLoading] = useState(false);

  const checkAuth = useCallback(async () => {
    if (!authStore.isLoggedIn()) return;
    setLoading(true);
    try {
      const res = await authApi.me();
      if (res.data.success && res.data.data) {
        const u = res.data.data;
        const userData: User = { user_id: u.user_id, username: u.username, nickname: u.nickname, shop_id: u.shop_id };
        authStore.setUser(userData);
        setUser(userData);
      }
    } catch {
      authStore.clear();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await authApi.login({ username, password });
    if (res.data.success && res.data.token) {
      const userData: User = {
        user_id: res.data.user_id || '',
        username: res.data.username || username,
        nickname: res.data.nickname,
        shop_id: '',
      };
      authStore.save(res.data.token, userData);
      setUser(userData);
      return { success: true };
    }
    return { success: false, message: res.data.message };
  }, []);

  const register = useCallback(async (data: { username: string; password: string; phone?: string; email?: string; code: string }) => {
    const res = await authApi.register(data);
    if (res.data.success && res.data.token) {
      const userData: User = {
        user_id: res.data.user_id || '',
        username: res.data.username || data.username,
        nickname: res.data.nickname,
        shop_id: '',
      };
      authStore.save(res.data.token, userData);
      setUser(userData);
      return { success: true };
    }
    return { success: false, message: res.data.message };
  }, []);

  const logout = useCallback(async () => {
    try { await authApi.logout(); } catch { /* ignore */ }
    authStore.clear();
    setUser(null);
  }, []);

  useEffect(() => { checkAuth(); }, [checkAuth]);

  return { user, loading, login, register, logout, checkAuth };
}
