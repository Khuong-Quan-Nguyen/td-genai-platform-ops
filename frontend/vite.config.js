import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Builds into ../static, which FastAPI serves. `base` must match the path the
// SPA is served from so asset URLs resolve in the container.
export default defineConfig({
  plugins: [react()],
  base: '/',
  build: {
    outDir: '../static',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
