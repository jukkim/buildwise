import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-three": ["three", "@react-three/fiber", "@react-three/drei"],
          "vendor-charts": ["recharts"],
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          "vendor-pdf": ["jspdf", "jspdf-autotable", "html2canvas"],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8001",
        changeOrigin: true,
        proxyTimeout: 60000,
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test-setup.ts",
    css: false,
  },
});
