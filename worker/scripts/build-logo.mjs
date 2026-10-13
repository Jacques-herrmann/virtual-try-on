// Recopie brand/logo.svg dans src/logo.generated.ts pour l'en-tête des pages.
// Les lettres prennent `currentColor` : le logo suit le mode sombre de la page.
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

const root = import.meta.dirname;
const source = path.join(root, "..", "..", "brand", "logo.svg");
const target = path.join(root, "..", "src", "logo.generated.ts");

const svg = readFileSync(source, "utf8")
  .trim()
  .replace('fill="#2E1F2B"', 'fill="currentColor"')
  .replace("<svg ", '<svg class="logo" ');

writeFileSync(
  target,
  `// Généré par scripts/build-logo.mjs depuis brand/logo.svg — ne pas modifier à la main.\nexport const LOGO_SVG = ${JSON.stringify(svg)};\n`,
);
console.log("src/logo.generated.ts");
