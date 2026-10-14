import type { Env } from "../env";
import { escapeHtml } from "../http";
import { EXAMPLE } from "./example.generated";
import { htmlPage } from "./layout";

// Icônes Lucide (ISC), en ligne : aucune police ni requête tierce.
const ICONS = {
  camera: `<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/>`,
  sparkles: `<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/>`,
  send: `<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>`,
  image: `<rect width="18" height="18" x="3" y="3" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>`,
  eye: `<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>`,
  lock: `<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>`,
  monitor: `<rect width="20" height="14" x="2" y="3" rx="2"/><path d="M8 21h8M12 17v4"/>`,
  check: `<path d="M20 6 9 17l-5-5"/>`,
  download: `<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>`,
  arrow: `<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>`,
};

function icon(name: keyof typeof ICONS, size = 24): string {
  return `<svg class="ico" aria-hidden="true" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`;
}

const CSS = `
section { padding: 72px 0; }
.eyebrow { display:inline-block; font-size:.8rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color: var(--link); margin-bottom: 12px; }
.section-title { font-size: clamp(1.6rem, 3.2vw, 2.2rem); line-height:1.15; letter-spacing:-.02em; margin:0 0 12px; }
.section-lead { color: var(--muted); max-width: 620px; margin: 0 0 40px; font-size: 1.05rem; }
.center { text-align:center; }
.center .section-lead { margin-left:auto; margin-right:auto; }
.hero { padding: 64px 0 72px; background: radial-gradient(1100px 500px at 85% -10%, var(--soft), transparent 70%); }
.hero .wrap { display:grid; grid-template-columns: 5fr 6fr; gap: 48px; align-items:center; }
.hero h1 { font-size: clamp(2.1rem, 4.6vw, 3.3rem); line-height:1.05; letter-spacing:-.03em; margin: 0 0 20px; }
.hero h1 em { font-style: normal; color: var(--link); }
.hero p.lead { font-size: 1.12rem; color: var(--muted); margin: 0 0 28px; }
.actions { display:flex; flex-wrap:wrap; gap: 12px; }
.actions .button { display:inline-flex; align-items:center; gap: 8px; }
.fine { margin-top: 16px; font-size:.9rem; color: var(--muted); }
.video { border-radius: 20px; overflow:hidden; border:1px solid var(--border); box-shadow: 0 24px 60px rgba(46,31,43,.18); background:#000; aspect-ratio: 16 / 10; }
.video video { display:block; width:100%; height:100%; }
.steps { display:grid; grid-template-columns: repeat(3, 1fr); gap: 20px; counter-reset: step; }
.step { background: var(--card); border:1px solid var(--border); border-radius: 18px; padding: 26px; position:relative; }
.step::before { counter-increment: step; content: counter(step); position:absolute; top: 22px; right: 24px; font-size: 2.6rem; font-weight: 800; line-height:1; color: var(--soft); }
.badge { display:inline-flex; align-items:center; justify-content:center; width: 48px; height:48px; border-radius: 14px; background: var(--soft); color: var(--link); margin-bottom: 16px; }
.step h3, .benefit h3 { margin: 0 0 6px; font-size: 1.1rem; }
.step p, .benefit p { margin:0; color: var(--muted); }
.alt { background: var(--card); border-top:1px solid var(--border); border-bottom:1px solid var(--border); }
.example { display:grid; grid-template-columns: 7fr 4fr; gap: 32px; align-items:start; }
.shots { display:grid; grid-template-columns: 1fr auto 1fr 1fr; gap: 14px; align-items:center; }
.shots figure { margin:0; }
.shots img { display:block; width:100%; height:auto; aspect-ratio: 3 / 4; object-fit: cover; border-radius: 14px; border:1px solid var(--border); }
.shots figcaption { font-size:.85rem; font-weight:700; margin-top: 8px; text-align:center; }
.shots .before img { filter: saturate(.85); }
.shots .then { color: var(--link); }
.listing { background: var(--bg); border:1px solid var(--border); border-radius: 18px; padding: 22px; }
.listing h3 { margin: 4px 0 8px; font-size: 1.1rem; line-height:1.3; }
.listing .price { font-size: 1.5rem; font-weight: 800; margin: 0 0 12px; }
.tags { display:flex; flex-wrap:wrap; gap: 6px; margin: 0 0 14px; padding:0; list-style:none; }
.tags li { font-size:.8rem; font-weight:700; padding: 3px 10px; border-radius: 999px; background: var(--soft); color: var(--link); }
.listing p { margin:0; color: var(--muted); font-size:.95rem; }
.benefits { display:grid; grid-template-columns: repeat(4, 1fr); gap: 20px; }
.benefit .badge { width: 44px; height: 44px; }
.pricing { max-width: 460px; margin: 0 auto; background: var(--card); border:2px solid var(--accent); border-radius: 22px; padding: 32px; box-shadow: 0 16px 40px rgba(46,31,43,.10); text-align:left; }
.amount { font-size: 3rem; font-weight: 800; letter-spacing:-.03em; line-height:1; }
.amount small { font-size: 1rem; font-weight: 600; color: var(--muted); letter-spacing:0; }
.pricing ul { list-style:none; padding:0; margin: 22px 0 24px; display:grid; gap: 10px; }
.pricing li { display:flex; gap: 10px; align-items:flex-start; }
.pricing li .ico { color: var(--link); flex: none; margin-top: 3px; }
.pricing .actions { flex-direction: column; }
.pricing .actions .button { justify-content:center; }
.note { font-size: .85rem; color: var(--muted); margin: 18px 0 0; }
.faq { max-width: 760px; margin: 0 auto; }
.faq details { border-bottom: 1px solid var(--border); padding: 18px 4px; }
.faq summary { cursor:pointer; font-weight: 700; font-size: 1.05rem; list-style:none; display:flex; justify-content:space-between; gap: 16px; }
.faq summary::-webkit-details-marker { display:none; }
.faq summary::after { content: "+"; color: var(--link); font-size: 1.4rem; line-height: 1; }
.faq details[open] summary::after { content: "–"; }
.faq details p { margin: 10px 0 0; color: var(--muted); }
.final { text-align:center; padding-bottom: 88px; }
.final .actions { justify-content:center; }
@media (max-width: 900px) {
  .hero .wrap, .example { grid-template-columns: 1fr; }
  .benefits { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 640px) {
  section { padding: 52px 0; }
  .hero { padding-top: 36px; }
  .steps, .benefits { grid-template-columns: 1fr; }
  .shots { grid-template-columns: 1fr 1fr; }
  .shots .before { grid-column: 1 / -1; max-width: 60%; margin: 0 auto; }
  .shots .then { display:none; }
  .actions .button { flex: 1 1 100%; justify-content:center; }
}
`;

