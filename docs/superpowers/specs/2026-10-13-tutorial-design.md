# Sous-projet 7 — Tutoriel de première ouverture — Design

Date : 2026-10-13
Statut : validé en brainstorming le 2026-10-13

## 1. Contexte

Kaloé s'adresse à des vendeurs non techniques. Aujourd'hui, après l'accueil (clé de licence puis clé Gemini), le vendeur arrive sur une liste d'articles vide, avec pour seule aide la page Aide écrite. Ce sous-projet ajoute deux aides complémentaires :

1. une **vidéo courte** (~75 s, sous-titrée, muette) qui montre le parcours complet une fois, à la première ouverture ;
2. des **bulles contextuelles** (visite guidée) qui pointent les vrais éléments de chaque écran clé à sa première visite.

S'y ajoute une **vidéo « créer sa clé Gemini »** (~30 s) accessible depuis l'étape Gemini de l'accueil.

### 1.1 Décisions (prises en brainstorming)

| Sujet | Décision |
|---|---|
| Enchaînement | Vidéo à l'arrivée sur Articles après l'accueil, puis bulles contextuelles, une visite par écran à sa première visite |
| Contenu de la vidéo | Kaloé seul ; envoi Vinted **simulé** côté Kaloé ; plan final = capture fixe d'un brouillon Vinted |
| Données de tournage | Un vrai passage Gemini, fait une fois sur un vêtement de démo, enregistré puis rejoué |
| Sous-titres | Fichier WebVTT rendu par l'app par-dessus la vidéo (pas incrustés) |
| Son (ajouté le 2026-10-13) | Voix off ElevenLabs (texte des sous-titres), bruitages d'interface synthétisés, musique de fond fournie par l'utilisateur ; voir §4.8 |
| Visite guidée | **driver.js** (MIT), habillé aux couleurs Kaloé |
| Mémoire « déjà vu » | Dans `settings.json` (backend) : pywebview tourne en `private_mode`, le `localStorage` ne survit pas à un redémarrage |
| Vidéo clé Gemini | Enregistrée par l'utilisateur (Outil Capture Windows) d'après un script de tournage fourni ; montage par un outil ffmpeg |

Approches écartées : visite linéaire unique juste après la vidéo (ne couvre pas la relecture, qui n'existe qu'une fois un article généré) ; choix laissé au vendeur entre vidéo et visite ; tournage du vrai remplissage Vinted (compte connecté et vrai brouillon à chaque tournage, montage de deux fenêtres) ; visite faite maison (placement, masque, défilement à réécrire) ; Shepherd.js et Intro.js (licences commerciales/AGPL) ; tournage scripté de Google AI Studio (page externe qui change, crée une vraie clé à chaque passage).

### 1.2 Hors périmètre

- Traduction, statistiques de visionnage.
- **Abonnement « IA incluse »** (l'utilisateur paie Gemini pour le vendeur) : sous-projet 8, à brainstormer séparément. Il remet en cause la décision BYOK et pose les questions de coût, de quota par licence et des conditions d'utilisation de Google. S'il est fait, le lien vers la vidéo de la clé Gemini sera masqué pour les abonnés concernés.

## 2. Comportement côté vendeur

### 2.1 Vidéo « Kaloé en 1 minute »

- S'ouvre dans une fenêtre modale à l'arrivée sur **Articles** tant que `tutorial.video_seen` est faux : donc juste après l'accueil, et une fois pour les vendeurs déjà installés qui reçoivent la mise à jour (voulu : découverte de la nouveauté, qu'ils peuvent passer).
- Lecture automatique, sous-titres par-dessus l'image, commandes lecture/pause et barre de progression.
- Boutons **Passer** pendant la lecture, **C'est parti** à la fin. Toute fermeture (bouton, Échap, croix) marque la vidéo vue.

### 2.2 Bulles contextuelles

Une visite par écran, 2 à 4 étapes, lancée à la première visite de l'écran (pour Articles : à la fermeture de la vidéo). La visite des articles est coupée en deux : un nouveau vendeur a une liste vide, la seconde partie attend le premier article.

