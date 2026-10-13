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

- [ ] Tests `activation.test.ts` :
  - `/api/activate` : clé inconnue → `unknown_key` ; abonnement terminé → `expired` ; 1er et 2ᵉ PC → jeton ; 3ᵉ → `too_many_devices` avec les noms des 2 PC ; un PC vu il y a plus de 30 jours ne compte pas et est supprimé ; même PC réactivé → pas de nouvelle place ;
  - `/api/token` : PC non activé → `not_activated` ; met à jour `last_seen` ; déclenche le recalage ;
  - `/api/deactivate` → place libérée ;
  - corps invalide → 400.
- [ ] Implémenter dans `src/index.ts` + `src/licenses.ts`.
- [ ] Commit `add device activation endpoints`.

### Tâche 5 — Relais des fichiers et portail (spec §2.3)

- [ ] Tests `files.test.ts` (GitHub simulé) :
  - sans en-tête, jeton faux ou expiré → 401 ;
  - `/updates/latest.json` → asset `latest.json` de la dernière Release publiée (API GitHub `releases/latest`, jeton GitHub) ;
  - `/updates/<installeur>` → l'asset du même nom de cette Release, en flux (pas de mise en mémoire de 60 Mo) ; nom inconnu → 404 ;
  - `/data/vinted-v1.json` → contenu de `main` ; `ETag` / `If-None-Match` transmis (le cache de l'app s'appuie dessus) ;
  - `/telecharger?cle=` → clé valide et abonnement valide → installeur ; sinon page d'erreur ;
  - `/api/portal` (jeton) → redirection vers une session du portail client Stripe.
- [ ] Implémenter `src/files.ts` ; cache Cloudflare de 5 min sur `latest.json` et `vinted-v1.json`.
- [ ] Commit `add authenticated file relay and billing portal`.

### Tâche 6 — Pages (spec §2.3)

- [ ] Tests `pages.test.ts` : `/` contient le lien d'essai (`PAYMENT_LINK_URL`) et « Retrouver ma clé » ; `/merci?session_id=` affiche la clé (et la crée si le webhook n'est pas arrivé) ; session inconnue → page d'erreur ; `/retrouver` POST → même page de réponse que l'e-mail existe ou non, e-mail envoyé seulement s'il existe, 4ᵉ demande dans l'heure → pas d'e-mail ; `/aide` reprend la page d'aide.
- [ ] Implémenter `src/pages.ts` (gabarit HTML commun, CSS en ligne, échappement systématique). `/aide` : contenu de `docs/aide/installation.md` converti au build (script `npm run build:aide`) et mis à jour (téléchargement via `/telecharger`).
- [ ] Commit `add worker pages`.

### Tâche 7 — Déploiement (spec §5) — **avec l'utilisateur**

