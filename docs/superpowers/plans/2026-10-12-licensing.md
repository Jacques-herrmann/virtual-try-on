# Plan d'implémentation — Sous-projet 5 : Licence

Spec : `docs/superpowers/specs/2026-10-12-licensing-design.md` (référencée ci-dessous par « spec §x »).
Branche : `main` (travail direct).

## Conventions

- **TDD** partout : test → échec constaté → implémentation → tests + lint verts → commit.
- Worker : TypeScript strict, Vitest avec `@cloudflare/vitest-pool-workers` (D1 locale) ; aucun appel réseau en test (Stripe, Resend et GitHub simulés par `fetchMock` / injection). Versions des paquets npm vérifiées sur le registre (stables, publiées depuis plus de 2 semaines), épinglées exactement comme dans `frontend/`.
- App : mêmes règles que les sous-projets précédents (`data_dir`, `httpx.MockTransport`, aucun `sleep` réel, prédicats injectés).
- **Un commit par tâche**, message court en anglais à l'impératif minuscule.
- Textes visibles : français, tutoiement, sans jargon. Pages du Worker : HTML sobre, sans framework, lisible sur mobile.
- Aucun secret dans le dépôt : `wrangler secret put`, `.dev.vars` ignoré par git pour le local.
- Cocher les cases au fur et à mesure.

---

## Partie A — Worker

### Tâche 0 — Squelette (spec §2.1, §2.2)

- [x] `worker/` : `package.json` (wrangler, typescript, vitest, `@cloudflare/vitest-pool-workers`, `@cloudflare/workers-types`), `tsconfig.json`, `wrangler.toml` (nom `vto-licence`, binding D1 `DB`, variables `PUBLIC_BASE_URL`, `GITHUB_REPO`, `PAYMENT_LINK_URL`), `vitest.config.ts`, `.dev.vars.example`.
- [x] `schema.sql` (spec §2.2) + migration D1 `migrations/0001_init.sql` ; les tests appliquent la migration à la D1 locale.
- [x] `src/index.ts` : routeur minimal, `GET /health` → `{ok: true}` ; réponses JSON d'erreur `{code, message}` en français.
- [x] Test : `/health`, route inconnue → 404.
- [x] `.gitignore` : `worker/node_modules`, `worker/.wrangler`, `worker/.dev.vars`.
- [x] `ci.yml` : job `worker` (`npm ci`, `npm run typecheck`, `npm test`).
- [x] Commit `add worker skeleton`.

### Tâche 1 — Licences et clés (spec §2.2)

- [x] Tests `licenses.test.ts` : format `VTO-XXXX-XXXX-XXXX-XXXX` (Crockford, sans I L O U) ; `normalizeKey` (espaces, minuscules, tirets manquants, `0/O` et `1/I/L` confondus) ; création ; une seule licence par client Stripe (reprise de la clé) ; mise à jour statut / `period_end` / `synced_at` ; `isValidStatus` (`trialing`, `active`, `past_due`).
- [x] Implémenter `src/licenses.ts` (requêtes D1 préparées).
- [x] Commit `add license keys and storage`.

### Tâche 2 — Jetons Ed25519 (spec §2.4)

