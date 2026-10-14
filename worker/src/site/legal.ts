import type { Env } from "../env";
import { escapeHtml } from "../http";
import { htmlPage } from "./layout";

/** Valeur d'un champ pas encore renseigné : affiché « à compléter », signalé au déploiement. */
export const TO_FILL = "À COMPLÉTER";

export interface Publisher {
  /** Nom et prénom, ou raison sociale. */
  name: string;
  /** Statut juridique (ex. « Micro-entreprise », « SASU au capital de 1 000 € »). */
  status: string;
  siret: string;
  /** Adresse postale du siège ou de domiciliation. */
  address: string;
  /** Directeur ou directrice de la publication. */
  director: string;
}

// Éditeur du site et vendeur de l'abonnement : à remplir avant la mise en production.
export const PUBLISHER: Publisher = {
  name: TO_FILL,
  status: "Entrepreneur individuel (micro-entreprise)",
  siret: TO_FILL,
  address: TO_FILL,
  director: TO_FILL,
};

const CONTACT = "contact@kaloe.fr";
const HOST = "Cloudflare, Inc., 101 Townsend St, San Francisco, CA 94107, États-Unis — www.cloudflare.com";

export function missingPublisherFields(publisher: Publisher = PUBLISHER): (keyof Publisher)[] {
  return (Object.keys(publisher) as (keyof Publisher)[]).filter((k) => publisher[k] === TO_FILL);
}

function field(value: string): string {
  return value === TO_FILL ? `<span class="todo">à compléter</span>` : escapeHtml(value);
}

const mail = `<a href="mailto:${CONTACT}">${CONTACT}</a>`;

function mentions(): string {
  const p = PUBLISHER;
  return `<h1>Mentions légales</h1>
<h2>Éditeur</h2>
<p>${field(p.name)}<br>${field(p.status)}<br>SIRET : ${field(p.siret)}<br>${field(p.address)}<br>Contact : ${mail}</p>
<h2>Directeur de la publication</h2>
<p>${field(p.director)}</p>
<h2>Hébergeur</h2>
<p>${escapeHtml(HOST)}</p>
<h2>Propriété intellectuelle</h2>
<p>Le nom Kaloé, le logo, les textes, les images et les vidéos de ce site sont protégés. Toute reproduction sans autorisation est interdite.</p>
<h2>Marques</h2>
<p>Vinted est une marque de Vinted UAB ; Gemini et Google sont des marques de Google LLC. Kaloé est un outil indépendant, ni affilié ni approuvé par ces sociétés.</p>`;
}

function cgv(env: Env): string {
  const price = escapeHtml(env.PRICE_LABEL);
  return `<h1>Conditions générales de vente</h1>
<p class="muted">En vigueur au 14 octobre 2026.</p>
<h2>1. Objet</h2>
<p>Les présentes conditions régissent l'abonnement à Kaloé, application pour Windows qui crée des photos portées et des annonces à partir de photos de vêtements, et prépare des brouillons d'annonces sur Vinted. Kaloé est édité par ${field(PUBLISHER.name)} (voir les <a href="/mentions-legales">mentions légales</a>).</p>
<h2>2. Essai gratuit</h2>
<p>L'abonnement commence par un essai gratuit de 7 jours. Une carte bancaire est demandée à l'inscription, mais rien n'est prélevé pendant l'essai. Sans résiliation avant la fin de l'essai, l'abonnement payant démarre automatiquement.</p>
<h2>3. Prix et paiement</h2>
<p>L'abonnement coûte ${price} TTC par mois, prélevé chaque mois à date anniversaire. Le paiement et la facturation sont assurés par Stripe, qui agit en tant que revendeur (Stripe Managed Payments) : les conditions de Stripe s'appliquent à la transaction, et les factures sont envoyées par e-mail. Une modification du prix est annoncée par e-mail au moins 30 jours avant de s'appliquer, et le client peut résilier d'ici là.</p>
<h2>4. Licence</h2>
<p>L'abonnement donne une clé de licence personnelle, utilisable sur 2 ordinateurs à la fois. Un ordinateur peut être désactivé depuis les réglages de l'application pour en activer un autre. Les mises à jour sont incluses pendant l'abonnement.</p>
<h2>5. Clé Gemini</h2>
<p>Kaloé utilise Gemini, service de Google, avec la clé personnelle du client. La création de cette clé, son usage et son éventuelle facturation relèvent des conditions de Google, entre le client et Google. Kaloé n'est pas responsable des coûts facturés par Google.</p>
<h2>6. Résiliation</h2>
<p>Le client peut résilier à tout moment, sans frais, depuis l'application (Réglages, « Gérer mon abonnement »). L'accès reste ouvert jusqu'à la fin de la période déjà payée ; aucune période entamée n'est remboursée. Les données du client restent sur son ordinateur.</p>
<h2>7. Droit de rétractation</h2>
<p>Le client consommateur dispose d'un délai de 14 jours à compter de la souscription pour se rétracter, en écrivant à ${mail}. L'essai gratuit de 7 jours lui permet de tester Kaloé sans frais. S'il demande à utiliser l'application dès la souscription, il reconnaît que l'exécution commence immédiatement et renonce à son droit de rétractation pour la part de service déjà fournie (article L221-28 du Code de la consommation).</p>
<h2>8. Responsabilité</h2>
<p>Les photos et les annonces sont générées par une intelligence artificielle et peuvent comporter des erreurs. Le client les relit avant tout envoi sur Vinted et reste seul responsable de ses annonces et de leur conformité aux règles de Vinted. Kaloé n'est ni affilié ni approuvé par Vinted ; un changement du site Vinted peut interrompre temporairement l'envoi des brouillons, rétabli par une mise à jour.</p>
<h2>9. Contact et litiges</h2>
<p>Pour toute question ou réclamation : ${mail}. Les présentes conditions sont soumises au droit français. En cas de litige, le client consommateur peut recourir gratuitement à un médiateur de la consommation ou à la plateforme européenne de règlement en ligne des litiges.</p>`;
}

