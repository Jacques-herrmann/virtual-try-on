# Kaloé — CLAUDE.md

**Kaloé** (anciennement Virtual Try-On ; package Python `vto`) : outil pour vendeurs Vinted : à partir d'une photo de vêtement, génère des photos « portées » (mannequin, cintre…) et une annonce via Gemini, puis crée les brouillons Vinted. Prototype personnel en cours de transformation en produit vendu à des vendeurs non techniques.

## Roadmap

| # | Sous-projet | Statut | Spec / plan |
|---|---|---|---|
| 1 | **Cœur propre** — package `vto`, config, stockage, scènes, génération, pipeline, CLI de dev, import du proto, tests + CI | ✅ terminé le 2026-10-12 sur `main` — validé de bout en bout par l'essai réel du sous-projet 3 | `docs/superpowers/specs/2026-10-10-core-clean-design.md`, `docs/superpowers/plans/2026-10-10-core-clean.md` |
| 2 | **App** — API FastAPI + UI Vue/Vite dans une fenêtre `pywebview` ; saisie article par article, écran de relecture | ✅ terminé le 2026-10-12 sur `main` — validé de bout en bout par l'essai réel du sous-projet 3 | `docs/superpowers/specs/2026-10-10-app-design.md`, `docs/superpowers/plans/2026-10-10-app.md` |
| 3 | **Vinted** — profil Chrome persistant (aucun mot de passe stocké), sélecteurs dans un JSON distant, remplissage complet du formulaire | ✅ terminé le 2026-10-12 sur `main` — essai réel fait (brouillons, lot, publication, 3 relances sans reconnexion, `pytest -m live_vinted`) ; catalogue complet relevé (783 feuilles, 26 grilles de tailles) ; `data/vinted.json` publié | `docs/superpowers/specs/2026-10-10-vinted-design.md`, `docs/superpowers/plans/2026-10-10-vinted.md` |
| 4 | **Distribution** — PyInstaller, installeur Inno Setup, mise à jour en un clic, signature de code (plus tard) | 🟡 implémenté sur `main`, v0.2.2 publiée — mise à jour en un clic et mise à jour obligatoire validées sur le poste le 2026-10-12 ; reste l'essai d'installation chez un ami | `docs/superpowers/specs/2026-10-12-distribution-design.md`, `docs/superpowers/plans/2026-10-12-distribution.md` |
| 5 | **Licence** — abonnement pour tout le monde (essai 7 jours), Stripe Managed Payments ; clé de licence, 2 PC ; Worker Cloudflare + D1 qui délivre des jetons signés et seul accès aux MAJ et sélecteurs ; dépôt privé | 🟡 code fait sur `main` (tâches 0–6 et 8–13 : Worker testé, app, front) ; Worker déployé le 2026-10-13 (tâche 7, `https://vto-licence.vto-licence.workers.dev`, compte Stripe dédié en mode test) ; essai de bout en bout en mode test validé (14) ; page `/renouveler` (réabonnement, même clé) ajoutée ; reste avec l'utilisateur : mise en production et dépôt privé (15) | `docs/superpowers/specs/2026-10-12-licensing-design.md`, `docs/superpowers/plans/2026-10-12-licensing.md` |
| 6 | **Marque & UI** — nom **Kaloé**, DA chaleureuse (abricot/crème), refonte des écrans, site et e-mails du Worker, renommage complet (exe, installeur, dossiers) avec migration des données | 🟡 spec et plan écrits le 2026-10-13 ; tâches 0–12 faites sur `main` (marque, migration, installeur, CI, thème, écrans, Worker, aide) ; reste l'essai réel (13) : préversion `v0.3.0rc1` puis mise à jour depuis la v0.2.2 du poste, et le déploiement du Worker | `docs/superpowers/specs/2026-10-13-brand-design.md`, `docs/superpowers/plans/2026-10-13-brand.md` |

Ordre : 1 → 2 → 3 → 4 → 5 → 6. Chaque sous-projet suit le cycle brainstorming → spec → plan → implémentation. Mettre à jour le statut ci-dessus à chaque étape.

## Décisions produit (ne pas re-discuter sans raison)

- Cible : vendeurs non techniques, app desktop Windows ; SaaS possible plus tard → le cœur ne dépend d'aucune interface.
- Clé Gemini fournie par le client (BYOK).
- Automatisation Vinted = fonctionnalité phare, à fiabiliser.
- Scène = dossier de décors + `prompt.md` modifiable ; pack par défaut + scènes du client.
- Relecture obligatoire avant envoi sur Vinted.
- Fichier de sélecteurs distant = données uniquement, jamais de code exécuté.
- Anti-piratage volontairement léger.

## Règles d'architecture