- [x] `tools/make_signing_key.py` : génère la paire (`cryptography`), affiche la clé privée (PKCS8 base64, à passer à `wrangler secret put TOKEN_PRIVATE_KEY`) et la clé publique (raw base64, à embarquer dans l'app) avec un `kid`.
- [x] Tests `tokens.test.ts` : contenu (`v`, `kid`, `lic` = sha256 tronqué, `dev`, `status`, `period_end`, `iat`) ; `exp = min(period_end, iat + 7 j)` ; signature vérifiable par la clé publique ; `verifyToken` refuse signature fausse, `kid` inconnu, `exp` passé.
- [x] **Vecteur partagé** : un jeton signé avec une clé de test fixe, écrit dans `worker/test/fixtures/token.json` et relu par les tests Python (tâche 8) pour garantir la compatibilité des deux implémentations.
- [x] Implémenter `src/tokens.ts` (WebCrypto `Ed25519`, base64url).
- [x] Commit `add signed license tokens`.

### Tâche 3 — Webhooks Stripe et e-mail (spec §2.3)

- [x] Tests `stripe.test.ts` (événements construits et signés en test avec un secret de test) :
  - signature absente, fausse ou trop ancienne (> 5 min) → 400 ;
  - `checkout.session.completed` → licence créée, e-mail envoyé (Resend simulé : destinataire, clé, lien `/telecharger?cle=`) ; même client → même clé, e-mail renvoyé ;
  - `customer.subscription.created/updated/deleted` → statut et `period_end` ;
  - même `event.id` deux fois → aucun effet la 2ᵉ fois ;
  - échec de Resend → licence créée quand même (log) ; le client retrouvera sa clé sur `/merci` ou `/retrouver`.
- [x] Implémenter `src/stripe.ts` (vérification HMAC-SHA256 de `Stripe-Signature` via WebCrypto, appels API Stripe par `fetch` — pas de SDK) et `src/email.ts` (API Resend par `fetch`, texte + HTML simples).
- [x] Recalage (spec §2.3) : `syncSubscription(license)` relit `GET /v1/subscriptions/:id` si `synced_at` > 24 h ; Stripe en erreur → valeurs de D1. Tests.
- [x] Commit `add stripe webhooks and license email`.

### Tâche 4 — Activation (spec §2.3)

- [x] Tests `activation.test.ts` :
  - `/api/activate` : clé inconnue → `unknown_key` ; abonnement terminé → `expired` ; 1er et 2ᵉ PC → jeton ; 3ᵉ → `too_many_devices` avec les noms des 2 PC ; un PC vu il y a plus de 30 jours ne compte pas et est supprimé ; même PC réactivé → pas de nouvelle place ;
  - `/api/token` : PC non activé → `not_activated` ; met à jour `last_seen` ; déclenche le recalage ;
  - `/api/deactivate` → place libérée ;
  - corps invalide → 400.
- [x] Implémenter dans `src/activation.ts` (routes) + `src/licenses.ts` (D1).
- [x] Commit `add device activation endpoints`.

### Tâche 5 — Relais des fichiers et portail (spec §2.3)

- [x] Tests `files.test.ts` (GitHub simulé) :
  - sans en-tête, jeton faux ou expiré → 401 ;
  - `/updates/latest.json` → asset `latest.json` de la dernière Release publiée (API GitHub `releases/latest`, jeton GitHub) ;
  - `/updates/<installeur>` → l'asset du même nom de cette Release, en flux (pas de mise en mémoire de 60 Mo) ; nom inconnu → 404 ;
  - `/data/vinted-v1.json` → contenu de `main` ; `ETag` / `If-None-Match` transmis (le cache de l'app s'appuie dessus) ;
  - `/telecharger?cle=` → clé valide et abonnement valide → installeur ; sinon page d'erreur ;
  - `/api/portal` (jeton) → redirection vers une session du portail client Stripe.
- [x] Implémenter `src/files.ts` ; cache Cloudflare de 5 min sur `latest.json` et `vinted-v1.json`.
- [x] Écart : colonne `key_hash` (empreinte du jeton) ajoutée à `licenses` pour retrouver la licence depuis le jeton de `/api/portal`.
- [x] Commit `add authenticated file relay and billing portal`.

### Tâche 6 — Pages (spec §2.3)

- [x] Tests `pages.test.ts` : `/` contient le lien d'essai (`PAYMENT_LINK_URL`) et « Retrouver ma clé » ; `/merci?session_id=` affiche la clé (et la crée si le webhook n'est pas arrivé) ; session inconnue → page d'erreur ; `/retrouver` POST → même page de réponse que l'e-mail existe ou non, e-mail envoyé seulement s'il existe, 4ᵉ demande dans l'heure → pas d'e-mail ; `/aide` reprend la page d'aide.
- [x] Implémenter `src/pages.ts` (gabarit HTML commun, CSS en ligne, échappement systématique). `/aide` : contenu de `docs/aide/installation.md` converti au build (script `npm run build:aide`) et mis à jour (téléchargement via `/telecharger`).
- [x] Écarts : limite de `/retrouver` comptée par adresse e-mail seule (une rotation d'IP ne permet pas d'inonder une boîte) ; `src/aide.generated.ts` généré par `pretest` / `pretypecheck` / `deploy`, ignoré par git ; section « Clé de licence » ajoutée à la page d'aide.
- [x] Commit `add worker pages`.

