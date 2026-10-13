import { escapeHtml } from "./http";

const STYLE = `
:root { color-scheme: light dark; --fg:#1d1d1f; --bg:#fafaf9; --muted:#6b6b70; --accent:#0d7a5f; --card:#fff; --border:#e4e4e7; }
@media (prefers-color-scheme: dark) { :root { --fg:#ececee; --bg:#141416; --muted:#a1a1aa; --accent:#3ccf9f; --card:#1e1e21; --border:#2e2e33; } }
* { box-sizing: border-box; }
body { margin:0; font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif; color:var(--fg); background:var(--bg); }
main { max-width: 640px; margin: 0 auto; padding: 32px 16px 64px; }
h1 { font-size: 1.6rem; line-height:1.25; margin: 0 0 16px; }
h2 { font-size: 1.15rem; margin: 28px 0 8px; }
p, li { color: var(--fg); }
.muted { color: var(--muted); }
.card { background: var(--card); border:1px solid var(--border); border-radius: 12px; padding: 20px; margin: 20px 0; }
.key { font: 600 1.25rem/1.4 ui-monospace,Consolas,monospace; letter-spacing: .04em; word-break: break-all; }
a { color: var(--accent); }
.button { display:inline-block; background: var(--accent); color:#fff; text-decoration:none; font-weight:600; padding: 12px 20px; border-radius: 10px; border:0; font-size:1rem; cursor:pointer; }
input[type=email] { width:100%; padding: 12px; font-size:1rem; border:1px solid var(--border); border-radius: 10px; background: var(--card); color: var(--fg); margin: 8px 0 16px; }
footer { margin-top: 40px; font-size: .9rem; color: var(--muted); }
img { max-width: 100%; }
`;

/** Gabarit commun : `body` est du HTML déjà échappé. */
export function htmlPage(title: string, body: string, status = 200): Response {
  const html = `<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(title)} · Virtual Try-On</title>
<style>${STYLE}</style>
</head>
<body>
<main>
${body}
<footer><a href="/">Virtual Try-On</a> · <a href="/aide">Aide</a> · <a href="/retrouver">Retrouver ma clé</a></footer>
</main>
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
