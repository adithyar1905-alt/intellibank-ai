import { apiClient } from "../api/client.js";

export const authService = {
  login: (email, password, mfaCode) => {
    const body = new URLSearchParams({ username: email, password });
    if (mfaCode) body.set("mfa_code", mfaCode);
    return apiClient.post("/auth/login", body, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
  },
  me: () => apiClient.get("/auth/me"),
  logout: () => apiClient.post("/auth/logout"),
  roles: () => apiClient.get("/auth/roles"),
  mfaStatus: () => apiClient.get("/auth/mfa/status"),
  setupMfa: () => apiClient.post("/auth/mfa/setup"),
  confirmMfa: (code) => apiClient.post("/auth/mfa/confirm", { code }),
};
