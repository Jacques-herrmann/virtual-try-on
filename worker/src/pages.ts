import { AIDE_HTML } from "./aide.generated";
import { sendLicenseEmail } from "./email";
import type { Env } from "./env";
import { escapeHtml, nowSeconds } from "./http";
import { getLicenseByEmail, type License } from "./licenses";
import {
  licenseFromSession,
  stripeApi,
  StripeUnavailable,
  type StripeCheckoutSession,
} from "./stripe";
import { toHex } from "./tokens";

/** Demandes « Retrouver ma clé » acceptées par adresse et par heure. */
const RECOVER_LIMIT = 3;
const SESSION_ID = /^cs_[A-Za-z0-9_]{1,200}$/;
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

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

export function homePage(env: Env): Response {
  return htmlPage(
    "Photos portées pour Vinted",
    `<h1>Virtual Try-On</h1>
<p>Des photos « portées » de tes vêtements et une annonce prête à relire, envoyées en brouillon sur Vinted. Une application Windows, ta clé Gemini, tes décors.</p>
<div class="card">
  <p><strong>7 jours d'essai</strong>, puis abonnement résiliable à tout moment.<br>
  <span class="muted">La carte est demandée au début de l'essai ; rien n'est prélevé avant la fin des 7 jours.</span></p>
  <p><a class="button" href="${escapeHtml(env.PAYMENT_LINK_URL)}">Essayer 7 jours</a></p>
</div>
<p>Déjà abonné ? <a href="/retrouver">Retrouver ma clé</a> · <a href="/aide">Aide à l'installation</a></p>`,
  );
}

export async function thanksPage(url: URL, env: Env): Promise<Response> {
  const id = url.searchParams.get("session_id") ?? "";
  if (!SESSION_ID.test(id)) return sessionNotFound();
  let session: (StripeCheckoutSession & { status?: string }) | null = null;
  try {
    const res = await stripeApi(env, `/checkout/sessions/${id}`);
    if (res.ok) session = (await res.json()) as StripeCheckoutSession & { status?: string };
    else console.error("stripe: session illisible", id, res.status);
  } catch (e) {
    console.error("stripe: injoignable", e);
  }
  if (!session || session.status !== "complete") return sessionNotFound();
  // Le webhook peut arriver après le retour du client : la licence est créée ici si besoin.
  let license: License | null = null;
  try {
    license = await licenseFromSession(env, session, nowSeconds());
  } catch (e) {
    if (!(e instanceof StripeUnavailable)) throw e;
  }
  if (!license) return sessionNotFound();
  return keyPage(env, license);
}

function keyPage(env: Env, license: License): Response {
  const download = `/telecharger?cle=${encodeURIComponent(license.key)}`;
  return htmlPage(
    "Merci",
    `<h1>Merci !</h1>
<p>Voici ta clé de licence. Elle t'a aussi été envoyée par e-mail${license.email ? ` (${escapeHtml(license.email)})` : ""}.</p>
<div class="card"><p class="key">${escapeHtml(license.key)}</p></div>
<ol>
  <li><a href="${escapeHtml(download)}">Télécharge l'application</a> et installe-la (<a href="/aide">aide</a>).</li>
  <li>Au premier lancement, colle ta clé.</li>
</ol>
<p class="muted">Ta clé fonctionne sur 2 PC. Garde-la précieusement.</p>`,
  );
}

function sessionNotFound(): Response {
  return htmlPage(
    "Paiement introuvable",
    `<h1>Paiement introuvable</h1>
<p>Nous ne retrouvons pas ce paiement. S'il vient d'avoir lieu, ta clé t'a été envoyée par e-mail.</p>
<p><a href="/retrouver">Retrouver ma clé</a></p>`,
    404,
  );
}

export function recoverForm(error?: string): Response {
  return htmlPage(
    "Retrouver ma clé",
    `<h1>Retrouver ma clé</h1>
<p>Indique l'adresse e-mail utilisée lors de l'achat : nous t'y renverrons ta clé de licence.</p>
<form method="post" action="/retrouver">
  <label for="email">Adresse e-mail</label>
  <input id="email" name="email" type="email" required autocomplete="email">
  ${error ? `<p role="alert"><strong>${escapeHtml(error)}</strong></p>` : ""}
  <button class="button" type="submit">Recevoir ma clé</button>
</form>`,
    error ? 400 : 200,
  );
}

export async function handleRecover(request: Request, env: Env): Promise<Response> {
  let email = "";
  try {
    email = String((await request.formData()).get("email") ?? "").trim().toLowerCase();
  } catch {
    // Formulaire illisible : traité comme une adresse vide.
  }
  if (!EMAIL.test(email) || email.length > 254) {
    return recoverForm("Cette adresse e-mail ne semble pas valide.");
  }

  // Même réponse que l'adresse soit connue ou non, et au plus 3 e-mails par heure.
  const now = nowSeconds();
  const hash = toHex(
    new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(email))),
  );
  const [, recent] = await env.DB.batch([
    env.DB.prepare("DELETE FROM recover_requests WHERE at < ?").bind(now - 86400),
    env.DB.prepare("SELECT COUNT(*) AS n FROM recover_requests WHERE ip_email_hash = ? AND at > ?").bind(
      hash,
      now - 3600,
    ),
    env.DB.prepare("INSERT INTO recover_requests (ip_email_hash, at) VALUES (?, ?)").bind(hash, now),
  ]);
  const count = (recent!.results[0] as { n: number }).n;
  if (count < RECOVER_LIMIT) {
    const license = await getLicenseByEmail(env.DB, email);
    if (license) await sendLicenseEmail(env, email, license.key);
  }
  return htmlPage(
    "Retrouver ma clé",
    `<h1>C'est noté</h1>
<p>Si une licence est associée à cette adresse, tu vas recevoir ta clé par e-mail dans quelques minutes. Pense à regarder dans les indésirables.</p>
<p><a href="/">Revenir à l'accueil</a></p>`,
  );
}

export function helpPage(): Response {
  return htmlPage("Aide à l'installation", AIDE_HTML);
}
