import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: '/static/ketcher/',
  define: {
    global: 'globalThis',
  },
  build: {
    outDir: '../static/ketcher',
    emptyOutDir: true,
    commonjsOptions: {
      include: [/node_modules/],
      transformMixedEsModules: true,
    },
  },
  resolve: {
    dedupe: ['react', 'react-dom'],
  },
});
