import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Mini App build config: mobile-first, single bundle, no external CDNs.
export default defineConfig({
  plugins: [react()],
  build: {
    target: "es2018",
    outDir: "dist",
    sourcemap: false,
    rollupOptions: {
      output: { manualChunks: undefined },
    },
  },
  server: { host: true, port: 5173 },
});
