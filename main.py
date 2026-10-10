import os
import random
from os.path import isfile

from google import genai

from description import generate_ad_description
from folder_managment import copy_files_to_folder, remove_folder
from image_generation import generate_image
from utils import get_random_item_from_folder, get_base_image_from_folder, get_item_info_if_exists

# ─── Configuration ───────────────────────────────────────────────────────────
BASE_FOLDER = r'C:\Users\jhn12\Twake\Annonces\batch'
INPUT_FOLDER = os.path.join(BASE_FOLDER, "input")
CLOTHES_DIR = os.path.join(INPUT_FOLDER, "clothes")
BACKGROUND_FOLDER = os.path.join(INPUT_FOLDER, "backgrounds")
OUTPUT_FOLDER = os.path.join(BASE_FOLDER, "output")

SUPPORTED_FORMATS = ('.png', '.jpg', '.jpeg', '.webp', '.avif')


# ─── Authentication ────────────────────────────────────────────────────────
API_KEY = os.environ["GEMINI_API_KEY"]
client = genai.Client(api_key=API_KEY)

def process_clothing_item(clothing_folder: str):
    """Process a single clothing item: generate a dressed mannequin image and an ad description."""

    clothing_name = os.path.basename(clothing_folder)
    clothing_type = clothing_name.split("_")[0]
    output_dir = os.path.join(OUTPUT_FOLDER, clothing_name)
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  {clothing_name}")
    print(f"{'='*60}")

    print(f"  Génération des images...")

    dummy_path = get_random_item_from_folder(os.path.join(BACKGROUND_FOLDER, clothing_type, '1'))
    hanger_path = get_random_item_from_folder(os.path.join(BACKGROUND_FOLDER, clothing_type, '2'))

    clothing_path = get_base_image_from_folder(clothing_folder)
    if not clothing_path:
        print(f"  Aucun fichier image trouvé pour {clothing_name}. Abandon.")
        return

    output_dummy_path = os.path.join(output_dir, f"0.jpg")
    output_hanger_path = os.path.join(output_dir, f"1.jpg")

    result_dummy_path = generate_image(
        client,
        background_path=dummy_path,
        clothing_path=clothing_path,
        clothing_name=clothing_name,
        output_path=output_dummy_path,
        type="dummy"
    )

    result_hanger_path = generate_image(
        client,
        background_path=hanger_path,
        clothing_path=clothing_path,
        clothing_name=clothing_name,
        output_path=output_hanger_path,
        type="hanger"
    )

    if not result_dummy_path or not result_hanger_path:
        print(f"  Abandon pour {clothing_name}.")
        return

    print(f"  Génération de la description...")

    description = generate_ad_description(client, result_dummy_path, clothing_name, clothing_folder)

    desc_path = os.path.join(output_dir, f"description.json")
    with open(desc_path, "w", encoding="utf-8") as f:
        f.write(description)

    print(f"  ✓ Description sauvegardée : {desc_path}")

    print(f' Déplacement du dossier traité vers "{output_dir}"')
    copy_files_to_folder(clothing_folder, output_dir)
    remove_folder(clothing_folder)

    print(f"  ✓ Traitement terminé pour {clothing_name}.")

if __name__ == "__main__":
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    clothing_folders = [
        os.path.join(CLOTHES_DIR, d)
        for d in sorted(os.listdir(CLOTHES_DIR))
        if os.path.isdir(os.path.join(CLOTHES_DIR, d))
    ]

    if not clothing_folders:
        print(f"\n  Aucun dossier de vêtement trouvé.")
    else:
        print(f"\n  {len(clothing_folders)} vêtement(s) à traiter.")
        for i, folder in enumerate(clothing_folders, 1):
            print(f"\n  [{i}/{len(clothing_folders)}]", end="")
            process_clothing_item(folder)

    print(f"\n{'='*60}")
    print("  Terminé !")
    print("=" * 60)
