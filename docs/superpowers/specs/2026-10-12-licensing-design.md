# Sous-projet 5 — Licence — Design

Date : 2026-10-12
Statut : validé en brainstorming, en attente de relecture

## 1. Contexte

Le sous-projet 4 a livré l'installeur, la mise à jour en un clic et la chaîne de publication ; l'URL du manifeste (`VTO_UPDATE_URL`) et celle de `vinted.json` (`VTO_VINTED_DATA_URL`) sont déjà configurables. Rien ne limite encore l'usage : le dépôt, les Releases et `vinted.json` sont publics. Ce sous-projet ajoute la vente par abonnement et la licence qui conditionne l'usage de l'app.

### 1.1 Décisions (prises en brainstorming)

| Sujet | Décision |
|---|---|
| Modèle | **Abonnement pour tout le monde** (remplace « achat unique + 12 mois de MAJ » de la roadmap) |
| Fin d'abonnement | L'app s'ouvre ; consultation et export des articles possibles ; **génération et envoi Vinted bloqués** |
| Vérification | Jeton Ed25519 signé par le Worker, valable jusqu'à la fin de la période payée et **au plus 7 jours** ; vérifié hors ligne par l'app ; rafraîchi au démarrage puis toutes les 24 h |
| Plateforme | **Stripe Managed Payments** (Stripe vendeur officiel : TVA, conformité). Paddle en repli si l'éligibilité coince : l'app n'en dépend pas |
| Identification | **Clé de licence** `VTO-XXXX-XXXX-XXXX-XXXX` affichée après paiement et envoyée par e-mail ; page « Retrouver ma clé » ; **2 PC** par clé, place libérée après 30 jours sans activité |
| Essai | **7 jours via Stripe**, carte demandée ; licence active pendant l'essai |
| Dépôt | **Passe en privé** ; le Worker est le seul accès aux installeurs, manifestes et `vinted.json` |
| Hébergement | **Cloudflare Worker + D1** ; Stripe fait référence, le Worker suit par webhooks et se recale sur l'API |

