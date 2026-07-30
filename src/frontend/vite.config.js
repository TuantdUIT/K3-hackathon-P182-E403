import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Chạy dev không cần đặt VITE_API_URL: cứ gọi cùng origin là được.
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/agent': { target: 'http://localhost:8000', changeOrigin: true, ws: false },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
});