| Visite (`id`) | Déclencheur | Étapes |
|---|---|---|
| `articles` | Écran Articles (liste) | Nouvel article ; Scènes, Réglages et Aide dans la barre latérale |
| `articles-list` | Écran Articles dès qu'un article existe | Recherche ; filtre par statut ; ouvrir un article ; cocher puis Envoyer sur Vinted |
| `article-form` | Formulaire Nouvel article | Zone photos ; type de vêtement ; champs facultatifs ; Générer |
| `review` | Premier article « À relire » ouvert | Régénérer / Écarter ; ordre des photos ; champs de l'annonce ; Valider l'article |
| `scenes` | Écran Scènes | Activer/désactiver une scène ; ajouter ses décors ; modifier le prompt |
| `settings` | Écran Réglages | Connecter mon compte Vinted ; mode brouillon/publication |

- Boutons **Suivant**, **Précédent**, **Passer la visite**, compteur « 2/4 » ; pas de croix (Échap ferme aussi).
- Terminer ou passer marque la visite vue.
- Une étape dont l'élément n'est pas affiché (liste vide, bouton masqué) est sautée ; si aucune étape ne reste, la visite n'est ni lancée ni marquée vue.
- Changer d'écran ou ouvrir une fenêtre (ex. : clic sur « Nouvel article » pendant la visite) la ferme sans la marquer vue : elle reviendra.
- Deux visites possibles en même temps (Articles) : jouées l'une après l'autre.
- Aucune visite ne démarre tant que la vidéo est ouverte.

### 2.3 Accueil, étape « Clé Gemini »

Lien **« Voir comment faire (30 s) »** sous les instructions écrites : ouvre le même lecteur avec la vidéo de la clé Gemini. N'influence pas `video_seen`.

### 2.4 Page Aide

Nouvelle carte en tête : **Revoir la vidéo** (ouvre le lecteur) et **Relancer les visites guidées** (vide `tours_seen` ; chaque visite se rejoue à la prochaine visite de son écran).

## 3. Architecture de l'app

### 3.1 Backend

