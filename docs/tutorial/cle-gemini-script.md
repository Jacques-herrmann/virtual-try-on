# Script de tournage : « Créer ta clé Gemini » (~30 s)

Vidéo montrée depuis l'accueil de Kaloé (lien « Voir comment faire »). Muette : les sous-titres
sont ajoutés au montage. Tu filmes, je monte (flou, recadrage, compression, sous-titres).

## Avant de filmer

- [ ] Chrome **seul à l'écran**, fenêtre d'environ 1280 × 800 (pas en plein écran), zoom 100 %.
- [ ] Un seul onglet ouvert. Barre de favoris masquée (Ctrl+Maj+B).
- [ ] Notifications Windows coupées (Paramètres → Système → Notifications → Ne pas déranger).
- [ ] Déjà connecté à Google dans ce Chrome (on ne filme pas la connexion).
- [ ] Supprimer d'avance les clés de test inutiles dans AI Studio : la liste doit être courte.

## Ce qui ne doit pas rester lisible

Je les floute au montage, mais moins il y en a, mieux c'est :

- ton adresse e-mail et ta photo de profil (en haut à droite) ;
- **la clé créée** : ne la montre pas en entier, ne la colle nulle part pendant le tournage ;
- le nom de tes projets Google Cloud s'il est personnel.

Après le tournage, **supprime la clé créée** dans AI Studio : elle a été filmée.

## Tournage

Démarrer l'enregistrement : **Win+Maj+R** (Outil Capture), sélectionner la fenêtre Chrome.
Gestes lents, souris immobile ~1 s avant chaque clic, ~2 s de pause sur chaque écran.

| # | Écran | Action | Durée |
|---|---|---|---|
| 1 | Onglet vide | Taper `aistudio.google.com/apikey` dans la barre d'adresse, Entrée | 4 s |
| 2 | Page des clés API | Laisser la page se charger, pointer le titre de la page | 3 s |
| 3 | Page des clés API | Cliquer sur le bouton de création de clé (« Créer une clé API » ou libellé proche) | 3 s |
| 4 | Fenêtre de création | Si un projet est demandé : choisir le projet proposé (ou en créer un), valider | 5 s |
| 5 | Clé affichée | Attendre que la clé apparaisse, puis cliquer sur l'icône **Copier** à côté | 4 s |
| 6 | Clé affichée | Pointer le message de confirmation « copié » s'il apparaît | 2 s |
| 7 | — | Arrêter l'enregistrement (bouton Arrêter de l'Outil Capture) | — |

La partie « coller dans Kaloé » n'est pas filmée : l'écran d'accueil l'explique à côté du lien.

## Ensuite

1. Envoie-moi le chemin du fichier `.mp4` (dossier Vidéos → Enregistrements d'écran).
2. Je repère sur la vidéo les zones et instants à flouter, puis je monte :

   ```
   vto-tutorial edit-key "C:\...\Enregistrement.mp4" --crop x,y,w,h --blur x,y,w,h@début-fin
   ```

3. J'écris `frontend/public/tutorial/cle-gemini.vtt` d'après la vidéo, je vérifie image par
   image que la clé n'apparaît jamais en clair, puis je commite.
