import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// Tailwind v4 integrates through the dedicated Vite plugin — no PostCSS config.
export default defineConfig({
  plugins: [react(), tailwindcss()],
});
