/**
 * Centralized API client for the Agri-Agent backend.
 *
 * Handles:
 *  - JWT Bearer token injection on every request
 *  - Token persistence in localStorage
 *  - Automatic 401 → logout flow
 *  - Typed response parsing
 *
 * Usage:
 *   import { apiClient } from '../api/client';
 *   const stats = await apiClient.get<AggregateStats>('/api/v1/stats');
 */
import { API_BASE } from '../constants';

// ---------------------------------------------------------------------------
// Token storage
// ---------------------------------------------------------------------------
const TOKEN_KEY = 'agri_access_token';

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// ---------------------------------------------------------------------------
// Auth API
// ---------------------------------------------------------------------------
export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

/**
 * Exchange username + password for a JWT token.
 * Stores the token automatically on success.
 */
export async function login(username: string, password: string): Promise<LoginResponse> {
  const form = new URLSearchParams({ username, password });
  const res = await fetch(`${API_BASE}/api/v1/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form.toString(),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? 'Login failed');
  }

  const data: LoginResponse = await res.json();
  setStoredToken(data.access_token);
  return data;
}

export function logout(): void {
  clearStoredToken();
  // Redirect to login page if routing is added
  window.location.reload();
}

// ---------------------------------------------------------------------------
// Generic HTTP client with auto-auth
// ---------------------------------------------------------------------------
type RequestOptions = Omit<RequestInit, 'body'> & { body?: unknown };

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const token = getStoredToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    body: options.body != null ? JSON.stringify(options.body) : undefined,
  });

  // Auto-logout on 401 (token expired / invalid)
  if (res.status === 401) {
    clearStoredToken();
    throw new Error('Session expired. Please log in again.');
  }

  if (res.status === 403) {
    throw new Error('You do not have permission to perform this action.');
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `Request failed: ${res.status}`);
  }

  return res.json() as Promise<T>;
}

/**
 * SSE streaming request with Bearer token injection.
 * Returns the raw Response for the caller to consume via ReadableStream.
 */
export async function streamRequest(path: string, body: unknown): Promise<Response> {
  const token = getStoredToken();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });

  if (res.status === 401) {
    clearStoredToken();
    throw new Error('Session expired. Please log in again.');
  }
  if (!res.ok) throw new Error(`Stream request failed: ${res.status}`);
  return res;
}

// ---------------------------------------------------------------------------
// Typed API surface
// ---------------------------------------------------------------------------
export const apiClient = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) => request<T>(path, { method: 'POST', body }),
  put: <T>(path: string, body: unknown) => request<T>(path, { method: 'PUT', body }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};
