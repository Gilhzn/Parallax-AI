/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// /api and /media are proxied to the FastAPI dev server (make demo).
export default defineConfig({
  // Sub-path hosting (e.g. GitHub Pages serves at /Parallax-AI/).
  base: process.env.BASE_PATH || '/',
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/media': 'http://localhost:8000',
    },
  },
  build: {
    // gaussian-splats-3d + three are heavy; keep them in their own chunk.
    rollupOptions: {
      output: {
        manualChunks: {
          splats: ['@mkkellogg/gaussian-splats-3d', 'three'],
        },
      },
    },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
});
