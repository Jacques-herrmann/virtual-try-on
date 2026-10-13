import type { Env } from "./env";
import { escapeHtml } from "./http";

/** Envoie la clé de licence ; `false` (et un log) si Resend refuse ou ne répond pas. */
export async function sendLicenseEmail(env: Env, to: string, key: string): Promise<boolean> {
  const download = `${env.PUBLIC_BASE_URL}/telecharger?cle=${encodeURIComponent(key)}`;
  const help = `${env.PUBLIC_BASE_URL}/aide`;
  const text = [
    "Bonjour,",
    "",
    "Merci pour ton abonnement à Wearo !",
    "",
    `Ta clé de licence : ${key}`,
    "",
    `Télécharger l'application : ${download}`,
    `Aide à l'installation : ${help}`,
    "",
    "Au premier lancement, colle ta clé dans l'application. Elle fonctionne sur 2 PC.",
    "Garde cet e-mail : il te servira si tu réinstalles l'application.",
  ].join("\n");
  // Styles en ligne (messageries) ; le nom en texte plutôt qu'en image, souvent bloquée.
  const html = `<div style="font-family:'Segoe UI',Arial,sans-serif;color:#2E1F2B;background:#FBF7F2;padding:24px">
<div style="max-width:560px;margin:0 auto;background:#ffffff;border:1px solid #E9DFD4;border-radius:18px;padding:28px">
<p style="margin:0 0 20px;font-size:26px;font-weight:800;letter-spacing:-0.5px">wear<span style="color:#E8774A">o</span></p>
<p>Bonjour,</p>
<p>Merci pour ton abonnement à Wearo !</p>
<p>Ta clé de licence :<br><strong style="display:inline-block;margin-top:6px;padding:8px 12px;background:#FDE8DC;border-radius:10px;font-family:Consolas,monospace;font-size:18px">${escapeHtml(key)}</strong></p>
<p style="margin:24px 0"><a href="${escapeHtml(download)}" style="display:inline-block;background:#E8774A;color:#2E1F2B;font-weight:700;text-decoration:none;padding:12px 22px;border-radius:12px">Télécharger l'application</a></p>
<p><a href="${escapeHtml(help)}" style="color:#AD4A24">Aide à l'installation</a></p>
<p style="color:#6E6058">Au premier lancement, colle ta clé dans l'application. Elle fonctionne sur 2 PC.<br>
Garde cet e-mail : il te servira si tu réinstalles l'application.</p>
</div></div>`;

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
        subject: "Ta clé de licence Wearo",
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
