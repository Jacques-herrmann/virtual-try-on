# Virtual Try-On — CLAUDE.md

Outil pour vendeurs Vinted : à partir d'une photo de vêtement, génère des photos « portées » (mannequin, cintre…) et une annonce via Gemini, puis crée les brouillons Vinted. Prototype personnel en cours de transformation en produit vendu à des vendeurs non techniques.

## Roadmap

| # | Sous-projet | Statut | Spec / plan |
|---|---|---|---|
| 1 | **Cœur propre** — package `vto`, config, stockage, scènes, génération, pipeline, CLI de dev, import du proto, tests + CI | 🟡 plan écrit | `docs/superpowers/specs/2026-10-10-core-clean-design.md`, `docs/superpowers/plans/2026-10-10-core-clean.md` |
| 2 | **App** — API FastAPI + UI Vue/Vite dans une fenêtre `pywebview` ; saisie article par article, écran de relecture | ⚪ à spécifier | — |
| 3 | **Vinted** — profil Chrome persistant (aucun mot de passe stocké), sélecteurs dans un JSON distant, remplissage complet du formulaire | ⚪ à spécifier | — |
| 4 | **Distribution** — PyInstaller, installeur Inno Setup, mise à jour en un clic, signature de code (plus tard) | ⚪ à spécifier | — |
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
- Aucun secret ni chemin absolu dans le code. Chemins utilisateur uniquement via `vto.core.paths` (racine `%APPDATA%\VirtualTryOn`, surchargeable par `VTO_DATA_DIR`).
- Gemini uniquement via le protocole `GenAIClient` ; les tests utilisent `FakeClient`, jamais le réseau (sauf `pytest -m live`).
- Messages d'erreur destinés au client final : en français, sans jargon ; détails techniques dans le log.
- Les données du client (articles, scènes) ne sont jamais supprimées implicitement.

## Commandes

```
pip install -e backend[dev]
pytest backend/tests             # sans réseau
pytest backend/tests -m live     # nécessite GEMINI_API_KEY
ruff check backend
```

## État du dépôt

- Fichiers à la racine (`main.py`, `utils.py`, `image_generation.py`, `description.py`, `folder_managment.py`, `create_post.py`) = prototype, remplacé par le sous-projet 1.
- ⚠️ L'historique git contient une ancienne clé Gemini et un ancien mot de passe Vinted (à révoquer/changer). Réécriture de l'historique seulement avec accord explicite.
