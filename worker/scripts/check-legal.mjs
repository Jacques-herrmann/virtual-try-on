// Avant le déploiement : signale les informations de l'éditeur encore « à compléter »
// dans src/site/legal.ts (PUBLISHER). Simple avertissement, le déploiement continue.
import { readFileSync } from "node:fs";
import path from "node:path";

const source = readFileSync(path.join(import.meta.dirname, "..", "src", "site", "legal.ts"), "utf8");
const block = source.match(/export const PUBLISHER: Publisher = \{([\s\S]*?)\};/);
if (!block) {
  console.warn("⚠ check-legal : PUBLISHER introuvable dans src/site/legal.ts.");
  process.exit(0);
}
const missing = [...block[1].matchAll(/(\w+):\s*TO_FILL/g)].map((m) => m[1]);
if (missing.length) {
  console.warn(
    `\n⚠ Pages légales : ${missing.join(", ")} encore « à compléter » (PUBLISHER dans src/site/legal.ts).\n`,
  );
}
