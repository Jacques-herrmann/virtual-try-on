from utils import load_image_as_pil, resize_if_needed, get_item_info_if_exists
from google.genai import types

TEXT_MODEL = "models/gemini-2.0-flash"

PROMPT = """
Contexte : Tu es mon assistant expert en vente Vinted. Ta mission est de rédiger une annonce attrayante, mixte (mais avec une touche de douceur féminine) et avenante, et d'estimer les informations de vente.

Règle absolue : Tu dois générer UNIQUEMENT un objet JSON valide. Ne rajoute absolument aucun texte avant ou après, pas de formules de politesse ni de markdown (pas de balises ```json).

⚠️ Règle technique obligatoire :
Le JSON généré ne doit contenir AUCUN caractère Unicode non BMP (aucun caractère au-delà de U+FFFF).
Cela signifie :
- Aucun symbole spécial hors BMP
- Aucun caractère décoratif ou rare
- Utilise uniquement des caractères standards (ASCII ou Unicode BMP classique).
- Si un élément du prompt contient un caractère non BMP, remplace-le par un équivalent texte simple.

Consignes pour remplir les clés du JSON :

"title" : Optimisé sous la forme -> Type d'article + Marque + Taille + Couleur + État .
⚠️ IMPORTANT pour le titre :

N'utilise PAS de majuscules excessives. Seule la première lettre du titre et des noms propres (marques) doivent être en majuscule.

Exemple correct : "Zara robe longue M bleu"

Exemple incorrect : "ZARA ROBE LONGUE M BLEU"

Les tailles (S, M, L, XL) restent en majuscules car ce sont des abréviations.

Utilise [x] si tu ne connais pas la marque, la taille ou la couleur.

"description" : Détaille la coupe, la matière et l'état avec un ton chaleureux. N'utilise pas de majuscules excessives dans la description non plus. Mets entre crochets [...] toutes les informations variables que tu ne connais pas (Marque, Taille, Matière exacte, Défauts éventuels). Ajoute une section "Idée de look" pour suggérer avec quoi porter la pièce. Fais un rappel de mes offres :
"Petit rappel : Abonne-toi à mon profil pour bénéficier de -10% de remise immédiate ! Et si tu es ravi(e) de ton achat, un petit commentaire te fera gagner -10% supplémentaires sur ta prochaine pépite !"
et finis en intégrant des mots-clés stratégiques et 5 à 8 hashtags pertinents (sans emoji).

"category" : La catégorie Vinted du vêtement (ex: Femmes > Vêtements > Robes).
"brand" : La marque du vêtement ou [x]. Respecter la casse officielle de la marque (ex: Zara, Nike, H&M).
"size" : La taille du vêtement ou [x].
"condition" : L'état du vêtement (Neuf, Très bon état, Bon état, Usé) ou [x].
"color" : La couleur dominante du vêtement ou [x]. Première lettre en majuscule uniquement.
"price" : Un prix de vente cohérent en euros adapté à l'état et à la marque du vêtement, sans le symbole €.
"parcel_size" : La taille de colis recommandée pour l'envoi (Petit, Moyen, Grand) ou [Taille de colis inconnue].

Structure JSON attendue :
{
"title": "",
"description": "",
"category": "",
"brand": "",
"size": "",
"condition": "",
"color": "",
"price": 0,
"parcel_size": ""
}

Vêtement à décrire : {clothing_name}
"""

def generate_ad_description(client, image_path: str, clothing_name: str, clothing_folder) -> str:
    """Generate a stylish e-commerce description for a clothing item based on its image."""
    try:
        img = load_image_as_pil(image_path)
        img = resize_if_needed(img)

        prompt = PROMPT.replace("{clothing_name}", clothing_name)
        info_item = get_item_info_if_exists(clothing_folder)
        if info_item:
            prompt += f"\n\nInformations connus sur le vêtement : {info_item}"

        response = client.models.generate_content(
            model=TEXT_MODEL,
            contents=[prompt, img],
            config=types.GenerateContentConfig(
                response_modalities=["TEXT"],
                temperature=0.7,
            ),
        )

        return response.text

    except Exception as e:
        print(f"  Erreur description : {e}")
        return "Description non disponible."