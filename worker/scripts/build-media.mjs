// Recopie la vidéo du tutoriel et l'exemple du jean dans public/media (servis tels quels par
// Cloudflare), et l'annonce de l'exemple dans src/site/example.generated.ts.
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

const root = path.join(import.meta.dirname, "..", "..");
const media = path.join(import.meta.dirname, "..", "public", "media");
const tutorial = path.join(root, "tools", "tutorial");

const RECORD = "lancer `vto-tutorial record` (après `npm run build` du front)";
const CAPTURE = "lancer `vto-tutorial capture`";

const files = [
  [path.join(root, "frontend", "public", "tutorial", "kaloe.mp4"), "kaloe.mp4", RECORD],
  [path.join(root, "frontend", "public", "tutorial", "kaloe.vtt"), "kaloe.vtt", RECORD],
  [path.join(root, "frontend", "public", "tutorial", "kaloe.jpg"), "kaloe.jpg", RECORD],
  [path.join(tutorial, "demo", "article-01.jpg"), "exemple-photo.jpg", CAPTURE],
  [path.join(tutorial, "capture", "images", "3a995f62fbd89082.jpg"), "exemple-cintre.jpg", CAPTURE],
  [path.join(tutorial, "capture", "images", "6a96f3ea2f114ff0.jpg"), "exemple-mannequin.jpg", CAPTURE],
];
const listing = path.join(tutorial, "capture", "listing.json");

for (const [source, , fix] of [...files, [listing, "", CAPTURE]]) {
  if (!existsSync(source)) {
    console.error(`${path.relative(root, source)} introuvable : ${fix}.`);
    process.exit(1);
  }
}

mkdirSync(media, { recursive: true });
for (const [source, name] of files) copyFileSync(source, path.join(media, name));

const data = JSON.parse(readFileSync(listing, "utf8"));
const example = {
  title: data.title,
  brand: data.brand,
  size: data.size,
  condition: data.condition,
  price: data.price,
  // La suite de la description contient la signature personnelle du vendeur.
  intro: data.description.split("\n\n")[0].trim(),
};
const site = path.join(import.meta.dirname, "..", "src", "site");
mkdirSync(site, { recursive: true });
writeFileSync(
  path.join(site, "example.generated.ts"),
  `// Généré par scripts/build-media.mjs depuis tools/tutorial/capture/listing.json — ne pas modifier à la main.\n` +
    `export const EXAMPLE = ${JSON.stringify(example, null, 2)};\n`,
);
console.log("public/media, src/site/example.generated.ts");
