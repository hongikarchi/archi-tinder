import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // PERF-FE-1: keep React + router in one stable vendor chunk. It rarely
        // changes between deploys, so returning visitors keep it cached while
        // the (frequently changing) app entry chunk re-downloads. Vite emits a
        // modulepreload hint for it, so it loads in parallel with the entry.
        manualChunks(id) {
          if (/node_modules\/(react|react-dom|react-router|react-router-dom|scheduler|cookie|set-cookie-parser)\//.test(id)) {
            return 'vendor-react'
          }
        },
      },
    },
  },
  server: {
    port: 5174,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/media': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
})
