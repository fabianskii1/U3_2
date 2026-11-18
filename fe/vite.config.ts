import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { mockApi } from "./mock/server.ts";
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd());
  return {
    // 개발 서버와 E2E 서버의 의존성 최적화 결과가 서로 덮어쓰지 않도록 분리한다.
    cacheDir: env.VITE_CACHE_DIR ?? "node_modules/.vite-dev",
    plugins: [
      react(),
      tailwindcss(),
      ...(env.VITE_API_MODE === "remote" ? [] : [mockApi()]),
    ],
    server: {
      port: 5173,
      strictPort: true,
      proxy: env.VITE_API_MODE === "remote" ? { "/api": "http://127.0.0.1:8000" } : undefined,
    },
    preview: { port: 4173 },
    build: { chunkSizeWarningLimit: 750 },
  };
});
