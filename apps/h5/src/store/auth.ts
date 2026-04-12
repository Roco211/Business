import type { User } from '../types';

const TOKEN_KEY = 'authToken';
const USER_KEY = 'currentUser';

export const authStore = {
  getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  },

  setToken(token: string) {
    localStorage.setItem(TOKEN_KEY, token);
  },

  getUser(): User | null {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  },

  setUser(user: User) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  },

  save(token: string, user: User) {
    this.setToken(token);
    this.setUser(user);
  },

  clear() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },

  isLoggedIn(): boolean {
    return !!this.getToken();
  },
};
