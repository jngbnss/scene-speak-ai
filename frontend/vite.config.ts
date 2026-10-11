import { createReadStream, existsSync } from "node:fs";
import { extname, join, normalize } from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

// Ports can be changed when other local projects already use the defaults:
//   BACKEND_PORT=8010 FRONTEND_PORT=5183 npm run dev
const backend = `127.0.0.1:${process.env.BACKEND_PORT ?? "8000"}`;

const VAD_TYPES: Record<string, string> = {
  ".mjs": "text/javascript",
  ".js": "text/javascript",
  ".wasm": "application/wasm",
  ".onnx": "application/octet-stream",
};

/**
 * onnxruntime-web loads /vad/ort-wasm-simd-threaded.mjs with a dynamic import(). The dev
 * server refuses to import files from public/ as modules (500), which broke the
 * microphone under `npm run dev` only. Serve those files as plain static files instead.
 */
function serveVadAssets(): Plugin {
  const root = join(__dirname, "public", "vad");
  return {
    name: "serve-vad-assets",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const path = req.url?.split("?")[0] ?? "";
        if (!path.startsWith("/vad/")) return next();
        const file = normalize(join(root, path.slice("/vad/".length)));
        if (!file.startsWith(root) || !existsSync(file)) return next();
        res.setHeader("Content-Type", VAD_TYPES[extname(file)] ?? "application/octet-stream");
        createReadStream(file).pipe(res);
      });
    },
  };
}

export default defineConfig({
  plugins: [serveVadAssets(), react()],
  // three.js alone is about 500 kB; it sits in its own chunk, loaded when the street opens.
  build: { chunkSizeWarningLimit: 700 },
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