function euros(value: number): string {
  return `${value.toFixed(2).replace(".", ",")} €`;
}

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

const FAQ: [string, string][] = [
  [
    "Comment se passe l'essai ?",
    "Tu t'inscris avec ton e-mail et ta carte : rien n'est prélevé pendant 7 jours. Tu reçois ta clé de licence par e-mail, tu la colles dans l'application, et c'est parti. Si tu résilies avant la fin de l'essai, tu ne paies rien.",
  ],
  [
    "Faut-il un compte Google ?",
    "Oui : Kaloé utilise Gemini, l'IA de Google, avec ta propre clé. Elle se crée gratuitement en deux minutes sur Google AI Studio, et l'application te guide pas à pas. Google peut facturer au-delà de son quota gratuit ; tu suis ta consommation dans ton compte Google.",
  ],
  [
    "Mon compte Vinted est-il en sécurité ?",
    "Kaloé ne te demande jamais ton mot de passe Vinted : tu te connectes toi-même dans une fenêtre dédiée, comme dans ton navigateur. Rien n'est envoyé sur Vinted sans que tu aies relu et validé l'annonce.",
  ],
  [
    "Sur combien de PC puis-je l'utiliser ?",
    "Ta clé fonctionne sur 2 PC Windows (10 ou 11). Pour changer de PC, désactive l'ancien depuis les réglages de l'application.",
  ],
  [
    "Kaloé fonctionne-t-il sur Mac ou sur téléphone ?",
    "Pas pour l'instant : Kaloé est une application pour Windows 10 et 11.",
  ],
  [
    "Comment résilier ?",
    "En un clic, dans l'application : Réglages, puis « Gérer mon abonnement ». Tu gardes l'accès jusqu'à la fin de la période payée, et tes articles restent sur ton PC.",
  ],
];

