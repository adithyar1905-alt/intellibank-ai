import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client.js";
import { authService } from "../services/auth.js";

const AuthContext = createContext(null);
const DEMO_USER = {
  id: "demo-admin",
  email: "admin@intellibank.ai",
  roles: ["Super Admin"],
  permissions: ["*"],
  is_active: true,
  is_verified: true,
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(DEMO_USER);
  const [isDemo, setIsDemo] = useState(!localStorage.getItem("intellibank.accessToken"));
  const [loading, setLoading] = useState(Boolean(localStorage.getItem("intellibank.accessToken")));

  useEffect(() => {
    const handleUnauthorized = () => {
      setUser(DEMO_USER);
      setIsDemo(true);
      setLoading(false);
    };
    window.addEventListener("intellibank:unauthorized", handleUnauthorized);
    if (localStorage.getItem("intellibank.accessToken")) {
      authService.me()
        .then(({ data }) => {
          setUser(data);
          setIsDemo(false);
        })
        .catch(() => {
          setUser(DEMO_USER);
          setIsDemo(true);
        })
        .finally(() => setLoading(false));
    }
    return () => window.removeEventListener("intellibank:unauthorized", handleUnauthorized);
  }, []);

  const value = useMemo(() => ({
    user,
    isDemo,
    loading,
    async login(email, password, mfaCode) {
      const { data } = await authService.login(email, password, mfaCode);
      localStorage.setItem("intellibank.accessToken", data.access_token);
      localStorage.setItem("intellibank.refreshToken", data.refresh_token);
      apiClient.defaults.headers.common.Authorization = `Bearer ${data.access_token}`;
      try {
        const profile = await authService.me();
        setUser(profile.data);
        setIsDemo(false);
        return profile.data;
      } catch (error) {
        localStorage.removeItem("intellibank.accessToken");
        localStorage.removeItem("intellibank.refreshToken");
        delete apiClient.defaults.headers.common.Authorization;
        throw error;
      }
    },
    async logout() {
      try {
        if (!isDemo && localStorage.getItem("intellibank.accessToken")) {
          await authService.logout();
        }
      } finally {
        localStorage.removeItem("intellibank.accessToken");
        localStorage.removeItem("intellibank.refreshToken");
        delete apiClient.defaults.headers.common.Authorization;
        setUser(DEMO_USER);
        setIsDemo(true);
      }
    },
  }), [user, isDemo, loading]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used within AuthProvider.");
  return value;
}
