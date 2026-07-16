import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    // Proxy only used in development (when VITE_API_URL is not set)
    proxy: {
      '/api': {
        target: process.env.API_PROXY_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: (process.env.API_PROXY_TARGET ?? 'http://localhost:8000').replace('http', 'ws'),
        ws: true,
      },
    },
  },
  // Ensure environment variables are properly typed
  define: {
    __APP_VERSION__: JSON.stringify(process.env.npm_package_version),
  },
})
