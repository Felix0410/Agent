import { defineConfig } from 'vite';

// 本地开发时将健康检查和 API 请求转发给 FastAPI，避免在浏览器中保存密钥。
export default defineConfig({
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/health': 'http://127.0.0.1:8000',
      '/api': 'http://127.0.0.1:8000',
    },
  },
});
