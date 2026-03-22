import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Phase 3: run `scripts/brainstorm-api.sh` then `npm run dev:api`
      '/api/brainstorm': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/brainstorm/, '') || '/',
      },
    },
  },
})
