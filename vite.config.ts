import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  build: {
    target: 'es2022',
    // Rapier ships its WebAssembly inlined as base64, so its chunk is large by design.
    chunkSizeWarningLimit: 4500,
    rollupOptions: {
      output: {
        manualChunks: {
          rapier: ['@dimforge/rapier3d-compat'],
          three: ['three'],
        },
      },
    },
  },
  server: {
    host: true,
  },
});