function confidentialite(): string {
  return `<h1>Politique de confidentialité</h1>
<p class="muted">En vigueur au 14 octobre 2026.</p>
<h2>Responsable du traitement</h2>
<p>${field(PUBLISHER.name)}, ${field(PUBLISHER.address)} — ${mail}.</p>
<h2>Données traitées</h2>
<ul>
<li><strong>Abonnement</strong> : adresse e-mail, identifiants client et d'abonnement Stripe, statut et date de fin de l'abonnement, clé de licence.</li>
<li><strong>Activation</strong> : un identifiant technique et le nom de chaque ordinateur activé, date de la dernière vérification.</li>
<li><strong>« Retrouver ma clé »</strong> : une empreinte de l'adresse saisie, conservée 24 heures pour limiter les abus.</li>
</ul>
<p>Ces données servent uniquement à délivrer et vérifier la licence, et à envoyer la clé par e-mail. Base légale : l'exécution du contrat d'abonnement.</p>
<h2>Ce qui reste sur ton ordinateur</h2>
<p>Tes photos, tes articles, tes annonces, ta clé Gemini et ta session Vinted restent sur ton PC : Kaloé ne les reçoit pas. Pour créer les photos et les annonces, l'application envoie tes photos directement à Google (Gemini) avec ta propre clé ; ce traitement relève des conditions de Google.</p>
<h2>Sous-traitants</h2>
<ul>
<li>Stripe (paiement, facturation)</li>
<li>Cloudflare (hébergement du site et de la base de licences)</li>
<li>Resend (envoi des e-mails de clé)</li>
<li>GitHub (stockage des fichiers d'installation)</li>
</ul>
<p>Certains sont situés aux États-Unis ; les transferts sont encadrés par les clauses contractuelles types de la Commission européenne ou le cadre de protection des données UE–États-Unis.</p>
<h2>Cookies</h2>
<p>Ce site ne dépose aucun cookie et n'utilise aucun outil de mesure d'audience ni traceur publicitaire.</p>
<h2>Durée de conservation</h2>
<p>Les données d'abonnement sont conservées pendant l'abonnement, puis 3 ans après sa fin. Les factures sont conservées par Stripe selon ses obligations légales.</p>
<h2>Tes droits</h2>
<p>Tu peux demander l'accès, la rectification, l'effacement ou la portabilité de tes données, ou t'opposer à leur traitement, en écrivant à ${mail}. Tu peux aussi adresser une réclamation à la CNIL (<a href="https://www.cnil.fr">www.cnil.fr</a>).</p>`;
}

const PAGES = {
  mentions: ["Mentions légales", mentions],
  cgv: ["Conditions générales de vente", cgv],
  confidentialite: ["Politique de confidentialité", confidentialite],
} as const;

export function legalPage(kind: keyof typeof PAGES, env: Env): Response {
  const [title, body] = PAGES[kind];
  return htmlPage(title, body(env));
}
