# Marque Kaloé

Spec : `docs/superpowers/specs/2026-10-13-brand-design.md` (piste A).

| Fichier | Usage |
|---|---|
| `logo.svg` | logo complet, texte prune et « o » cintre abricot, sur fond clair |
| `logo-light.svg` | même logo sur fond prune ou foncé |
| `logo-mark.svg` | « o » cintre seul, abricot |
| `app-icon.svg` | icône d'app (carré abricot, « o » cintre prune) : source de `packaging/icon.ico` |
| `tokens.json` | palette, rayons, ombres ; recopiés dans `frontend/src/theme.ts` et `worker/src/pages.ts` |

Règles :

- Police unique : Plus Jakarta Sans (OFL), embarquée dans l'app (`@fontsource/plus-jakarta-sans`).
- Texte sur abricot : toujours prune (`#2E1F2B`, 5,3:1), jamais blanc (2,9:1).
- Liens et texte d'accent sur fond clair : abricot 700 (`#AD4A24`).
- Laisser autour du logo une marge au moins égale à la hauteur du « o ». Taille minimale du logo complet : 24 px de haut ; en dessous, le pictogramme seul.

Régénérer : `python brand/make_logo.py` (fonttools + brotli, police installée par `npm ci` dans `frontend/`), puis `python packaging/make_icon.py`.
