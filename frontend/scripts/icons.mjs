// Génère src/icons.css : police Lucide (woff2 seul) et classes `icon-<nom>` des icônes utilisées.
// Ajouter le nom ci-dessous puis `node scripts/icons.mjs` ; un test Vitest signale les oublis.
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const ICONS = [
  'arrow-down', 'arrow-left', 'arrow-right', 'arrow-up', 'check', 'chevron-left', 'circle-alert',
  'circle-check', 'circle-help', 'circle-play', 'circle-stop', 'clock', 'cloud-upload', 'credit-card', 'download', 'external-link',
  'eye', 'eye-off', 'folder-open', 'image', 'image-plus', 'info', 'key-round', 'loader-circle', 'log-in',
  'log-out', 'mail', 'map', 'pause', 'pencil', 'play', 'plus', 'power', 'refresh-cw', 'save', 'search', 'send', 'settings', 'shirt', 'sparkles',
  'trash-2', 'triangle-alert', 'undo-2', 'upload', 'wifi-off', 'x',
]

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const codepoints = JSON.parse(
  readFileSync(join(root, 'node_modules/lucide-static/font/codepoints.json'), 'utf8'),
)
const rules = ICONS.map((name) => {
  const code = codepoints[name]
  if (code === undefined) throw new Error(`Icône Lucide inconnue : ${name}`)
  return `.icon-${name}::before { content: "\\${code.toString(16)}"; }`
})

writeFileSync(
  join(root, 'src/icons.css'),
  `/* Généré par scripts/icons.mjs — ne pas modifier à la main. Icônes Lucide (ISC). */
@font-face {
  font-family: 'lucide';
  src: url('../node_modules/lucide-static/font/lucide.woff2') format('woff2');
  font-display: block;
}

[class^='icon-'],
[class*=' icon-'] {
  font-family: 'lucide' !important;
  font-style: normal;
  font-weight: normal;
  line-height: 1;
  display: inline-block;
  -webkit-font-smoothing: antialiased;
}

.icon-spin {
  animation: icon-spin 1s linear infinite;
}

@keyframes icon-spin {
  to {
    transform: rotate(360deg);
  }
}

${rules.join('\n')}
`,
)
console.log(`src/icons.css : ${ICONS.length} icônes`)
