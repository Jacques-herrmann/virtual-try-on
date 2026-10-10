import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

const API = 'http://127.0.0.1:8765' // vto-app --dev

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  build: {
    // Servi par FastAPI (backend/src/vto/api/static), ignoré par git.
    outDir: '../backend/src/vto/api/static',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': { target: API, changeOrigin: true },
      '/files': { target: API, changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
  },
})
