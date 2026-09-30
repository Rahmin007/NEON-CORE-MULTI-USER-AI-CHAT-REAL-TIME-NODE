/**
 * Small fetch wrapper for the FastAPI backend.
 * VITE_API_URL points at the deployed API; in development it is empty and Vite proxies /api.
 */
export const API_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
const TOKEN_KEY = 'neon_core_token';

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (token) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

/** Turns FastAPI error bodies (string or validation list) into one readable sentence. */
export function errorMessage(body, status) {
  const detail = body?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((item) => {
        const field = item.loc?.[item.loc.length - 1];
        const msg = String(item.msg || '').replace(/^Value error, /, '');
        return field && field !== 'body' ? `${field}: ${msg}` : msg;
      })
      .join(' ');
  }
  if (status >= 500) return 'The server had a problem. Please try again.';
  return `Request failed (${status}).`;
}

export async function api(path, { method = 'GET', body, form, auth = true } = {}) {
  const headers = {};
  const token = tokenStore.get();
  if (auth && token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (form) {
    payload = new URLSearchParams(form);
    headers['Content-Type'] = 'application/x-www-form-urlencoded';
  } else if (body !== undefined) {
    payload = JSON.stringify(body);
    headers['Content-Type'] = 'application/json';
  }

  let res;
  try {
    res = await fetch(`${API_URL}/api/v1${path}`, { method, headers, body: payload });
  } catch {
    throw new ApiError('Cannot reach the server. Check your connection or try again shortly.', 0);
  }
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }
  if (!res.ok) throw new ApiError(errorMessage(data, res.status), res.status);
  return data;
}

/** WebSocket URL for the chat, e.g. wss://api.example.com/api/v1/chat/ws?token=... */
export function socketUrl(token) {
  const base = API_URL || window.location.origin;
  const url = new URL(`${base}/api/v1/chat/ws`);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  url.searchParams.set('token', token);
  return url.toString();
}
