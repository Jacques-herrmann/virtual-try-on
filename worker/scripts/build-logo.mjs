// Recopie brand/logo.svg (en-tête des pages) et brand/app-icon.svg (favicon) dans src/logo.generated.ts.
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

const icon = readFileSync(path.join(root, "..", "..", "brand", "app-icon.svg"), "utf8").trim();

writeFileSync(
  target,
  `// Généré par scripts/build-logo.mjs depuis brand/logo.svg et brand/app-icon.svg — ne pas modifier à la main.\n` +
    `export const LOGO_SVG = ${JSON.stringify(svg)};\n` +
    `export const ICON_SVG = ${JSON.stringify(icon)};\n`,
);
console.log("src/logo.generated.ts");
