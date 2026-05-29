import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Proxy all /api and /health requests to the FastAPI backend.
    // This eliminates CORS entirely during development — the browser
    // only ever talks to localhost:5173 (same origin).
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8888',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8888',
        changeOrigin: true,
      },
    },
  },
})
