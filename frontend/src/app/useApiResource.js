import { useCallback, useEffect, useRef, useState } from "react";
import { apiErrorMessage } from "../api/client.js";
import { useAuth } from "./AuthContext.jsx";

export function useApiResource(loader, demoValue = []) {
  const { isDemo } = useAuth();
  const loaderRef = useRef(loader);
  const demoRef = useRef(demoValue);
  loaderRef.current = loader;
  demoRef.current = demoValue;
  const [data, setData] = useState(isDemo ? demoValue : null);
  const [loading, setLoading] = useState(!isDemo);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    if (isDemo) {
      setData(demoRef.current);
      setError("");
      setLoading(false);
      return demoRef.current;
    }
    setLoading(true);
    setError("");
    setData(null);
    try {
      const response = await loaderRef.current();
      const result = response?.data ?? response;
      setData(result);
      return result;
    } catch (requestError) {
      setData(null);
      setError(apiErrorMessage(requestError));
      throw requestError;
    } finally {
      setLoading(false);
    }
  }, [isDemo]);

  useEffect(() => {
    refresh().catch(() => {});
  }, [refresh]);

  return { data, setData, loading, error, refresh, isDemo };
}
