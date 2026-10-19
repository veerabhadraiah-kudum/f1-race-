import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    cors: true,
    // @ts-ignore - vite 5.x supports boolean
    allowedHosts: true as any,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/ws': { target: 'ws://localhost:8000', ws: true, changeOrigin: true },
    },
    hmr: { clientPort: 443 },
  },
  preview: { host: '0.0.0.0', port: 5173, cors: true },
})
