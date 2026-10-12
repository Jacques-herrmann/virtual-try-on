# Virtual Try-On — CLAUDE.md

Outil pour vendeurs Vinted : à partir d'une photo de vêtement, génère des photos « portées » (mannequin, cintre…) et une annonce via Gemini, puis crée les brouillons Vinted. Prototype personnel en cours de transformation en produit vendu à des vendeurs non techniques.

## Roadmap

| # | Sous-projet | Statut | Spec / plan |
|---|---|---|---|
| 1 | **Cœur propre** — package `vto`, config, stockage, scènes, génération, pipeline, CLI de dev, import du proto, tests + CI | ✅ terminé le 2026-10-12 sur `main` — validé de bout en bout par l'essai réel du sous-projet 3 | `docs/superpowers/specs/2026-10-10-core-clean-design.md`, `docs/superpowers/plans/2026-10-10-core-clean.md` |
| 2 | **App** — API FastAPI + UI Vue/Vite dans une fenêtre `pywebview` ; saisie article par article, écran de relecture | ✅ terminé le 2026-10-12 sur `main` — validé de bout en bout par l'essai réel du sous-projet 3 | `docs/superpowers/specs/2026-10-10-app-design.md`, `docs/superpowers/plans/2026-10-10-app.md` |
| 3 | **Vinted** — profil Chrome persistant (aucun mot de passe stocké), sélecteurs dans un JSON distant, remplissage complet du formulaire | ✅ terminé le 2026-10-12 sur `main` — essai réel fait (brouillons, lot, publication, 3 relances sans reconnexion, `pytest -m live_vinted`) ; catalogue complet relevé (783 feuilles, 26 grilles de tailles) ; `data/vinted.json` publié | `docs/superpowers/specs/2026-10-10-vinted-design.md`, `docs/superpowers/plans/2026-10-10-vinted.md` |
| 4 | **Distribution** — PyInstaller, installeur Inno Setup, mise à jour en un clic, signature de code (plus tard) | 🟡 spec et plan écrits — implémentation en cours sur `main` | `docs/superpowers/specs/2026-10-12-distribution-design.md`, `docs/superpowers/plans/2026-10-12-distribution.md` |
| 5 | **Licence** — achat unique + 12 mois de MAJ, abonnement MAJ optionnel ; plateforme *merchant of record* ; Worker qui vérifie la licence avant de servir MAJ et sélecteurs | ⚪ à spécifier | — |

Ordre : 1 → 2 → 3 → 4 → 5. Chaque sous-projet suit le cycle brainstorming → spec → plan → implémentation. Mettre à jour le statut ci-dessus à chaque étape.

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
- Aucun secret ni chemin absolu dans le code. Chemins utilisateur uniquement via `vto.core.paths` (racine `%LOCALAPPDATA%\VirtualTryOn`, surchargeable par `VTO_DATA_DIR`).
- Gemini uniquement via le protocole `GenAIClient` ; les tests utilisent `FakeClient`, jamais le réseau (sauf `pytest -m live`).
- Messages d'erreur destinés au client final : en français, sans jargon ; détails techniques dans le log.
- Les données du client (articles, scènes) ne sont jamais supprimées implicitement.

## Commandes

```
pip install -e backend[dev]
pytest backend/tests             # sans réseau
pytest backend/tests -m live     # nécessite GEMINI_API_KEY
pytest backend/tests -m browser  # pilote un navigateur (Chrome installé ou `playwright install chromium`)
pytest backend/tests -m live_vinted  # crée puis efface un vrai brouillon (profil Vinted connecté)
ruff check backend

vto-vinted-catalog               # relève le catalogue Vinted (~1 h, reprenable) et réécrit data/vinted.json ;
                                 # recopier ensuite dans backend/src/vto/vinted/data/vinted.json

cd frontend && npm ci            # Node ≥ 22.12 (nvm-windows sur le poste de dev)
npm test                         # Vitest
npm run build                    # compile dans backend/src/vto/api/static (ignoré par git)

vto-app                          # application complète (fenêtre pywebview)
vto-app --dev                    # API seule sur 127.0.0.1:8765, puis `npm run dev` et
                                 # http://localhost:5173/api/session?token=dev
```

## État du dépôt

- Prototype supprimé, remplacé par `backend/` (package `vto`). L'ancien script Selenium `legacy/create_post.py` a été supprimé avec le sous-projet 3 (envoi Vinted par `vto.vinted`, sans identifiants stockés).
- App : API FastAPI locale (`vto.api`, protégée par cookie de session + contrôle du Host) et UI Vue 3 + PrimeVue 4 dans `frontend/`. PrimeVue reste en 4.x : la v5 n'est plus MIT (licence commerciale PrimeTek).
- Pack de scènes livré : `default_scenes/` (décors de l'auteur, droits OK pour redistribution).
- Secret local dans `.env` (ignoré par git) : `GEMINI_API_KEY`. Ne jamais le commiter. Aucun identifiant Vinted : le vendeur se connecte lui-même dans la fenêtre dédiée.
- Historique git nettoyé des secrets le 2026-10-10 (`git filter-repo --replace-text`). Le dépôt GitHub étant public, la clé et le mot de passe y ont été exposés avant le nettoyage.
