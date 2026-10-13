import { lookupLicense, UNKNOWN_KEY_MESSAGE } from "./activation";
import { AIDE_HTML } from "./aide.generated";
import { sendLicenseEmail } from "./email";
import type { Env } from "./env";
import { escapeHtml, nowSeconds } from "./http";
import { ICON_SVG, LOGO_SVG } from "./logo.generated";
import { getLicenseByEmail, isValidStatus, type License } from "./licenses";
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

// Couleurs Kaloé (brand/tokens.json) ; texte prune sur les boutons abricot (5,3:1).
const STYLE = `
:root { color-scheme: light dark; --fg:#2E1F2B; --bg:#FBF7F2; --muted:#6E6058; --link:#AD4A24; --accent:#E8774A; --on-accent:#2E1F2B; --card:#fff; --border:#E9DFD4; --soft:#FDE8DC; }
@media (prefers-color-scheme: dark) { :root { --fg:#FBF7F2; --bg:#1E1520; --muted:#B5A595; --link:#F5AC86; --card:#2E1F2B; --border:#3D3331; --soft:#3D180C; } }
* { box-sizing: border-box; }
body { margin:0; font:16px/1.6 "Plus Jakarta Sans","Segoe UI",system-ui,-apple-system,sans-serif; color:var(--fg); background:var(--bg); }
main { max-width: 640px; margin: 0 auto; padding: 28px 16px 64px; }
.brand { display:inline-block; color: var(--fg); margin-bottom: 32px; }
.logo { display:block; height: 30px; width: auto; }
h1 { font-size: 1.75rem; line-height:1.2; letter-spacing: -0.02em; margin: 0 0 16px; }
h2 { font-size: 1.15rem; margin: 28px 0 8px; }
p, li { color: var(--fg); }
.muted { color: var(--muted); }
.card { background: var(--card); border:1px solid var(--border); border-radius: 18px; padding: 22px; margin: 20px 0; box-shadow: 0 2px 8px rgba(46,31,43,.05); }
.key { font: 600 1.25rem/1.4 ui-monospace,Consolas,monospace; letter-spacing: .04em; word-break: break-all; background: var(--soft); padding: 10px 14px; border-radius: 12px; }
a { color: var(--link); font-weight: 600; }
.button { display:inline-block; background: var(--accent); color: var(--on-accent); text-decoration:none; font-weight:700; padding: 12px 22px; border-radius: 12px; border:0; font-size:1rem; cursor:pointer; }
input[type=email] { width:100%; padding: 12px 14px; font-size:1rem; border:1.5px solid var(--border); border-radius: 12px; background: var(--card); color: var(--fg); margin: 8px 0 16px; }
footer { margin-top: 48px; padding-top: 16px; border-top: 1px solid var(--border); font-size: .9rem; color: var(--muted); }
img { max-width: 100%; }
`;

/** Gabarit commun : `body` est du HTML déjà échappé. */
export function htmlPage(title: string, body: string, status = 200): Response {
  const html = `<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(title)} · Kaloé</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,${encodeURIComponent(ICON_SVG)}">
<style>${STYLE}</style>
</head>
<body>
<main>
<a class="brand" href="/" aria-label="Kaloé, accueil">${LOGO_SVG}</a>
${body}
<footer><a href="/">Kaloé</a> · <a href="/aide">Aide</a> · <a href="/retrouver">Retrouver ma clé</a></footer>
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
    `<h1>Tes vêtements, portés et prêts à vendre.</h1>
<p>Ajoute une photo de ton vêtement : Kaloé crée des photos portées, rédige l'annonce et prépare le brouillon sur Vinted. Tu relis, tu valides, c'est en ligne. Une application Windows, ta clé Gemini, tes décors.</p>
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

/** `/renouveler?cle=` : reprise d'un abonnement terminé, sur le même client Stripe (même clé). */
export async function renewPage(url: URL, env: Env): Promise<Response> {
  const license = await lookupLicense(env, url.searchParams.get("cle") ?? "", nowSeconds());
  if (!license) return renewUnknownKey();
  if (isValidStatus(license.status)) return renewStillRunning();
  return htmlPage(
    "Reprendre mon abonnement",
    `<h1>Reprendre mon abonnement</h1>
<p>Ton abonnement est terminé. Reprends-le pour générer et envoyer à nouveau sur Vinted : tu gardes la même clé, rien à changer dans l'application.</p>
<form method="post" action="/renouveler">
  <input type="hidden" name="cle" value="${escapeHtml(license.key)}">
  <button class="button" type="submit">Reprendre mon abonnement</button>
</form>
<p class="muted">Le paiement se fait sur la page sécurisée de Stripe.</p>`,
  );
}

export async function handleRenew(request: Request, env: Env): Promise<Response> {
  let key = "";
  try {
    key = String((await request.formData()).get("cle") ?? "");
  } catch {
    // Formulaire illisible : traité comme une clé vide.
  }
  const license = await lookupLicense(env, key, nowSeconds());
  if (!license?.stripe_customer) return renewUnknownKey();
  if (isValidStatus(license.status)) return renewStillRunning();

  const price = env.STRIPE_PRICE_IDS.split(",")[0]!.trim();
  try {
    const res = await stripeApi(env, "/checkout/sessions", {
      mode: "subscription",
      customer: license.stripe_customer,
      "line_items[0][price]": price,
      "line_items[0][quantity]": "1",
      success_url: `${env.PUBLIC_BASE_URL}/merci?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${env.PUBLIC_BASE_URL}/renouveler?cle=${encodeURIComponent(license.key)}`,
      allow_promotion_codes: "true",
    });
    if (res.ok) {
      const { url } = (await res.json()) as { url: string };
      return Response.redirect(url, 303);
    }
    console.error("stripe: session de réabonnement refusée", res.status, await res.text());
  } catch (e) {
    console.error("stripe: injoignable", e);
  }
  return errorPage(502, "Le paiement est momentanément indisponible. Réessaie dans quelques minutes.");
}

function renewUnknownKey(): Response {
  return htmlPage(
    "Clé inconnue",
    `<h1>Clé inconnue</h1>
<p>${escapeHtml(UNKNOWN_KEY_MESSAGE)}</p>
<p><a href="/retrouver">Retrouver ma clé</a></p>`,
    404,
  );
}

function renewStillRunning(): Response {
  return htmlPage(
    "Abonnement actif",
    `<h1>Ton abonnement est déjà actif</h1>
<p>Rien à faire : tu peux continuer à utiliser l'application. Pour changer de carte ou voir tes factures, utilise « Gérer mon abonnement » dans l'application.</p>
<p><a href="/">Revenir à l'accueil</a></p>`,
  );
}
