import axios from "axios";

export const TOKEN_KEY = "gb_access";
export const REFRESH_KEY = "gb_refresh";
export const USER_KEY = "gb_user";

const BASE = import.meta.env.VITE_API_URL || "/api";

export const api = axios.create({ baseURL: BASE });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshing: Promise<string | null> | null = null;

async function doRefresh(): Promise<string | null> {
  const refresh = localStorage.getItem(REFRESH_KEY);
  if (!refresh) return null;
  try {
    // bare axios (not `api`) to avoid the interceptor loop
    const res = await axios.post(`${BASE}/auth/refresh`, { refresh_token: refresh });
    localStorage.setItem(TOKEN_KEY, res.data.access_token);
    localStorage.setItem(REFRESH_KEY, res.data.refresh_token);
    return res.data.access_token as string;
  } catch {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
    return null;
  }
}

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && original && !original._retry) {
      original._retry = true;
      if (!refreshing) refreshing = doRefresh();
      const token = await refreshing;
      refreshing = null;
      if (token) {
        original.headers.Authorization = `Bearer ${token}`;
        return api(original);
      }
    }
    return Promise.reject(error);
  },
);
