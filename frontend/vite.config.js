import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In development, /api and /health are forwarded to the FastAPI server (including WebSockets),
// so the frontend can use relative URLs and no CORS setup is needed locally.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', ws: true, changeOrigin: true },
      '/health': 'http://127.0.0.1:8000',
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
    css: false,
  },
});
