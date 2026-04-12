import client from './client';
import type { LoginResponse } from '../types';

export const authApi = {
  sendCode(phone?: string, email?: string, codeType = 'register') {
    return client.post('/auth/send-code', { phone, email, code_type: codeType });
  },

  register(data: { username: string; password: string; phone?: string; email?: string; code: string }) {
    return client.post<LoginResponse>('/auth/register', data);
  },

  login(data: { username?: string; phone?: string; email?: string; password?: string; code?: string }) {
    return client.post<LoginResponse>('/auth/login', data);
  },

  logout() {
    return client.post('/auth/logout');
  },

  me() {
    return client.get<{ success: boolean; data?: { user_id: string; username: string; nickname?: string; shop_id: string } }>('/auth/me');
  },
};
