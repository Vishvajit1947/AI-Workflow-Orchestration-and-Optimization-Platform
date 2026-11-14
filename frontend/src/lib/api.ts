import axios from 'axios';

/**
 * Backend origin. Unset: the dev default. Empty string: same origin as the page
 * (production build behind the nginx reverse proxy).
 */
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

/** WebSocket origin matching the API (http -> ws, https -> wss; same origin when API_BASE_URL is empty). */
export const WS_BASE_URL = API_BASE_URL
  ? API_BASE_URL.replace(/^http/, 'ws')
  : `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`;

const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
  withCredentials: true, // Include cookies in requests
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);

    // Redirect to login on 401 Unauthorized (except if already on login page)
    if (error.response?.status === 401 && !window.location.pathname.startsWith('/login')) {
      window.location.href = '/login';
    }

    return Promise.reject(error);
  }
);

export default api;
