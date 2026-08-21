import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// VirtualStudent Sandbox v6.0 frontend
// Dev server on port 4000, proxies /api to FastAPI backend on port 6668
export default defineConfig({
  plugins: [react()],
  server: {
    port: 4000,
    host: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:6668',
        changeOrigin: true,
      },
    },
  },
})
