import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/analyze': 'http://127.0.0.1:8001',
      '/tracks':  'http://127.0.0.1:8001',
      '/outputs': 'http://127.0.0.1:8001',
      '/jobs':    'http://127.0.0.1:8001',
    },
  },
})
