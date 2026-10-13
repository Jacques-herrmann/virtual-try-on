import type { Env } from "./env";
import { escapeHtml } from "./http";

/** Envoie la clé de licence ; `false` (et un log) si Resend refuse ou ne répond pas. */
export async function sendLicenseEmail(env: Env, to: string, key: string): Promise<boolean> {
  const download = `${env.PUBLIC_BASE_URL}/telecharger?cle=${encodeURIComponent(key)}`;
  const help = `${env.PUBLIC_BASE_URL}/aide`;
  const text = [
    "Bonjour,",
    "",
    "Merci pour ton abonnement à Virtual Try-On !",
    "",
    `Ta clé de licence : ${key}`,
    "",
    `Télécharger l'application : ${download}`,
    `Aide à l'installation : ${help}`,
    "",
    "Au premier lancement, colle ta clé dans l'application. Elle fonctionne sur 2 PC.",
    "Garde cet e-mail : il te servira si tu réinstalles l'application.",
  ].join("\n");
  const html = `<p>Bonjour,</p>
<p>Merci pour ton abonnement à Virtual Try-On !</p>
<p>Ta clé de licence :<br><strong style="font-family:monospace;font-size:18px">${escapeHtml(key)}</strong></p>
<p><a href="${escapeHtml(download)}">Télécharger l'application</a> · <a href="${escapeHtml(help)}">Aide à l'installation</a></p>
<p>Au premier lancement, colle ta clé dans l'application. Elle fonctionne sur 2 PC.<br>
Garde cet e-mail : il te servira si tu réinstalles l'application.</p>`;

  try {
    const res = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        authorization: `Bearer ${env.RESEND_API_KEY}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        from: env.EMAIL_FROM,
        to: [to],
        subject: "Ta clé de licence Virtual Try-On",
        text,
        html,
      }),
    });
    if (!res.ok) {
      console.error("resend: envoi refusé", res.status, await res.text());
      return false;
    }
    return true;
  } catch (e) {
    console.error("resend: injoignable", e);
    return false;
  }
}