- [ ] `.github/workflows/worker.yml` : sur push `main` touchant `worker/**` : tests puis `wrangler d1 migrations apply --remote` et `wrangler deploy` (secret `CLOUDFLARE_API_TOKEN`).
- [ ] L'utilisateur : compte Cloudflare ; jeton API (Workers + D1) ajouté aux secrets GitHub ; `wrangler d1 create vto-licence` (l'identifiant va dans `wrangler.toml`).
- [ ] Stripe **mode test** (l'utilisateur, guidé) : produit « Virtual Try-On », prix (montant à décider par l'utilisateur), essai 7 jours, Payment Link avec redirection `…/merci?session_id={CHECKOUT_SESSION_ID}`, portail client (résiliation, carte, factures), endpoint webhook `…/stripe/webhook` (événements de la tâche 3), relances de paiement sur 7 jours.
- [ ] Resend : compte, clé API ; domaine plus tard (en test, Resend n'envoie qu'à l'adresse du compte — suffisant).
- [ ] Jeton GitHub fine-grained (lecture seule, ce dépôt : Contents + Metadata ; Releases via Contents).
- [ ] Secrets : `wrangler secret put` pour les 5 secrets ; clé de signature générée par `tools/make_signing_key.py`.
- [ ] Vérifier : `/health`, `/`, un webhook de test envoyé depuis le tableau de bord Stripe → 200.
- [ ] Commit `add worker deployment`.

## Partie B — App

### Tâche 8 — Clé et jeton (spec §3.1)

- [ ] Dépendance `cryptography` (version stable vérifiée sur PyPI).
- [ ] Tests `tests/licensing/test_key.py` : mêmes cas de normalisation que le Worker (tableau partagé `worker/test/fixtures/keys.json`).
- [ ] Tests `test_token.py` : vecteur partagé de la tâche 2 vérifié ; signature fausse, `kid` inconnu, `dev` d'un autre PC, `exp` passé, statut expiré ; clés publiques injectables pour les tests.
- [ ] Implémenter `licensing/__init__.py` (`LicenseError`), `key.py`, `token.py` (clé publique de production `k1` embarquée).
- [ ] Commit `add license key and token verification`.

### Tâche 9 — Client et état (spec §3.1)

- [ ] Tests `test_client.py` : activate / refresh / deactivate (corps envoyés, erreurs `unknown_key`, `expired`, `too_many_devices`, `not_activated` traduites en `LicenseError` avec les messages de la spec §3.5 ; réseau en erreur → `LicenseUnreachable`).
- [ ] Tests `test_state.py` :
  - `device_id` créé une fois et conservé ; `license.json` écrit de façon atomique ;
  - états `none` / `active` / `expired` / `unverified` (spec §3.1), y compris jeton valide + Worker injoignable → `active` ;
  - `not_activated` au rafraîchissement → réactivation silencieuse ;
  - thread : au démarrage puis toutes les 24 h (intervalle injecté), `stop()` ;
  - `VTO_DEV_LICENSE=1` → `active` hors exécutable, ignoré si `sys.frozen`.
- [ ] Implémenter `client.py`, `state.py` ; URL de base `VTO_LICENSE_URL` sinon constante de production.
- [ ] Commit `add license client and state`.

### Tâche 10 — Blocage de la génération et de l'envoi (spec §3.2)

- [ ] Tests : `GenerationQueue.enqueue` lève `LicenseError` « Cette action demande un abonnement actif. » si le prédicat `licensed()` est faux ; régénération aussi ; `VintedWorker.send` idem (après le contrôle de mise à jour obligatoire) ; routes → 402 ; consultation des articles, scènes et réglages inchangée.
- [ ] Prédicats injectés (`licensed=lambda: True` par défaut) ; câblage dans `desktop.py`.
- [ ] Commit `require an active license to generate and send`.

### Tâche 11 — Mises à jour et `vinted.json` via le Worker (spec §3.3)

- [ ] Tests : URL par défaut du manifeste et de `vinted.json` = Worker ; en-tête `Authorization: Bearer` envoyé quand un jeton valide existe (fournisseur de jeton injecté) ; sans jeton : pas de requête de manifeste (`unknown`), `vinted.json` depuis cache / copie embarquée sans requête ; téléchargement de l'installeur avec l'en-tête ; 401 du Worker → comme une indisponibilité (log).
- [ ] `make_manifest.py --base-url` (défaut : URL du Worker) → `url` = `<base>/updates/<installeur>` ; tests mis à jour.
- [ ] Commit `fetch updates and vinted data through the license worker`.

### Tâche 12 — API (spec §3.4)

- [ ] Tests `test_api_license.py` : `GET /api/license` (indice de clé `VTO-…-WXYZ`, jamais la clé entière) ; `POST` clé valide / mal formée / refusée ; `DELETE` ; `GET /api/license/portal` → URL ; sans gestionnaire → état `none`.
- [ ] `routes/license.py` ; `create_app(..., license_manager=...)`.
- [ ] `--self-check` : clé publique de production présente et valide.
- [ ] Commit `add license routes`.

### Tâche 13 — Front (spec §3.4)

- [ ] Types et appels API.
- [ ] Tests Vitest : accueil → étape clé de licence avant la clé Gemini (route `welcome` tant que licence `none` ou clé Gemini absente) ; erreurs affichées ; lien d'essai ; section Licence (état, date, gérer l'abonnement, désactiver ce PC avec confirmation, changer de clé) ; bandeau `expired` / `unverified` ; boutons de génération et d'envoi désactivés hors `active` avec explication.
- [ ] Implémenter (`WelcomeView.vue`, `LicenseSection.vue`, `LicenseBanner.vue`, garde du routeur).
- [ ] Commit `add license screens`.

## Partie C — Acceptation

### Tâche 14 — Bout en bout en mode test Stripe (spec §4, §7) — **avec l'utilisateur**

- [ ] App en dev avec `VTO_LICENSE_URL` → Worker déployé (mode test).
- [ ] Achat par le Payment Link de test (carte 4242), e-mail reçu, `/merci` affiche la clé, activation dans l'app, génération, envoi Vinted.
- [ ] Horloges de test Stripe : fin d'essai → `active` ; paiement refusé (carte 4000 0000 0000 0341) → `past_due` puis `unpaid` → bandeau, génération et envoi refusés, articles consultables ; réabonnement → même clé, débloqué.
- [ ] 3ᵉ PC refusé (troisième `device_id` simulé) ; désactivation ; Worker coupé (`VTO_LICENSE_URL` injoignable) → `active` puis `unverified` à l'expiration du jeton (jeton de test court).
- [ ] Noter dans ce plan les écarts constatés.

### Tâche 15 — Mise en production et migration (spec §6) — **avec l'utilisateur**

- [ ] Stripe Managed Payments activé en production (éligibilité confirmée), mêmes réglages qu'en test ; secrets de production ; domaine + Resend vérifié ; `PUBLIC_BASE_URL` et constante de l'app sur le domaine.
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
