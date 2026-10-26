import { create } from 'zustand';
import { login as apiLogin, getStoredToken, setStoredToken, clearStoredToken } from '../api/client';
import type { UserSession } from '../types';

interface AuthState {
  token: string | null;
  user: UserSession | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
  initialize: () => void;
}

function parseJwt(token: string): { sub?: string; role?: string; user_id?: number } | null {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,

  initialize: () => {
    const storedToken = getStoredToken();
    if (storedToken) {
      const claims = parseJwt(storedToken);
      if (claims && claims.sub) {
        set({
          token: storedToken,
          user: {
            username: claims.sub,
            role: (claims.role as 'viewer' | 'operator' | 'admin') || 'viewer',
            user_id: claims.user_id,
          },
          isAuthenticated: true,
          isLoading: false,
        });
        return;
      }
    }
    set({ token: null, user: null, isAuthenticated: false, isLoading: false });
  },

  login: async (username: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      const res = await apiLogin(username, password);
      const claims = parseJwt(res.access_token);
      const userSession: UserSession = {
        username: claims?.sub || username,
        role: (claims?.role as 'viewer' | 'operator' | 'admin') || 'viewer',
        user_id: claims?.user_id,
      };

      setStoredToken(res.access_token);
      set({
        token: res.access_token,
        user: userSession,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
      return true;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Invalid credentials';
      set({ isLoading: false, error: msg });
      return false;
    }
  },

  logout: () => {
    clearStoredToken();
    set({ token: null, user: null, isAuthenticated: false, isLoading: false, error: null });
  },
}));
