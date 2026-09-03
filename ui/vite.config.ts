import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Lets the dev server talk to the API without CORS preflight in the browser.
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
