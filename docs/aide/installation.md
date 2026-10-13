# Installer Virtual Try-On

## Télécharger

Télécharge `VirtualTryOn-Setup-X.Y.Z.exe` depuis le lien reçu à l'achat, puis double-clique dessus. L'installation ne demande pas de mot de passe administrateur et prend moins d'une minute.

## Clé de licence

Ta clé (`VTO-XXXX-XXXX-XXXX-XXXX`) s'affiche juste après le paiement et t'est aussi envoyée par e-mail. Au premier lancement, colle-la dans l'application. Elle fonctionne sur 2 PC ; un PC inutilisé pendant 30 jours libère sa place, et tu peux aussi désactiver un PC depuis les réglages de l'application.

Clé perdue ? Va sur la page « Retrouver ma clé » et indique l'adresse e-mail utilisée pour l'achat.

## « Windows a protégé votre ordinateur »

Windows affiche ce message pour les applications récentes qu'il ne connaît pas encore. Pour continuer :

1. Clique sur **Informations complémentaires**.
2. Clique sur **Exécuter quand même**.

Le même message peut apparaître si Windows bloque une mise à jour lancée depuis l'application : télécharge alors la dernière version depuis le même lien et installe-la par-dessus. Tes articles et tes réglages sont conservés.

## Antivirus

Certains antivirus se méfient des applications récentes. Si le tien bloque ou met en quarantaine `VirtualTryOn.exe` :

- restaure le fichier depuis la quarantaine ;
- ajoute une exception pour le dossier `%LOCALAPPDATA%\Programs\VirtualTryOn` ;
- relance l'installation.

## « Un composant Windows (WebView2) n'a pas pu être installé »

L'application s'affiche grâce à WebView2, un composant de Microsoft déjà présent sur Windows 11 et sur la plupart des Windows 10. S'il manque et que l'installation automatique échoue, installe-le depuis le site de Microsoft (« Microsoft Edge WebView2 Runtime », version *Evergreen Bootstrapper*), puis relance Virtual Try-On.

## Mises à jour

Quand une nouvelle version est disponible, un bandeau s'affiche en haut de l'application. Clique sur **Mettre à jour** : l'application télécharge la nouvelle version, se ferme, s'installe et se relance d'elle-même. La mise à jour n'est possible que lorsqu'aucune génération ni aucun envoi Vinted n'est en cours.

Si le bandeau est rouge, ta version ne fonctionne plus avec Vinted : l'envoi des annonces est bloqué jusqu'à la mise à jour, mais tu peux continuer à générer et relire tes articles.

## Où sont mes données ?

Tes articles, tes scènes, tes réglages et ta connexion Vinted sont dans `%LOCALAPPDATA%\VirtualTryOn` (colle ce chemin dans la barre d'adresse de l'Explorateur). L'application elle-même est dans `%LOCALAPPDATA%\Programs\VirtualTryOn`.

## Désinstaller

Paramètres Windows → **Applications** → **Applications installées** → Virtual Try-On → **Désinstaller**.

La désinstallation retire l'application mais **garde tes données** : si tu réinstalles, tu retrouves tout. Pour tout effacer, supprime aussi le dossier `%LOCALAPPDATA%\VirtualTryOn`.