- `vto.core` n'importe jamais `cli`, `tools`, `api`, `vinted`, `licensing`, `updates`. Dépendances toujours vers `core`.
- Aucun secret ni chemin absolu dans le code. Chemins utilisateur uniquement via `vto.core.paths` (racine `%LOCALAPPDATA%\Kaloe`, surchargeable par `VTO_DATA_DIR` ; l'ancien `%LOCALAPPDATA%\VirtualTryOn` est renommé au premier lancement par `paths.migrate_legacy_data_dir`).
- Gemini uniquement via le protocole `GenAIClient` ; les tests utilisent `FakeClient`, jamais le réseau (sauf `pytest -m live`).
- Messages d'erreur destinés au client final : en français, sans jargon ; détails techniques dans le log.
- Les données du client (articles, scènes) ne sont jamais supprimées implicitement.

## Commandes

```
pip install -e backend[dev,build]   # build = PyInstaller ; réinstaller après un changement de version
pytest backend/tests             # sans réseau
pytest backend/tests -m live     # nécessite GEMINI_API_KEY
pytest backend/tests -m browser  # pilote un navigateur (Chrome installé ou `playwright install chromium`)
pytest backend/tests -m live_vinted  # crée puis efface un vrai brouillon (profil Vinted connecté)
ruff check backend

vto-vinted-catalog               # relève le catalogue Vinted (~1 h, reprenable) et réécrit data/vinted-v1.json ;
                                 # recopier ensuite dans backend/src/vto/vinted/data/vinted.json

cd frontend && npm ci            # Node ≥ 22.12 (nvm-windows sur le poste de dev)
node scripts/icons.mjs           # régénère src/icons.css après ajout d'une icône Lucide
npm test                         # Vitest
npm run build                    # compile dans backend/src/vto/api/static (ignoré par git)

cd worker && npm ci              # Worker de licence (Cloudflare) ; Node ≥ 22.12
npm test                         # Vitest dans workerd, D1 locale, Stripe/Resend/GitHub simulés
npm run typecheck
npm run dev                      # wrangler dev (secrets dans worker/.dev.vars)
python tools/make_signing_key.py k2  # nouvelle clé de signature des jetons (privée → secret Cloudflare)

python brand/make_logo.py        # logo vectorisé depuis la police (fonttools + brotli)
python packaging/make_icon.py    # icon.ico + favicon depuis brand/app-icon.svg (Playwright)

vto-app                          # application complète (fenêtre pywebview)
vto-app --dev                    # API seule sur 127.0.0.1:8765, puis `npm run dev` et
                                 # http://localhost:5173/api/session?token=dev
                                 # VTO_DEV_LICENSE=1 : licence « active » hors exécutable ;
                                 # VTO_LICENSE_URL : autre Worker (ex. http://127.0.0.1:8787)
vto-app --self-check --output f  # test de fumée (modules, front, données, scènes, pilote Playwright)

# Empaquetage local (après npm run build) ; Inno Setup 6 : winget install JRSoftware.InnoSetup
pyinstaller packaging/vto.spec --noconfirm          # → dist/Kaloe/ (mode dossier)
powershell -File packaging/fetch_redist.ps1         # bootstrapper WebView2 (non versionné)
iscc /DAppVersion=X.Y.Z packaging/installer.iss     # → packaging/Output/Kaloe-Setup-X.Y.Z.exe
```

## Publier une version

1. Monter `__version__` dans `backend/src/vto/__init__.py` (PEP 440 : `0.3.0`, `0.3.0rc1`), commit, push sur `main`.
2. Si une ancienne version ne doit plus envoyer sur Vinted : monter `packaging/minimum_version.txt`.
3. `git tag -a vX.Y.Z` — le message du tag devient les notes « Nouveautés » (en français, pour le vendeur) — puis `git push origin vX.Y.Z`.
4. `release.yml` construit, teste (exécutable, installation, désinstallation) et crée une Release **brouillon** avec l'installeur et `latest.json`. Une préversion (`rc`) est marquée *prerelease* et n'est jamais proposée aux apps.
5. Essayer l'installeur du brouillon, puis publier la Release : les apps installées la voient via `releases/latest/download/latest.json` (surchargeable par `VTO_UPDATE_URL`).

Ne jamais changer l'`AppId` de `packaging/installer.iss`. Une évolution incompatible de `vinted.json` = nouveau `format` et nouveau fichier `data/vinted-v{N}.json`, l'ancien étant maintenu tant que des versions au-dessus de `minimum_version` le lisent.

## État du dépôt

- Prototype supprimé, remplacé par `backend/` (package `vto`). L'ancien script Selenium `legacy/create_post.py` a été supprimé avec le sous-projet 3 (envoi Vinted par `vto.vinted`, sans identifiants stockés).
- Marque : `brand/` (logo, icône, couleurs ; spec du sous-projet 6). UI : thème `frontend/src/theme.ts` (palettes d'état d'Aura remplacées), police Plus Jakarta Sans, icônes Lucide en police (`icon-*`), composants `frontend/src/components/ui/`.
- App : API FastAPI locale (`vto.api`, protégée par cookie de session + contrôle du Host) et UI Vue 3 + PrimeVue 4 dans `frontend/`. PrimeVue reste en 4.x : la v5 n'est plus MIT (licence commerciale PrimeTek).
- Distribution : `packaging/` (spec PyInstaller, script Inno Setup, générateur de `latest.json`, icône provisoire `make_icon.py`), mises à jour par `vto.updates` + bandeau du front, page d'aide vendeur `docs/aide/installation.md`. Code non signé : avertissement SmartScreen documenté dans la page d'aide.
- Pack de scènes livré : `backend/src/vto/core/default_scenes/`, embarqué dans le paquet (décors de l'auteur, droits OK pour redistribution).
- Secret local dans `.env` (ignoré par git) : `GEMINI_API_KEY`. Ne jamais le commiter. Aucun identifiant Vinted : le vendeur se connecte lui-même dans la fenêtre dédiée.
- Historique git nettoyé des secrets le 2026-10-10 (`git filter-repo --replace-text`). Le dépôt GitHub étant public, la clé et le mot de passe y ont été exposés avant le nettoyage.
