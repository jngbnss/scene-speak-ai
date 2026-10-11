// Copies evals/results/*.json into public/reports with an index.json, so the /report page
// also works on GitHub Pages, where there is no backend. Runs before build.
import { copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = join(root, "..", "evals", "results");
const out = join(root, "public", "reports");
const KINDS = ["suite", "dialogue", "feedback", "asr"];

rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });
const index = [];
const names = existsSync(src) ? readdirSync(src).filter((n) => n.endsWith(".json")) : [];
for (const name of names.sort().reverse()) {
  let data;
  try {
    data = JSON.parse(readFileSync(join(src, name), "utf8"));
  } catch {
    continue;
  }
  copyFileSync(join(src, name), join(out, name));
  index.push({
    name,
    label: data.label ?? null,
    kind: data.kind ?? KINDS.find((k) => name.includes(`-${k}-`)) ?? "unknown",
    created_at: data.created_at ?? null,
    git_commit: data.git_commit ?? null,
  });
}
writeFileSync(join(out, "index.json"), JSON.stringify(index, null, 2));
console.log(`copy-reports: ${index.length} result files -> public/reports`);
