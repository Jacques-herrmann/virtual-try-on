import { escapeHtml } from "../http";
import { ICON_SVG, LOGO_SVG } from "../logo.generated";

const NAV = [
  ["/#etapes", "Comment ça marche"],
  ["/#exemples", "Exemples"],
  ["/#tarif", "Tarif"],
  ["/#questions", "Questions"],
  ["/aide", "Aide"],
] as const;

// Icône « menu » de Lucide (ISC).
const MENU_ICON = `<svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>`;

// Couleurs Kaloé (brand/tokens.json) ; texte prune sur les boutons abricot (5,3:1).
const STYLE = `
:root { color-scheme: light dark; --fg:#2E1F2B; --bg:#FBF7F2; --muted:#6E6058; --link:#AD4A24; --accent:#E8774A; --on-accent:#2E1F2B; --card:#fff; --border:#E9DFD4; --soft:#FDE8DC; --header:rgba(251,247,242,.88); }
@media (prefers-color-scheme: dark) { :root { --fg:#FBF7F2; --bg:#1E1520; --muted:#B5A595; --link:#F5AC86; --card:#2E1F2B; --border:#3D3331; --soft:#3D180C; --header:rgba(30,21,32,.88); } }
* { box-sizing: border-box; }
html { scroll-behavior: smooth; scroll-padding-top: 80px; }
body { margin:0; font:16px/1.6 "Plus Jakarta Sans","Segoe UI",system-ui,-apple-system,sans-serif; color:var(--fg); background:var(--bg); }
.wrap { max-width: 1080px; margin: 0 auto; padding: 0 16px; }
main.narrow { max-width: 720px; margin: 0 auto; padding: 40px 16px 64px; }
.site-header { position: sticky; top: 0; z-index: 10; background: var(--header); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border-bottom: 1px solid var(--border); }
.site-header .wrap { display:flex; align-items:center; gap: 24px; height: 64px; }
.brand { display:inline-flex; color: var(--fg); }
.logo { display:block; height: 28px; width: auto; }
.nav { display:flex; gap: 22px; margin-left: auto; }
.nav a, .menu nav a { color: var(--fg); font-weight: 600; text-decoration: none; font-size: .95rem; }
.nav a:hover, .menu nav a:hover { color: var(--link); }
.menu { display:none; margin-left: auto; position: relative; }
.menu summary { list-style: none; cursor: pointer; display:flex; padding: 8px; border-radius: 10px; border: 1px solid var(--border); }
.menu summary::-webkit-details-marker { display:none; }
.menu nav { position:absolute; right:0; top: calc(100% + 8px); min-width: 230px; display:flex; flex-direction:column; gap: 4px; padding: 10px; background: var(--card); border:1px solid var(--border); border-radius: 14px; box-shadow: 0 12px 32px rgba(46,31,43,.16); }
.menu nav a { padding: 8px 10px; border-radius: 8px; }
.menu nav .button { text-align:center; margin-top: 6px; }
@media (max-width: 760px) { .nav, .site-header .header-cta { display:none; } .menu { display:block; } }
h1 { font-size: 1.75rem; line-height:1.2; letter-spacing: -0.02em; margin: 0 0 16px; }
h2 { font-size: 1.15rem; margin: 28px 0 8px; }
.muted { color: var(--muted); }
.card { background: var(--card); border:1px solid var(--border); border-radius: 18px; padding: 22px; margin: 20px 0; box-shadow: 0 2px 8px rgba(46,31,43,.05); }
.key { font: 600 1.25rem/1.4 ui-monospace,Consolas,monospace; letter-spacing: .04em; word-break: break-all; background: var(--soft); padding: 10px 14px; border-radius: 12px; }
a { color: var(--link); font-weight: 600; }
.button { display:inline-block; background: var(--accent); color: var(--on-accent); text-decoration:none; font-weight:700; padding: 12px 22px; border-radius: 12px; border:1.5px solid var(--accent); font-size:1rem; cursor:pointer; }
.button.secondary { background: transparent; color: var(--fg); border-color: var(--border); }
.button.small { padding: 8px 16px; font-size: .95rem; }
input[type=email] { width:100%; padding: 12px 14px; font-size:1rem; border:1.5px solid var(--border); border-radius: 12px; background: var(--card); color: var(--fg); margin: 8px 0 16px; }
.site-footer { border-top: 1px solid var(--border); padding: 28px 0 40px; font-size: .9rem; color: var(--muted); }
.site-footer nav { display:flex; flex-wrap: wrap; gap: 8px 20px; margin-bottom: 10px; }
.site-footer a { color: var(--muted); font-weight: 600; text-decoration: none; }
.site-footer a:hover { color: var(--link); }
.todo { background: var(--soft); color: var(--link); padding: 0 6px; border-radius: 6px; font-weight: 700; }
img, video { max-width: 100%; height: auto; }
`;

function header(): string {
  const links = NAV.map(([href, label]) => `<a href="${href}">${label}</a>`).join("");
  return `<header class="site-header"><div class="wrap">
<a class="brand" href="/" aria-label="Kaloé, accueil">${LOGO_SVG}</a>
<nav class="nav" aria-label="Menu principal">${links}</nav>
<a class="button small header-cta" href="/essai">Essayer 7 jours</a>
<details class="menu"><summary aria-label="Menu">${MENU_ICON}</summary>
<nav aria-label="Menu principal">${links}<a class="button small" href="/essai">Essayer 7 jours</a></nav>
</details>
</div></header>`;
}

function footer(): string {
  return `<footer class="site-footer"><div class="wrap">
<nav aria-label="Liens utiles">
<a href="/aide">Aide</a><a href="/retrouver">Retrouver ma clé</a><a href="mailto:contact@kaloe.fr">Contact</a>
<a href="/mentions-legales">Mentions légales</a><a href="/cgv">CGV</a><a href="/confidentialite">Confidentialité</a>
</nav>
<div>© ${new Date().getUTCFullYear()} Kaloé</div>
</div></footer>`;
}

export interface PageOptions {
  /** Page pleine largeur (l'accueil gère ses propres conteneurs `.wrap`). */
  wide?: boolean;
  /** Styles propres à la page, ajoutés après les styles communs. */
  css?: string;
  description?: string;
}

/** Gabarit commun : `body` est du HTML déjà échappé. */
export function htmlPage(title: string, body: string, status = 200, options: PageOptions = {}): Response {
  const description = options.description
    ? `\n<meta name="description" content="${escapeHtml(options.description)}">`
    : "";
  const main = options.wide ? `<main>${body}</main>` : `<main class="narrow">${body}</main>`;
  const html = `<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(title)} · Kaloé</title>${description}
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,${encodeURIComponent(ICON_SVG)}">
<style>${STYLE}${options.css ?? ""}</style>
</head>
<body>
${header()}
${main}
${footer()}
</body>
</html>`;
  return new Response(html, {
    status,
    headers: {
      "content-type": "text/html; charset=utf-8",
      "x-content-type-options": "nosniff",
      "referrer-policy": "no-referrer",
    },
  });
}

export function errorPage(status: number, message: string): Response {
  return htmlPage(
    "Oups",
    `<h1>Oups…</h1><p>${escapeHtml(message)}</p><p><a href="/">Revenir à l'accueil</a></p>`,
    status,
  );
}
