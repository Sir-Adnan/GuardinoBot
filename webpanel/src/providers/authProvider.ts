import type { AuthProvider } from "@refinedev/core";
import { api, TOKEN_KEY, REFRESH_KEY, USER_KEY } from "./axios";

// Telegram one-time-code login. Step 1 (request-code) is triggered from the
// login page; `login()` here performs step 2 (verify → store JWTs).
export const authProvider: AuthProvider = {
  login: async (params: any) => {
    const { identifier, code, init_data } = params ?? {};
    try {
      // Telegram Web App auto-login (signed initData) or OTP verify.
      const res = init_data
        ? await api.post("/auth/telegram", { init_data })
        : await api.post("/auth/verify", { identifier, code });
      localStorage.setItem(TOKEN_KEY, res.data.access_token);
      localStorage.setItem(REFRESH_KEY, res.data.refresh_token);
      localStorage.setItem(USER_KEY, JSON.stringify(res.data.user));
      return { success: true, redirectTo: "/" };
    } catch (e: any) {
      return {
        success: false,
        error: {
          name: "LoginError",
          message: e?.response?.data?.detail || "ورود ناموفق بود",
        },
      };
    }
  },
  logout: async () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
    return { success: true, redirectTo: "/login" };
  },
  check: async () => {
    if (localStorage.getItem(TOKEN_KEY)) return { authenticated: true };
    return { authenticated: false, redirectTo: "/login" };
  },
  onError: async (error) => {
    if (error?.response?.status === 401) {
      return { logout: true, redirectTo: "/login" };
    }
    return {};
  },
  getPermissions: async () => {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw).role : null;
  },
  getIdentity: async () => {
    const raw = localStorage.getItem(USER_KEY);
    if (raw) return JSON.parse(raw);
    try {
      const res = await api.get("/auth/me");
      localStorage.setItem(USER_KEY, JSON.stringify(res.data));
      return res.data;
    } catch {
      return null;
    }
  },
};
