import { defineConfig } from 'vite';
export default defineConfig({
  server: { proxy: { '/v1': 'http://127.0.0.1:8000', '/health': 'http://127.0.0.1:8000' } },
  build: { rollupOptions: { input: { main: 'index.html', chat: 'chat.html' } }, outDir: '../../services/api/platform_api/web', emptyOutDir: true },
});
