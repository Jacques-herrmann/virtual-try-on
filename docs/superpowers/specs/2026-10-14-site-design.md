# Sous-projet 9 — Site vitrine kaloe.fr — Design

Date : 2026-10-14
Statut : validé en brainstorming le 2026-10-14

## 1. Contexte

`kaloe.fr` est servi par le Worker de licence (`worker/`). Son accueil (`homePage` dans `worker/src/pages.ts`) se limite à un titre, un paragraphe et un bouton « Essayer 7 jours » vers le lien de paiement Stripe. Le téléchargement (`/telecharger`) exige une clé de licence valide : on ne peut obtenir l'app qu'après l'inscription à l'essai.

L'utilisateur veut un lien à envoyer à des vendeurs : un vrai site de présentation (menu, explication de l'app, vidéo, exemples, tarif) avec un lien pour démarrer l'essai et un lien pour télécharger. Les deux parcours doivent se rejoindre : qui télécharge d'abord peut, depuis l'app, aller au paiement (lien déjà présent sur l'écran d'accueil de l'app) ; qui paie d'abord reçoit le lien de téléchargement (déjà le cas).

### 1.1 Décisions (prises en brainstorming)

| Sujet | Décision |
|---|---|
| Accès au téléchargement | **Libre** : `/telecharger` sans clé donne l'installeur ; l'app reste inutilisable sans clé (inscription à l'essai depuis l'app ou le site) |
| Présentation | Vidéo du tutoriel (`frontend/public/tutorial/kaloe.*`) + exemple avant/après tiré de l'article du tutoriel (`tools/tutorial/`) |
| Navigation | En-tête de site avec menu (ancres de l'accueil + Aide), repliable sur téléphone |
| Tarif | **14,90 € / mois** affiché en clair, après 7 jours d'essai, sans engagement ; texte du prix dans `wrangler.toml` |
| Pages légales | Mentions légales, CGV, confidentialité : brouillons rédigés, informations de l'éditeur à compléter par l'utilisateur |
| Technique | Tout dans le Worker existant ; médias servis par les fichiers statiques Cloudflare (`[assets]`) |

Approches écartées : téléchargement réservé aux inscrits (comme aujourd'hui) ; essai démarré dans l'app sans carte (revoit la licence, anti-abus coûteux, déjà écarté au sous-projet 5) ; présentation par captures seules ou vidéo seule ; prix masqué ; site statique séparé sur Cloudflare Pages ou Astro (deux déploiements, routage partagé avec le Worker, deux styles) ; site Vite dans `frontend/` (mélange site public et app de bureau) ; redimensionnement des photos par ffmpeg (absent de la CI ; les photos font déjà ~300 Ko).

### 1.2 Hors périmètre

- Blog, plusieurs langues, statistiques de visite, bandeau cookies (aucun cookie ni traceur sur le site).
- Formule annuelle (envisagée plus tard).
- Autres exemples que le jean du tutoriel.
- Relecture juridique des pages légales (à la charge de l'utilisateur).

## 2. Page d'accueil (`GET /`)

De haut en bas :

1. **En-tête fixe** : logo Kaloé (lien vers `/`) ; liens *Comment ça marche* (`/#etapes`), *Exemples* (`/#exemples`), *Tarif* (`/#tarif`), *Questions* (`/#questions`), *Aide* (`/aide`) ; bouton « Essayer 7 jours » (`/essai`). Sous ~760 px, les liens passent dans un `<details>` « Menu » (aucun JavaScript). Les ancres sont absolues (`/#…`) pour fonctionner depuis toutes les pages.
2. **Bandeau principal** : titre « Tes vêtements, portés et prêts à vendre. », une phrase d'explication, boutons **Essayer 7 jours gratuits** (`/essai`, principal) et **Télécharger pour Windows** (`/telecharger`, secondaire), mention « Windows 10 et 11 · {PRICE_LABEL}/mois après l'essai · sans engagement ». À côté (en dessous sur téléphone) : `<video controls preload="none" poster="/media/kaloe.jpg">` avec `<track kind="subtitles" srclang="fr" default src="/media/kaloe.vtt">`. Pas de lecture automatique.
3. **Comment ça marche** (`#etapes`) : trois étapes avec icône — *Prends ton vêtement en photo* → *Kaloé crée les photos portées et rédige l'annonce* → *Tu relis, le brouillon est prêt sur Vinted*.
4. **Exemples** (`#exemples`) : photo d'origine (« Ta photo »), puis « Sur cintre » et « Sur mannequin » ; à côté, l'annonce générée : titre, marque, taille, état, prix, et le **premier paragraphe** de la description (la suite contient la signature personnelle du vendeur).
5. **Ce qui change pour toi** : quatre arguments — tes décors (scènes personnalisables), relecture avant tout envoi, aucun mot de passe Vinted stocké, l'app tourne sur ton PC.
6. **Tarif** (`#tarif`) : une carte — *{PRICE_LABEL} / mois* ; 7 jours d'essai, rien n'est prélevé avant la fin ; 2 PC par licence ; résiliable en un clic. Note : « Kaloé utilise ta clé Gemini (Google) : gratuite à créer ; Google peut facturer au-delà de son quota gratuit. » Les deux boutons à nouveau.
7. **Questions fréquentes** (`#questions`), en `<details>` : Comment se passe l'essai ? · Faut-il un compte Google ? · Mon compte Vinted est-il en sécurité ? · Sur combien de PC ? · Comment résilier ? · Windows dit que l'app est inconnue (SmartScreen, lien vers `/aide`) · J'ai téléchargé avant de m'inscrire (ouvrir l'app, « Essayer 7 jours »).
8. **Pied de page** (commun à toutes les pages) : Aide · Retrouver ma clé · Contact (`mailto:contact@kaloe.fr`) · Mentions légales · CGV · Confidentialité · © Kaloé.

Style : palette Kaloé de `pages.ts` (abricot/crème, mode sombre par `prefers-color-scheme`), logo SVG en ligne, polices système (aucune requête tierce). Mise en page en grille sur ordinateur (largeur max ~1080 px pour l'accueil), une colonne sur téléphone, marge latérale 16 px, aucun défilement horizontal à 375 px. Les pages de texte (licence, légales, aide) gardent une colonne étroite (~720 px).

## 3. Routes et données

### 3.1 Routes du Worker

| Route | Comportement |
|---|---|
| `GET /` | Nouvelle page d'accueil (§2) |
| `GET /essai` | **Nouvelle** : `302` vers `PAYMENT_LINK_URL`. Seule adresse de paiement utilisée par le site et l'app |
| `GET /telecharger` | Sans paramètre `cle` : installeur (`.exe`) de la dernière Release, par le relais GitHub existant (`latestRelease`, `releaseAsset`). Avec `cle` : inchangé (clé inconnue → 404, expirée → 403) |
| `GET /mentions-legales`, `/cgv`, `/confidentialite` | **Nouvelles** : pages légales (§3.5) |
| `/merci`, `/retrouver`, `/renouveler`, `/aide`, erreurs | Contenu inchangé, nouveau gabarit (en-tête avec menu, pied de page) |

Les fichiers de `worker/public/` sont servis par Cloudflare avant le code du Worker (`[assets] directory = "public"`) ; seuls des chemins `/media/…` y sont déposés, sans collision avec les routes.

### 3.2 Côté app

`WelcomeView.vue` : le lien « Essayer 7 jours » pointe vers `${site_url}/essai` (au lieu de `${site_url}/`). Les versions déjà installées arrivent sur l'accueil, qui porte le même bouton.

### 3.3 Configuration (`wrangler.toml`)

- Nouvelle variable `PRICE_LABEL = "14,90 €"` (ajoutée au type `Env`).
- `PAYMENT_LINK_URL` et `STRIPE_PRICE_IDS` : à remplacer par l'utilisateur une fois le prix à 14,90 € créé dans Stripe (§5). Le prix à 20 € reste dans `STRIPE_PRICE_IDS` tant que des abonnements de test le portent.

### 3.4 Médias (`npm run build:media`)

Script `worker/scripts/build-media.mjs`, en Node seul (pas de ffmpeg), ajouté à `build:generated` (donc lancé par `dev`, `deploy`, `test`, `typecheck`) :

- copie `frontend/public/tutorial/kaloe.mp4`, `kaloe.vtt`, `kaloe.jpg` → `worker/public/media/` ;
- copie `tools/tutorial/demo/article-01.jpg` → `media/exemple-photo.jpg`, et les deux images de `tools/tutorial/capture/images/` → `media/exemple-cintre.jpg` et `media/exemple-mannequin.jpg` (correspondance des noms fixée dans le script) ;
- écrit `worker/src/site/example.generated.ts` : titre, marque, taille, état, prix et premier paragraphe de la description, lus dans `tools/tutorial/capture/listing.json`.

Un fichier source manquant arrête le script avec un message qui indique la commande à lancer (`vto-tutorial record` ou `vto-tutorial capture`). `worker/public/` et `example.generated.ts` sont ignorés par git, comme les autres fichiers générés. `.github/workflows/worker.yml` se déclenche aussi sur `frontend/public/tutorial/**` et `tools/tutorial/**`.

### 3.5 Pages légales

`worker/src/site/legal.ts` commence par un objet `PUBLISHER` (nom ou raison sociale, statut, SIRET, adresse, e-mail `contact@kaloe.fr`, directeur de publication) ; hébergeur pré-rempli (Cloudflare, Inc., 101 Townsend St, San Francisco, CA 94107, USA). Un champ non rempli vaut la constante `TO_FILL` et s'affiche « à compléter ».

- **Mentions légales** : éditeur, directeur de publication, hébergeur, contact.
- **CGV** : objet (licence d'utilisation de l'app par abonnement), essai de 7 jours avec carte et sans prélèvement avant la fin, prix et renouvellement mensuel, paiement et facturation par Stripe (vendeur officiel via Managed Payments, ses conditions s'appliquent au paiement), résiliation depuis l'app (« Gérer mon abonnement ») ou le portail Stripe, 2 PC par licence, clé Gemini fournie et payée par le client auprès de Google, responsabilité (relecture obligatoire avant envoi sur Vinted, Kaloé n'est pas affilié à Vinted), droit de rétractation (renoncement exprès pour un contenu numérique fourni pendant l'essai, à faire valider par l'utilisateur), contact et droit applicable.
- **Confidentialité** : données traitées (e-mail, identifiant client Stripe, empreintes des PC activés), finalités (licence, e-mails de clé), sous-traitants (Stripe, Cloudflare, Resend, GitHub pour les téléchargements), absence de cookies et de traceurs sur le site, données restant sur le PC (photos, articles, clé Gemini, session Vinted), envoi des photos à Google par la clé Gemini du client, durée de conservation, droits RGPD et contact, réclamation à la CNIL.

### 3.6 Code

- `worker/src/site/layout.ts` : `htmlPage` (déplacé depuis `pages.ts`, même signature, option de mise en page large pour l'accueil), style, en-tête, pied de page.
- `worker/src/site/home.ts` : `homePage(env)`.
- `worker/src/site/legal.ts` : `PUBLISHER`, `legalPage(kind)`, `missingPublisherFields()`.
- `pages.ts` garde les pages de licence et importe le gabarit ; `index.ts` ajoute les routes.

## 4. Erreurs

- GitHub injoignable ou Release sans installeur : `/telecharger` sans clé renvoie la page d'erreur actuelle (502, « Le téléchargement est momentanément indisponible. Réessaie dans quelques minutes. »).
- Média source absent : `build:media` échoue (§3.4), donc pas de déploiement sans vidéo.
- Champs de l'éditeur non remplis : `npm run deploy` affiche un avertissement listant les champs « à compléter » (script `scripts/check-legal.mjs`, qui lit `legal.ts`) ; le déploiement n'est pas bloqué.

## 5. Tests et vérification

Vitest (Worker, D1 locale, GitHub simulé comme dans les tests existants) :

- `/` : 200, contient `PRICE_LABEL`, des liens vers `/essai` et `/telecharger`, la balise vidéo et les ancres `etapes`, `exemples`, `tarif`, `questions`.
- `/essai` : 302 vers `PAYMENT_LINK_URL`.
- `/telecharger` sans clé : installeur renvoyé ; avec une clé inconnue : 404.
- `/mentions-legales`, `/cgv`, `/confidentialite` : 200 ; une page de licence existante (`/retrouver`) porte l'en-tête et le pied de page.
- `missingPublisherFields()` liste les champs valant `TO_FILL`.

Front (Vitest) : le test de `WelcomeView` vérifie le lien vers `/essai`.

Vérification visuelle : `npm run dev` du Worker, tour de l'accueil, d'une page légale et de `/retrouver` à ~1280 px et ~375 px, en clair et en sombre ; lecture de la vidéo avec sous-titres.

### Étapes de l'utilisateur avant la mise en production

1. Stripe (test, puis production) : créer le prix à 14,90 €/mois, refaire le lien de paiement, reporter l'identifiant du prix et le lien dans `wrangler.toml`.
2. Remplir `PUBLISHER` dans `legal.ts` ; faire relire les pages légales si souhaité.
3. Déployer (push sur `main` si le jeton Cloudflare est configuré dans GitHub, sinon `npm run deploy`).
