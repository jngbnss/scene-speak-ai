import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Ports can be changed when other local projects already use the defaults:
//   BACKEND_PORT=8010 FRONTEND_PORT=5183 npm run dev
const backend = `127.0.0.1:${process.env.BACKEND_PORT ?? "8000"}`;

export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.FRONTEND_PORT ?? 5173),
    strictPort: true,
    proxy: {
      "/ws": { target: `ws://${backend}`, ws: true },
      "/health": `http://${backend}`,
      "/api": `http://${backend}`,
    },
  },
});
