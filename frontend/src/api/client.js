import axios from "axios";

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

export const apiClient = axios.create({
  baseURL: configuredBaseUrl || "/api/v1",
  timeout: 15000,
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("intellibank.accessToken");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("intellibank.accessToken");
      localStorage.removeItem("intellibank.refreshToken");
      window.dispatchEvent(new Event("intellibank:unauthorized"));
    }
    return Promise.reject(error);
  },
);

export function apiErrorMessage(error) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join(", ");
  if (error?.code === "ERR_NETWORK" || error?.message === "Network Error") {
    return "Could not reach the IntelliBank API. Start the FastAPI backend and PostgreSQL, then verify the frontend API proxy configuration.";
  }
  if (error?.code === "ECONNABORTED") {
    return "The IntelliBank API request timed out. Check that the backend and database are responding.";
  }
  return error?.message || "The request could not be completed.";
}