Approches écartées : un abonnement qui ne coupe que les mises à jour (C de la question 1, abandonnée avec l'achat unique) ; app entièrement bloquée à la fin de l'abonnement (données prises en otage) ; vérification en ligne à chaque action (une panne du Worker bloque tout le monde) ; date de fin vérifiée une fois par mois (remboursement sans effet pendant un mois) ; Lemon Squeezy (absorbé par Stripe, avenir des licences incertain) ; Polar (jeune, réorienté vers la facturation à l'usage) ; Paddle (gardé en repli) ; e-mail + code à chaque connexion ; essai sans carte (anti-abus coûteux) ; dépôt public (code lisible, contournement trivial) ; Worker sans base (activations sans stockage) ; KV (écritures éventuellement cohérentes : 3ᵉ activation possible) ; backend classique.

### 1.2 Hors périmètre

- Site vitrine au-delà d'une page d'accueil simple ; plusieurs formules ; affiliation.
- Interface d'administration : tableau de bord Stripe (clients, remboursements, codes promo) et console D1 suffisent.
- Comptes clients, connexion par e-mail.
- Paiement lancé depuis l'app (pourra s'ajouter par-dessus la clé).
- Protection de l'exécutable contre la modification (anti-piratage volontairement léger : le Worker refuse quand même fichiers et `vinted.json` sans jeton valide).

## 2. Architecture

### 2.1 Arborescence

```
worker/                           Cloudflare Worker (TypeScript)
  wrangler.toml                   D1, routes, variables non secrètes
  schema.sql                      tables licenses, activations, events, recover_requests
  src/index.ts                    routeur
  src/stripe.ts                   webhooks (signature), recalage via l'API Stripe
  src/licenses.ts                 clés, statut, activations
  src/tokens.ts                   signature Ed25519
  src/files.ts                    relais vers le dépôt privé (jeton GitHub en lecture seule)
  src/email.ts                    e-mail de la clé (Resend)
  src/pages.ts                    pages HTML : accueil, merci, retrouver, télécharger, aide
  test/                           Vitest + @cloudflare/vitest-pool-workers
.github/workflows/worker.yml      tests + `wrangler deploy` quand worker/ change sur main
tools/make_signing_key.py         génère la paire Ed25519 (privée → secret Cloudflare)

backend/src/vto/licensing/        nouveau paquet ; dépend de core, jamais l'inverse
  __init__.py                     LicenseError (VtoError)
  key.py                          format, normalisation (espaces, minuscules, tirets)
  token.py                        vérification Ed25519, clés publiques embarquées par identifiant
  client.py                       activate / refresh / deactivate auprès du Worker
  state.py                        LicenseManager : état, rafraîchissement, persistance
backend/src/vto/api/routes/license.py
frontend/src/components/LicenseSection.vue, LicenseBanner.vue ; WelcomeView.vue complété
```

### 2.2 Données du Worker (D1)

```sql
licenses(key TEXT PRIMARY KEY, email TEXT, stripe_customer TEXT UNIQUE, stripe_subscription TEXT,
         status TEXT, period_end INTEGER, synced_at INTEGER, created_at INTEGER)
activations(key TEXT, device_id TEXT, device_name TEXT, last_seen INTEGER, PRIMARY KEY(key, device_id))
events(id TEXT PRIMARY KEY, received_at INTEGER)          -- idempotence des webhooks Stripe
recover_requests(ip_email_hash TEXT, at INTEGER)           -- limite de fréquence de /retrouver
```

- Clé : 16 caractères de l'alphabet Crockford (sans I, L, O, U), groupés par 4, préfixe `VTO-` ; générée par `crypto.getRandomValues`.
- Une licence par client Stripe : un nouvel abonnement du même client reprend la même clé.

### 2.3 Routes du Worker

| Route | Rôle |
|---|---|
| `GET /` | Page d'accueil : offre, bouton « Essayer 7 jours » (Payment Link Stripe), lien « Retrouver ma clé » |
| `POST /stripe/webhook` | Signature vérifiée ; `checkout.session.completed` → licence créée ou reprise, e-mail envoyé ; `customer.subscription.created/updated/deleted` → statut et `period_end` ; événement déjà reçu → 200 sans effet |
| `GET /merci?session_id=` | Lit la session Stripe, affiche la clé et le lien de téléchargement (la licence est créée ici si le webhook n'est pas encore arrivé) |
| `GET /telecharger?cle=` | Clé valide → redirige vers le dernier installeur (relais GitHub) |
| `GET /retrouver`, `POST /retrouver` | Formulaire e-mail ; si une licence existe, la clé est renvoyée par e-mail ; réponse identique dans tous les cas ; 3 demandes par heure et par adresse |
| `GET /aide` | Page d'aide installation (reprend `docs/aide/installation.md`, le dépôt devenant privé) |
| `POST /api/activate` | `{key, device_id, device_name}` → jeton, ou erreur (clé inconnue, abonnement terminé, 2 PC déjà actifs) |
| `POST /api/token` | `{key, device_id}` → jeton rafraîchi ; PC non activé → erreur `not_activated` |
| `POST /api/deactivate` | `{key, device_id}` → libère la place |
| `GET /api/portal` | `Authorization: Bearer <jeton>` → redirection vers une session du portail client Stripe |
| `GET /updates/latest.json`, `GET /updates/<installeur>`, `GET /data/vinted-v<N>.json` | `Authorization: Bearer <jeton>` valide et non expiré → relais du fichier GitHub (Release publiée la plus récente / fichier de `main`) ; sinon 401 |

Statuts Stripe valides : `trialing`, `active`, `past_due` (Stripe retente le paiement). `canceled`, `unpaid`, `incomplete_expired`, `paused` → licence expirée.

Recalage : à l'émission d'un jeton, si `synced_at` date de plus de 24 h, le Worker relit l'abonnement dans l'API Stripe (rattrape un webhook perdu). Si Stripe ne répond pas, il se fie à D1.

Activations : une activation dont `last_seen` date de plus de 30 jours ne compte plus dans la limite de 2 et est supprimée à la prochaine activation. `last_seen` est mis à jour à chaque jeton.

### 2.4 Jeton

```json
{"v": 1, "kid": "k1", "lic": "<sha256 de la clé, 16 hex>", "dev": "<device_id>",
 "status": "active", "period_end": 1793000000, "exp": 1792500000, "iat": 1791900000}
```

- Encodage : `base64url(payload) + "." + base64url(signature Ed25519)`.
- `exp = min(period_end, iat + 7 jours)`.
- La clé privée est un secret Cloudflare ; l'app embarque les clés publiques par `kid`, ce qui permet d'en changer sans casser les versions installées.

## 3. App

### 3.1 `vto.licensing`

- **Persistance** : `<données>/license.json` = `{key, device_id, token}`. `device_id` (UUID4) est créé une fois ; il survit à une réinstallation (dossier de données conservé).
- **État** (`LicenseManager.state()`) :
  - `none` : aucune clé saisie ;
  - `active` : jeton valide (signature, `dev` = ce PC, `exp` futur, statut valide) ;
  - `expired` : le Worker a répondu « abonnement terminé », ou le jeton porte un statut expiré ;
  - `unverified` : jeton expiré ou absent et Worker injoignable.
- **Rafraîchissement** : au démarrage puis toutes les 24 h, dans un thread (comme `UpdateChecker`) ; Worker injoignable → jeton conservé tant qu'il est valide.
- **Contournement de développement** : `VTO_DEV_LICENSE=1` → `active`, **uniquement si `paths.is_frozen()` est faux** ; l'exécutable l'ignore.
- **Dépendance** : `cryptography` (Ed25519).

### 3.2 Ce qui est bloqué

- `GenerationQueue.enqueue` et `VintedWorker.send` refusent hors `active` (`LicenseError`, 402 côté API), avec un prédicat injecté comme `update_required`.
- Restent possibles : ouvrir l'app, consulter et exporter les articles, gérer les scènes et les réglages, saisir ou changer la clé.

### 3.3 Mises à jour et `vinted.json`

- URL par défaut du manifeste : `https://<worker>/updates/latest.json` ; de `vinted.json` : `https://<worker>/data/vinted-v{FORMAT}.json`.
- `fetch_manifest`, le téléchargement de l'installeur et `load_vinted_data` envoient `Authorization: Bearer <jeton>` quand un jeton valide existe.
- Sans jeton : pas de vérification de mise à jour (état `unknown`, pas de bandeau) ; `vinted.json` depuis le cache puis la copie embarquée.
- `make_manifest.py` écrit une `url` vers le Worker (`/updates/<installeur>`).

### 3.4 API et front

- `GET /api/license` → `{state, key_hint, period_end, status, devices_max}` ; `POST /api/license` `{key}` → activation ; `DELETE /api/license` → désactivation de ce PC ; `GET /api/license/portal` → URL du portail Stripe.
- **Écran d'accueil** : étape « Clé de licence » avant la clé Gemini ; lien « Pas encore de clé ? Essayer 7 jours » vers la page d'accueil du Worker.
- **Réglages → Licence** : état, date de renouvellement, « Gérer mon abonnement » (portail), « Désactiver ce PC », changer de clé.
- **Bandeau** (même emplacement que celui des mises à jour) : `expired` → « Ton abonnement est terminé — Renouveler » ; `unverified` → « Impossible de vérifier ton abonnement. Vérifie ta connexion Internet. »

### 3.5 Messages

| Cas | Message |
|---|---|
| Clé mal formée | « Cette clé n'a pas le bon format. Elle ressemble à VTO-XXXX-XXXX-XXXX-XXXX. » |
| Clé inconnue | « Cette clé de licence n'existe pas. Vérifie-la dans l'e-mail reçu après l'achat. » |
| Abonnement terminé | « Ton abonnement est terminé. Renouvelle-le pour continuer à générer et à envoyer sur Vinted. » |
| 2 PC déjà actifs | « Ta clé est déjà utilisée sur 2 PC (noms). Désactive-la sur l'un d'eux, ou attends 30 jours sans utilisation. » |
| Worker injoignable, jeton expiré | « Impossible de vérifier ton abonnement. Vérifie ta connexion Internet. » |
| Action bloquée | « Cette action demande un abonnement actif. » + lien Renouveler |
| Signature invalide | (aucun message) jeton ignoré, nouvelle activation silencieuse avec la clé enregistrée |

## 4. Tests

- **Worker** (Vitest, D1 locale, Stripe / Resend / GitHub simulés) : signature et rejeu des webhooks ; création, reprise par client, changements de statut ; `/merci` avant le webhook ; activations, limite, libération à 30 jours ; jeton (contenu, `exp`, signature) ; relais refusé sans jeton, avec jeton expiré ou falsifié ; `/retrouver` sans énumération et limité ; recalage Stripe après 24 h.
- **App** : jetons de test signés avec une clé de test (`kid` de test injecté) ; `key` (normalisation) ; `client` (`MockTransport`) ; transitions d'`état` ; contournement de dev refusé si `sys.frozen` ; refus dans la file et l'envoi Vinted ; routes `/api/license` ; en-tête `Authorization` sur manifeste, installeur et `vinted.json`.
- **Front** (Vitest) : étape clé de l'accueil, section Licence, bandeau.
- **Bout en bout, mode test Stripe** : Payment Link de test → carte 4242 → e-mail → activation dans l'app → génération ; horloges de test Stripe pour la fin d'essai, un paiement refusé (`past_due` puis `unpaid`) et la résiliation ; 3ᵉ PC refusé ; `stripe listen` vers `wrangler dev` en local.

## 5. Déploiement

- Comptes : Cloudflare (gratuit), Stripe (Managed Payments à activer, éligibilité à vérifier), Resend, **nom de domaine** (requis par Resend pour écrire aux clients).
- Secrets Cloudflare : `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `TOKEN_PRIVATE_KEY`, `GITHUB_TOKEN` (fine-grained, lecture seule, ce seul dépôt : contenus et Releases), `RESEND_API_KEY`. Secret GitHub Actions : `CLOUDFLARE_API_TOKEN`.
- Le Worker démarre sur `*.workers.dev`, puis passe sur le domaine ; l'URL de base est une constante de l'app (surchargeable par `VTO_LICENSE_URL`).
- Licences offertes : code promo Stripe à 100 %.

## 6. Migration

1. Worker en service, relayant le dépôt encore public.
2. Version **0.3.0** : licence, URLs vers le Worker.
3. L'utilisateur installe la 0.3.0 via `/telecharger` et active une licence offerte.
4. L'utilisateur passe le dépôt en **privé** ; les 0.2.x (poste de l'utilisateur et d'un ami) ne reçoivent plus rien.
5. `CLAUDE.md` : modèle par abonnement dans les décisions produit, dépôt privé, roadmap, commandes du Worker.

## 7. Acceptation

- Achat en mode test Stripe de bout en bout, e-mail reçu, activation, génération et envoi Vinted.
- Fin d'essai et résiliation simulées (horloges de test) → bandeau, génération et envoi bloqués, articles consultables.
- 3ᵉ PC refusé ; désactivation puis activation ailleurs.
- Worker coupé : l'app continue avec un jeton valide, puis passe en `unverified` après expiration.
- Mise à jour 0.3.0 → 0.3.1 via le Worker ; dépôt privé ; `vinted.json` servi par le Worker.
- Premier achat réel (mode production) par l'utilisateur, remboursé ensuite.