export function homePage(env: Env): Response {
  const price = escapeHtml(env.PRICE_LABEL);
  const ex = EXAMPLE;
  const faq = FAQ.map(([q, a]) => `<details><summary>${escapeHtml(q)}</summary><p>${escapeHtml(a)}</p></details>`).join("\n");
  const ctas = `<a class="button" href="/essai">${icon("sparkles", 18)} Essayer 7 jours gratuits</a>
<a class="button secondary" href="/telecharger">${icon("download", 18)} Télécharger pour Windows</a>`;

  return htmlPage(
    "Photos portées et annonces Vinted",
    `<section class="hero"><div class="wrap">
<div>
<span class="eyebrow">Pour les vendeurs Vinted</span>
<h1>Tes vêtements, <em>portés</em> et prêts à vendre.</h1>
<p class="lead">Prends ton vêtement en photo, même sur une porte : Kaloé en fait des photos portées soignées, rédige l'annonce et prépare le brouillon sur Vinted. Tu relis, tu valides, c'est en ligne.</p>
<div class="actions">${ctas}</div>
<p class="fine">Windows 10 et 11 · ${price}/mois après l'essai · sans engagement</p>
</div>
<div class="video">
<video controls preload="none" playsinline poster="/media/kaloe.jpg" aria-label="Kaloé en une minute">
<source src="/media/kaloe.mp4" type="video/mp4">
<track kind="subtitles" srclang="fr" label="Français" src="/media/kaloe.vtt" default>
</video>
</div>
</div></section>

<section id="etapes"><div class="wrap">
<div class="center">
<span class="eyebrow">Comment ça marche</span>
<h2 class="section-title">Trois étapes, quelques minutes.</h2>
<p class="section-lead">Fini les heures à chercher la bonne lumière et la bonne description.</p>
</div>
<div class="steps">
<div class="step"><span class="badge">${icon("camera")}</span><h3>Prends ton vêtement en photo</h3><p>À plat, sur un cintre ou contre une porte : une photo nette suffit.</p></div>
<div class="step"><span class="badge">${icon("sparkles")}</span><h3>Kaloé fait le reste</h3><p>Photos portées dans tes décors, titre, description, taille, état et prix proposés.</p></div>
<div class="step"><span class="badge">${icon("send")}</span><h3>Tu relis, c'est sur Vinted</h3><p>Tu ajustes si besoin, puis Kaloé crée le brouillon sur Vinted en un clic.</p></div>
</div>
</div></section>

<section id="exemples" class="alt"><div class="wrap">
<span class="eyebrow">Exemple</span>
<h2 class="section-title">D'une photo vite prise à une annonce complète.</h2>
<p class="section-lead">Un jean photographié contre une porte. Kaloé en tire deux photos portées et rédige l'annonce.</p>
<div class="example">
<div class="shots">
<figure class="before"><img src="/media/exemple-photo.jpg" alt="Photo d'origine : jean suspendu à une porte" width="600" height="800" loading="lazy"><figcaption>Ta photo</figcaption></figure>
<span class="then">${icon("arrow", 28)}</span>
<figure><img src="/media/exemple-cintre.jpg" alt="Le jean sur un cintre, dans un décor chaleureux" width="896" height="1200" loading="lazy"><figcaption>Sur cintre</figcaption></figure>
<figure><img src="/media/exemple-mannequin.jpg" alt="Le jean porté par un mannequin, dans un dressing" width="896" height="1200" loading="lazy"><figcaption>Sur mannequin</figcaption></figure>
</div>
<article class="listing" aria-label="Annonce rédigée par Kaloé">
<span class="eyebrow">Annonce rédigée</span>
<h3>${escapeHtml(ex.title)}</h3>
<p class="price">${escapeHtml(euros(ex.price))}</p>
<ul class="tags"><li>${escapeHtml(capitalize(ex.brand))}</li><li>Taille ${escapeHtml(ex.size)}</li><li>${escapeHtml(ex.condition)}</li></ul>
<p>${escapeHtml(ex.intro)}</p>
</article>
</div>
</div></section>

<section><div class="wrap">
<div class="center">
<span class="eyebrow">Pourquoi Kaloé</span>
<h2 class="section-title">Pensé pour vendre, sans prise de tête.</h2>
<p class="section-lead">Une application simple, qui te laisse toujours le dernier mot.</p>
</div>
<div class="benefits">
<div class="benefit"><span class="badge">${icon("image", 22)}</span><h3>Tes décors, ton style</h3><p>Mannequin, cintre… ou tes propres décors, pour une vitrine reconnaissable.</p></div>
<div class="benefit"><span class="badge">${icon("eye", 22)}</span><h3>Toujours relu par toi</h3><p>Chaque photo et chaque annonce passent par ta relecture avant l'envoi.</p></div>
<div class="benefit"><span class="badge">${icon("lock", 22)}</span><h3>Aucun mot de passe stocké</h3><p>Tu te connectes à Vinted toi-même ; Kaloé ne connaît pas ton mot de passe.</p></div>
<div class="benefit"><span class="badge">${icon("monitor", 22)}</span><h3>Sur ton PC</h3><p>Tes photos et tes articles restent sur ton ordinateur.</p></div>
</div>
</div></section>

<section id="tarif" class="alt"><div class="wrap">
<div class="center">
<span class="eyebrow">Tarif</span>
<h2 class="section-title">Un prix simple, sans surprise.</h2>
<p class="section-lead">Essaie gratuitement pendant 7 jours, puis continue seulement si Kaloé te fait gagner du temps.</p>
</div>
<div class="pricing">
<div class="amount">${price} <small>/ mois</small></div>
<ul>
<li>${icon("check", 18)}<span><strong>7 jours d'essai gratuit</strong> : rien n'est prélevé avant la fin</span></li>
<li>${icon("check", 18)}<span>Photos portées, annonces et brouillons Vinted</span></li>
<li>${icon("check", 18)}<span>Mises à jour incluses</span></li>
<li>${icon("check", 18)}<span>2 PC par licence</span></li>
<li>${icon("check", 18)}<span>Sans engagement, résiliable en un clic</span></li>
</ul>
<div class="actions">${ctas}</div>
<p class="note">Kaloé utilise ta clé Gemini (Google) : gratuite à créer ; Google peut facturer au-delà de son quota gratuit.</p>
</div>
</div></section>

<section id="questions"><div class="wrap">
<div class="center">
<span class="eyebrow">Questions</span>
<h2 class="section-title">Questions fréquentes</h2>
</div>
<div class="faq">
${faq}
<details><summary>Windows dit que l'application est inconnue</summary><p>C'est normal pour une petite application récente : clique sur « Informations complémentaires », puis « Exécuter quand même ». Tout est expliqué dans <a href="/aide">l'aide à l'installation</a>.</p></details>
<details><summary>J'ai téléchargé l'application avant de m'inscrire</summary><p>Ouvre-la : sur le premier écran, clique sur « Essayer 7 jours ». Une fois inscrit, colle la clé reçue par e-mail. Déjà abonné ? <a href="/retrouver">Retrouver ma clé</a>.</p></details>
</div>
</div></section>

<section class="final alt"><div class="wrap">
<h2 class="section-title">Ta prochaine annonce en quelques minutes.</h2>
<p class="section-lead">7 jours pour essayer, sans engagement.</p>
<div class="actions">${ctas}</div>
</div></section>`,
    200,
    {
      wide: true,
      css: CSS,
      description:
        "Kaloé transforme la photo de ton vêtement en photos portées et en annonce Vinted prête à publier. Application Windows, 7 jours d'essai gratuit.",
    },
  );
}
