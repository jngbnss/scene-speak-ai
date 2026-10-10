// Copies the Silero VAD model, its AudioWorklet and the onnxruntime-web wasm files into
// public/vad so the app serves them itself (no CDN at runtime). Runs before dev/build.
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(root, "public", "vad");
const vad = join(root, "node_modules", "@ricky0123", "vad-web", "dist");
const ort = join(root, "node_modules", "onnxruntime-web", "dist");

const files = [
  [vad, "vad.worklet.bundle.min.js"],
  [vad, "silero_vad_v5.onnx"],
  [vad, "silero_vad_legacy.onnx"],
  [ort, "ort-wasm-simd-threaded.wasm"],
  [ort, "ort-wasm-simd-threaded.mjs"],
];

mkdirSync(out, { recursive: true });
for (const [dir, name] of files) {
  const src = join(dir, name);
  if (!existsSync(src)) {
    console.error(`copy-vad-assets: missing ${src}. Run npm install.`);
    process.exit(1);
  }
  copyFileSync(src, join(out, name));
}
console.log(`copy-vad-assets: ${files.length} files -> public/vad`);
