/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = { ...loadEnv(mode, process.cwd(), ''), ...process.env }

  return {
    plugins: [react()],
    // Testes (Vitest): npm test
    test: {
      environment: 'jsdom',
      include: ['src/**/*.test.{ts,tsx}'],
      setupFiles: ['src/test/setup.ts'],
    },
    server: {
      host: true,
      port: 5173,
      // Em Docker no Windows o file watcher nativo não funciona em bind mounts
      watch: env.VITE_USE_POLLING === 'true' ? { usePolling: true, interval: 300 } : undefined,
      proxy: {
        '/api': {
          // Local: http://localhost:8000 | Docker: http://backend:8000
          target: env.VITE_PROXY_TARGET ?? 'http://localhost:8000',
          changeOrigin: true,
          // Envia X-Forwarded-For: o backend usa o IP real no limite de tentativas de login
          xfwd: true,
          // WebSocket da subscription GraphQL (/api/graphql)
          ws: true,
        },
      },
    },
  }
})
