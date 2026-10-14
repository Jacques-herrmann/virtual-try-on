import { lookupLicense, UNKNOWN_KEY_MESSAGE } from "./activation";
import { AIDE_HTML } from "./aide.generated";
import { sendLicenseEmail } from "./email";
import type { Env } from "./env";
import { escapeHtml, nowSeconds } from "./http";
import { getLicenseByEmail, isValidStatus, type License } from "./licenses";
import {
  licenseFromSession,
  stripeApi,
  StripeUnavailable,
  type StripeCheckoutSession,
} from "./stripe";
import { errorPage, htmlPage } from "./site/layout";
import { toHex } from "./tokens";

/** Demandes « Retrouver ma clé » acceptées par adresse et par heure. */
const RECOVER_LIMIT = 3;
const SESSION_ID = /^cs_[A-Za-z0-9_]{1,200}$/;
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

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