### Tâche 7 — Déploiement (spec §5) — **avec l'utilisateur**

- [x] `.github/workflows/worker.yml` : sur push `main` touchant `worker/**` ou `docs/aide/**` : tests puis `wrangler d1 migrations apply --remote` et `wrangler deploy` (secrets `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`) ; sans jeton, seuls les tests tournent.
- [x] L'utilisateur : compte Cloudflare ; jeton API (Workers + D1) ajouté aux secrets GitHub ; `wrangler d1 create vto-licence` (l'identifiant va dans `wrangler.toml`).
- [x] Stripe **mode test** (l'utilisateur, guidé) : produit « Virtual Try-On », prix (montant à décider par l'utilisateur), essai 7 jours, Payment Link avec redirection `…/merci?session_id={CHECKOUT_SESSION_ID}`, portail client (résiliation, carte, factures), endpoint webhook `…/stripe/webhook` (événements de la tâche 3), relances de paiement sur 7 jours.
- [x] Resend : compte, clé API ; domaine plus tard (en test, Resend n'envoie qu'à l'adresse du compte — suffisant).
- [x] Jeton GitHub fine-grained (lecture seule, ce dépôt : Contents + Metadata ; Releases via Contents).
- [x] Secrets : `wrangler secret put` pour les 5 secrets ; clé de signature générée par `tools/make_signing_key.py`.
- [x] Garde ajoutée au déploiement : seuls les abonnements portant un prix de `STRIPE_PRICE_IDS` (`wrangler.toml`) créent ou modifient une licence ; session sans abonnement ignorée ; abonnement illisible → 500 (Stripe relance) ou page « Paiement introuvable » sur `/merci`. Compte Stripe dédié à Virtual Try-On (l'ancien compte porte une autre activité).
- [x] Vérifier : `/health`, `/`, un webhook de test envoyé depuis le tableau de bord Stripe → 200.
- [x] Déployé le 2026-10-13 sur `https://vto-licence.vto-licence.workers.dev` (D1 `vto-licence`, WEUR). Portail client créé par l'API (résiliation en fin de période, carte, factures). Achat de test : licence en essai, webhooks livrés. `/telecharger` répond 502 tant qu'aucune Release n'est publiée sur GitHub (le dépôt n'en a plus).
- [x] Commit `add worker deployment`.

## Partie B — App

### Tâche 8 — Clé et jeton (spec §3.1)

- [x] Dépendance `cryptography` (version stable vérifiée sur PyPI).
- [x] Tests `tests/licensing/test_key.py` : mêmes cas de normalisation que le Worker (tableau partagé `worker/test/fixtures/keys.json`).
- [x] Tests `test_token.py` : vecteur partagé de la tâche 2 vérifié ; signature fausse, `kid` inconnu, `dev` d'un autre PC, `exp` passé, statut expiré ; clés publiques injectables pour les tests.
- [x] Implémenter `licensing/__init__.py` (`LicenseError`), `key.py`, `token.py` (clé publique de production `k1` embarquée).
- [x] Clé de production `k1` générée : publique dans `token.py`, privée dans `.env` (ignoré par git) en attendant `wrangler secret put` (tâche 7).
- [x] Commit `add license key and token verification`.

### Tâche 9 — Client et état (spec §3.1)

- [x] Tests `test_license_client.py` : activate / refresh / deactivate (corps envoyés, erreurs `unknown_key`, `expired`, `too_many_devices`, `not_activated` traduites en `LicenseError` avec les messages de la spec §3.5 ; réseau en erreur → `LicenseUnreachable`).
- [x] Tests `test_state.py` :
  - `device_id` créé une fois et conservé ; `license.json` écrit de façon atomique ;
  - états `none` / `active` / `expired` / `unverified` (spec §3.1), y compris jeton valide + Worker injoignable → `active` ;
  - `not_activated` au rafraîchissement → réactivation silencieuse ;
  - thread : au démarrage puis toutes les 24 h (intervalle injecté), `stop()` ;
  - `VTO_DEV_LICENSE=1` → `active` hors exécutable, ignoré si `sys.frozen`.
- [x] Implémenter `client.py`, `state.py` ; URL de base `VTO_LICENSE_URL` sinon constante de production.
- [x] `DEFAULT_URL` provisoire (`https://vto-licence.workers.dev`) : à remplacer par l'URL réelle à la tâche 7. `paths.license_file()` ajouté. Refus autre qu'`expired` au rafraîchissement (ex. 2 PC déjà actifs lors d'une réactivation) : jeton conservé, message exposé dans `snapshot()["message"]`.
- [x] Commit `add license client and state`.

### Tâche 10 — Blocage de la génération et de l'envoi (spec §3.2)

- [x] Tests : `GenerationQueue.enqueue` lève `LicenseError` « Cette action demande un abonnement actif. » si le prédicat `licensed()` est faux ; régénération aussi ; `VintedWorker.send` idem (après le contrôle de mise à jour obligatoire) ; routes → 402 ; consultation des articles, scènes et réglages inchangée.
- [x] Prédicats injectés (`licensed=lambda: True` par défaut) ; câblage dans `desktop.py`.
- [x] En plus : la création d'un article (qui le met en file) est refusée avant d'écrire quoi que ce soit ; un article déjà en file quand l'abonnement s'arrête met la file en pause (raison affichée) sans perdre sa place.
- [x] Commit `require an active license to generate and send`.

### Tâche 11 — Mises à jour et `vinted.json` via le Worker (spec §3.3)

- [x] Tests : URL par défaut du manifeste et de `vinted.json` = Worker ; en-tête `Authorization: Bearer` envoyé quand un jeton valide existe (fournisseur de jeton injecté) ; sans jeton : pas de requête de manifeste (`unknown`), `vinted.json` depuis cache / copie embarquée sans requête ; téléchargement de l'installeur avec l'en-tête ; 401 du Worker → comme une indisponibilité (log).
- [x] `make_manifest.py --base-url` (défaut : URL du Worker) → `url` = `<base>/updates/<installeur>` ; tests mis à jour.
- [x] L'en-tête `Authorization` n'est envoyé qu'à l'origine du Worker (`licensing.client.bearer`) ; `VTO_UPDATE_URL` / `VTO_VINTED_DATA_URL` vers un autre hôte restent utilisables sans jeton. `make_manifest.py --repo` remplacé par `--base-url`.
- [x] Commit `fetch updates and vinted data through the license worker`.

### Tâche 12 — API (spec §3.4)

- [x] Tests `test_api_license.py` : `GET /api/license` (indice de clé `VTO-…-WXYZ`, jamais la clé entière) ; `POST` clé valide / mal formée / refusée ; `DELETE` ; `GET /api/license/portal` → URL ; sans gestionnaire → état `none`.
- [x] `routes/license.py` ; `create_app(..., license_manager=...)`.
- [x] `--self-check` : clé publique de production présente et valide.
- [x] Erreurs : refus → 400, Worker injoignable → 503 (le 402 reste pour les actions bloquées). Essai de fumée `vto-app --dev` avec Worker injoignable : OK.
- [x] Commit `add license routes`.

### Tâche 13 — Front (spec §3.4)

- [x] Types et appels API.
- [x] Tests Vitest : accueil → étape clé de licence avant la clé Gemini (route `welcome` tant que licence `none` ou clé Gemini absente) ; erreurs affichées ; lien d'essai ; section Licence (état, date, gérer l'abonnement, désactiver ce PC avec confirmation, changer de clé) ; bandeau `expired` / `unverified` ; boutons de génération et d'envoi désactivés hors `active` avec explication.
- [x] Implémenter (`WelcomeView.vue`, `LicenseSection.vue`, `LicenseBanner.vue`, garde du routeur).
- [x] En plus : `site_url` (Worker) exposé par `GET /api/license` pour les liens d'essai, de renouvellement et d'aide (le lien d'aide du bandeau de mise à jour pointait vers GitHub). Rendu vérifié dans Chrome (accueil, erreur Worker injoignable).
- [x] Commit `add license screens`.

## Partie C — Acceptation

### Tâche 14 — Bout en bout en mode test Stripe (spec §4, §7) — **avec l'utilisateur**

- [x] App en dev (`vto-app`, sans `VTO_DEV_LICENSE`) → Worker déployé (mode test) ; `DEFAULT_URL` pointe déjà dessus.
- [x] Achat par le Payment Link de test (carte 4242), e-mail reçu, `/merci` affiche la clé, activation dans l'app, génération, envoi Vinted.
- [x] Horloges de test Stripe (client, abonnement et cartes créés par l'API) : fin d'essai → `active` ; carte 4000 0000 0000 0341 au renouvellement → `past_due` (message « Le dernier paiement a échoué… », génération et envoi encore permis) → `canceled` (« Ton abonnement est terminé. », génération et envoi refusés, articles consultables) ; nouvel abonnement du même client → même clé, débloqué.
- [x] 3ᵉ PC refusé (`too_many_devices`, 409, noms des 2 PC dans le message) ; désactivation puis activation ailleurs ; Worker coupé (`VTO_LICENSE_URL=http://127.0.0.1:9`) → reste `active`, génération OK, « jeton conservé » dans le log.
- [x] Écarts constatés :
  - Relances Stripe : par défaut ~2 semaines et 9 tentatives, puis un délai de 7 jours avant l'action finale (l'abonnement restait `past_due`, donc utilisable sans payer). Réglé par l'utilisateur : 7 jours puis résiliation, vérifié par horloge (`canceled` à J+8). **À reproduire à l'identique en production.**
  - Portail client absent du nouveau compte : créé par l'API (tâche 7). À recréer en production.
  - Passage à `unverified` à l'expiration du jeton non essayé en réel (jeton de 7 jours, pas de jeton court) : couvert par `backend/tests/licensing/test_state.py`.
  - Réabonnement essayé sur le même client Stripe (API) : même clé. Par le Payment Link, un ancien client devient un nouveau client Stripe → **nouvelle clé** → corrigé : `GET /renouveler?cle=` (page avec bouton) puis `POST /renouveler` crée une Checkout Session sur le client existant, au premier prix de `STRIPE_PRICE_IDS`, sans essai, retour par `/merci` (même clé) ; l'app ouvre cette page par `GET /api/license/renew` depuis le bandeau et l'écran Licence. Vérifié en réel : abonnement résilié → « Renouveler » → paiement 4242 → même clé, app débloquée.
  - Une licence créée par `customer.subscription.created` sans paiement Checkout n'a pas d'e-mail (abonnements créés par l'API uniquement ; le parcours réel passe toujours par Checkout).
  - L'app ne relit la licence qu'au démarrage puis toutes les 24 h : un changement de statut apparaît au plus tard le lendemain (ou à la relance de l'app). Conforme à la spec.
  - `/telecharger` en 502 : aucune Release publiée sur GitHub (à régler par la 0.3.0, tâche 15).

### Tâche 15 — Mise en production et migration (spec §6) — **avec l'utilisateur**

- [ ] Stripe Managed Payments activé en production (éligibilité confirmée), mêmes réglages qu'en test ; secrets de production. (Fait le 2026-10-13 : domaine `kaloe.fr` chez IONOS, DNS sur Cloudflare, Worker en domaine personnalisé, Resend vérifié, expéditeur `licence@kaloe.fr`, routage `licence@`/`contact@` vers Gmail ; `PUBLIC_BASE_URL`, `DEFAULT_URL` de l'app et URLs Stripe de test sur `https://kaloe.fr`. En production, recréer le webhook, le Payment Link et le portail avec ces URLs.)
- [ ] Release **0.3.0** ; installation via `/telecharger` avec une licence offerte (code promo 100 %).
- [ ] Mise à jour 0.3.0 → 0.3.1 via le Worker.
- [ ] L'utilisateur passe le dépôt en **privé** ; vérifier : CI, `release.yml`, relais du Worker (`latest.json`, installeur, `vinted-v1.json`) toujours OK.
- [ ] `CLAUDE.md` : décisions produit (abonnement, dépôt privé), roadmap, commandes du Worker, procédure de publication.
- [ ] Premier achat réel par l'utilisateur, puis remboursement depuis Stripe.
- [ ] Statut du sous-projet 5 à ✅.

---

## Points nécessitant l'utilisateur

- Tâche 7 : comptes Cloudflare, Stripe (mode test), Resend ; jeton GitHub ; prix de l'abonnement.
- Tâche 14 : achat de test et vérifications dans l'app.
- Tâche 15 : Managed Payments en production, nom de domaine, passage du dépôt en privé, achat réel.
