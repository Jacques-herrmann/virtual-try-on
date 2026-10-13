# Interface Kaloé

Vue 3 + Vite + TypeScript + PrimeVue 4 (MIT). Node ≥ 22.12.

## Développement

```
vto-app --dev          # API seule sur 127.0.0.1:8765
npm run dev            # dans frontend/
```

Puis ouvrir http://localhost:5173/api/session?token=dev : le proxy Vite transmet la
requête à l'API, qui pose le cookie de session et redirige vers l'interface.

## Commandes

```
npm test               # Vitest
npm run build          # vérifie les types puis compile dans backend/src/vto/api/static
```

`vto-app` (sans `--dev`) sert la version compilée.