- `vto.core.config.Settings` gagne `tutorial: TutorialState` avec `video_seen: bool = False` et `tours_seen: list[str] = []`. Un `settings.json` sans ce champ se charge avec les valeurs par défaut.
- `SettingsView` expose `tutorial` ; `SettingsUpdate` accepte `tutorial` (remplacement complet de l'objet). Pas de nouvelle route.
- `vto.self_check` vérifie la présence de `tutorial/kaloe.mp4` et `tutorial/kaloe.vtt` dans le front embarqué.

### 3.2 Médias

Dans `frontend/public/tutorial/`, versionnés (3 à 6 Mo au total) ; Vite les recopie dans `backend/src/vto/api/static/`, embarqué par PyInstaller :

| Fichier | Contenu |
|---|---|
| `kaloe.mp4`, `kaloe.vtt`, `kaloe.jpg` | Vidéo principale, sous-titres, image d'affiche |
| `cle-gemini.mp4`, `cle-gemini.vtt` | Vidéo de la clé Gemini et ses sous-titres |

### 3.3 Frontend

- `components/TutorialVideo.vue` : `Dialog` PrimeVue avec `<video>` ; props `src`, `captions`, `poster`, `title` ; la piste `.vtt` est chargée en mode `hidden` et le sous-titre courant (événement `cuechange`) est rendu dans un bloc stylé Kaloé ; émet `close`. Sert aux deux vidéos.
- `tours.ts` : données seules. `Record<TourId, TourStep[]>` avec `TourStep = { target: string /* '[data-tour="…"]' */, title: string, text: string }`.
- `stores/tutorial.ts` : état partagé `videoOpen` ; `save(changes)` met à jour `tutorial` localement puis l'enregistre (`PUT /api/settings`, échec ignoré) ; `tourSeen`, `markTourSeen`.
- `composables/tour.ts` :
  - `useTour().maybeStart(id)` : ne fait rien si `id ∈ tours_seen` ou si la vidéo est ouverte ; une visite à la fois (les suivantes attendent) ; attend que les éléments visés existent (les listes arrivent par l'API, 1,5 s au plus), filtre les étapes sans élément, lance driver.js, marque la visite vue quand le vendeur la termine ou la passe. `stop(id)` la ferme sans la marquer ; `resetTours()` vide `tours_seen`.
  - `useAutoTour(id, when?)` : dans un composant, lance la visite dès que `when()` est vrai et la vidéo fermée ; la ferme sans la marquer quand `when()` redevient faux ou au démontage. La fermeture de la vidéo relance donc d'elle-même les visites de l'écran affiché.
- Écrans : attributs `data-tour="…"` et `useAutoTour(…)` dans `App.vue` (liens de la barre latérale, cibles seulement), `ArticlesView`, `ArticleList`, `ArticleForm` (création), `ArticleReview` (« À relire »), `ScenesView` (`BackgroundGallery`), `SettingsView`.
- `tour.css` : thème driver.js à partir des jetons de `theme.ts` (abricot/crème, Plus Jakarta Sans, coins arrondis).
- `WelcomeView` : lien et lecteur de la vidéo de la clé Gemini.
- `HelpView` : carte « Revoir la vidéo / Relancer les visites guidées ».
- Dépendance ajoutée : `driver.js` (MIT), version exacte épinglée comme les autres.

## 4. Tournage scripté de la vidéo principale

### 4.1 Outil

`vto.tools.tutorial`, commande `vto-tutorial` (déclarée dans `pyproject.toml` comme `vto-vinted-catalog`). `core` n'en dépend pas. Données dans `tools/tutorial/` à la racine du dépôt :

- `demo/` : 1 ou 2 photos du vêtement de démo (fournies par l'utilisateur, droits OK) ;
- `capture/` : résultats Gemini enregistrés (images générées, annonce en JSON) ;
- `vinted-draft.png` : capture fixe d'un brouillon Vinted, nom de compte flouté (fournie par l'utilisateur).

### 4.2 `vto-tutorial capture` (une fois, réseau)

Génère avec le vrai Gemini (`GEMINI_API_KEY`) les photos portées (scènes par défaut) et l'annonce à partir de `demo/`, et les écrit dans `capture/`. L'utilisateur valide le résultat ; on relance jusqu'à en être satisfait.

**Variante retenue : `vto-tutorial capture --from-article <identifiant ou mot du titre>`.** L'utilisateur crée l'article de démo dans le vrai Kaloé et l'envoie en brouillon sur Vinted ; l'outil reprend cet article (lecture seule sur les données de l'app) : images rangées sous les prompts du pack par défaut, annonce telle qu'envoyée, photo d'origine et type recopiés dans `demo/`. Une seule génération, et le film, le brouillon et `vinted-draft.png` montrent le même article.

### 4.3 `vto-tutorial record` (rejouable, sans réseau)

1. Crée un `VTO_DATA_DIR` temporaire : clé Gemini factice, `tutorial.video_seen = true` et toutes les visites dans `tours_seen` (rien ne doit s'afficher dans le film).
2. Démarre `create_app` dans un thread uvicorn avec :
   - un **client de rejeu** (`GenAIClient`) qui rend les données de `capture/` après un délai réaliste mais raccourci ;
   - un gestionnaire de licence simulé « active » ;
   - le vrai `VintedWorker`, branché sur des faux (`start_playwright`, `open_context`, `is_logged_in` → connecté, `fill` → attend ~1 s et réussit, `pause_range` court) ;
   - le front compilé (`npm run build` préalable ; erreur claire s'il manque).
3. Playwright (Chromium, 1280×800, `recordVideo`) déroule le scénario.

### 4.4 Scénario (~75 s)

Articles vide → Nouvel article → dépôt de la photo → type → Générer → progression → l'article passe « À relire » → ouverture, défilement des photos, retouche du prix → Valider l'article → cocher → Envoyer sur Vinted → progression jusqu'à « Envoyé » → plan final : `vinted-draft.png` affiché quelques secondes (page HTML locale ouverte dans le même onglet).

Chaque étape du scénario est une fonction associée à son sous-titre (« Ajoute une photo de ton vêtement »…). Les instants de début et de fin de chaque étape sont relevés pendant le tournage et donnent le `.vtt` : vidéo et sous-titres restent alignés quand l'interface change.

### 4.5 Lisibilité

- **Faux curseur** injecté dans la page (Playwright ne filme pas la souris) : déplacements interpolés vers l'élément visé, halo au clic.
- Saisie lettre par lettre, pauses de lecture après chaque action.

### 4.6 Post-production (ffmpeg)

Coupe des premières images blanches (décalage appliqué au `.vtt`), encodage webm → mp4 H.264 (`-crf 28`, `-movflags +faststart`, sans piste audio), extraction de l'affiche. Sortie directe dans `frontend/public/tutorial/`.

### 4.7 Vidéo de la clé Gemini

- `docs/tutorial/cle-gemini-script.md` : script de tournage pour l'utilisateur (préparation de l'écran, chaque clic, durée par écran, ce qu'il ne faut pas montrer : adresse e-mail, clé, autres onglets).
- `vto-tutorial edit-key <fichier> [--crop x,y,w,h] [--blur x,y,w,h[@début-fin]]…` : recadre, floute les zones indiquées, compresse comme en 4.6 et écrit `cle-gemini.mp4`.
- `cle-gemini.vtt` rédigé à la main d'après la vidéo montée.

### 4.8 Son (ajouté le 2026-10-13)

- **Voix off** : chaque sous-titre est lu par une voix ElevenLabs (`ELEVENLABS_API_KEY` et `ELEVENLABS_VOICE_ID` dans `.env`, jamais commités ; modèle multilingue). Les fichiers sont mis en cache dans `tools/tutorial/voice/` sous l'empreinte du texte et de la voix, et commités : un nouveau tournage ne rappelle ElevenLabs que pour un texte modifié, et `record` reste possible sans réseau si le cache est complet. Les voix sont générées **avant** le tournage : chaque étape dure au moins le temps de sa phrase (+0,4 s).
- **Bruitages** : clic (à chaque clic du faux curseur), frappe (saisie), « ding » (article prêt, brouillon envoyé), synthétisés en code (aucun droit). Instants relevés par le `Director`.
- **Musique** : `tools/tutorial/music.mp3`, morceau libre de droits choisi par l'utilisateur ; bouclé ou coupé à la durée, volume bas, baissé sous la voix (compression en side-chain), fondu de 2 s en fin. Facultative : sans fichier, pas de musique.
- **Mixage** ffmpeg, audio AAC 128 kb/s dans le mp4. `record --mute` garde la vidéo muette.
- **Lecteur** : lecture automatique avec le son ; si la fenêtre la refuse, lecture muette et bouton « Activer le son ». Bouton couper/remettre le son dans les commandes.

## 5. Erreurs

Messages en français, sans jargon ; détails dans la console du front (`console.warn`) : le front n'a pas de canal de log vers l'API.

| Situation | Comportement |
|---|---|
| Vidéo introuvable ou illisible | « La vidéo n'a pas pu être lue. Tu peux la revoir plus tard depuis l'Aide. » + Fermer ; la vidéo est marquée vue |
| Enregistrement « vu » impossible (API injoignable) | Rien ne bloque ; la vidéo ou la visite reviendra au prochain lancement |
| Élément visé absent | Étape sautée ; visite non lancée et non marquée vue si plus aucune étape |
| Changement d'écran pendant une visite | Visite fermée, non marquée vue |
| `record` sans front compilé ou sans `capture/` | Message clair indiquant la commande à lancer |

## 6. Tests et vérification

**Backend** (`pytest`, sans réseau) :
- ancien `settings.json` sans `tutorial` → valeurs par défaut ;
- `PUT /api/settings` met à jour et relit `tutorial`, remise à zéro de `tours_seen` ;
- client de rejeu : rend les données enregistrées ;
- génération du `.vtt` à partir des instants (format, ordre, décalage de coupe) ;
- `--self-check` signale l'absence des médias du tutoriel.

**Front** (Vitest) :
- `maybeStart` : rien si visite vue ou vidéo ouverte ; étapes sans élément filtrées ; marquage vu après « Passer » et à la fin (driver.js simulé) ; rien de marqué si aucune étape ;
- `useAutoTour` : lancement quand la condition devient vraie, fermeture sans marquage quand elle redevient fausse ou au démontage ;
- `TutorialVideo` : sous-titre courant affiché, marquage vu à la fermeture, message en cas d'erreur de lecture ;
- cohérence : chaque `target` de `tours.ts` correspond à un `data-tour` présent dans le composant de son écran.

**Tournage** (`pytest -m browser`) : `vto-tutorial record` en mode court (2 étapes) produit une vidéo et un `.vtt` non vides.

**Essai réel** : préversion `rc` installée sur le poste par-dessus la version en place ; la vidéo s'affiche une fois, les bulles apparaissent sur chaque écran, l'Aide permet de tout revoir, la vidéo de la clé Gemini se lit depuis l'accueil.

## 7. Documentation

- Page Aide de l'app : carte du tutoriel (§2.4).
- `CLAUDE.md` : ligne 7 de la roadmap, commandes `vto-tutorial capture|record|edit-key`.
- `docs/tutorial/cle-gemini-script.md` (§4.7).
