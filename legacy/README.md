# legacy/

`create_post.py` est le script du prototype qui crée des brouillons Vinted avec Selenium. Il reste ici, inchangé sur le fond, en attendant le sous-projet 3 (automatisation Vinted fiabilisée).

Usage transitoire :

1. `vto run` puis, pour chaque article prêt : `vto export <id> <dossier_annonces>/<nom>` ;
2. `pip install -e backend "selenium>=4.11"` ;
3. dans `.env` à la racine du dépôt (ignoré par git) : `VINTED_EMAIL=…`, `VINTED_PASSWORD=…`, `VTO_LEGACY_OUTPUT=<dossier_annonces>` ;
4. `python legacy/create_post.py` (ou `python legacy/create_post.py <dossier_annonces>`).
