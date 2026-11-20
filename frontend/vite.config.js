import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000";

  return {
    plugins: [react()],
    server: {
      host: "127.0.0.1",
      proxy: {
        "/api": {
          target: apiProxyTarget,
          changeOrigin: true,
          configure(proxy) {
            proxy.on("error", (_error, _request, response) => {
              if (!response.headersSent) {
                response.writeHead(503, { "Content-Type": "application/json" });
              }
              response.end(JSON.stringify({
                detail: "IntelliBank API is unavailable. Start FastAPI and verify VITE_API_PROXY_TARGET.",
              }));
            });
          },
        },
      },
    },
  };
});
