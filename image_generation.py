import io
from google.genai import types
from PIL import Image as PILImage

from utils import load_image_as_pil, resize_if_needed, prepare_for_gemini

IMAGE_MODEL = "models/gemini-2.5-flash-image"

PROMPT_DUMMY = """
Hyper-realistic studio photography composition merging [Image A] and [Image B].
Place the garment from [Image B] onto the white female mannequin standing on a gold stand in [Image A], inside the elegant walk-in closet environment.

Physics and Fit:
The garment must conform naturally to the mannequin’s body shape, respecting anatomical proportions. Fabric tension should appear realistic around the bust, waist, and hips. Gravity must create organic vertical draping, subtle tension folds at structural points (shoulders, waistline, seams), and soft creases where the fabric gathers. The garment should show believable volume and structure depending on its material (fluid if silk/chiffon, structured if cotton/wool/leather).

Lighting and Color:
Use the warm ambient lighting from the closet scene. A soft golden light from the left (closet LED strip) should create gentle highlights along the left contours of the garment. Warm fairy lights on the right should add subtle amber rim lighting. Shadows must be soft but defined, with depth in folds. Preserve the garment’s original color and texture from [Image B], but subtly tint it with the warm amber indoor glow for cohesive integration.

Shadow Integration:
Create precise contact shadows where the garment touches the mannequin surface. The mannequin and garment together should cast a soft, diffused shadow onto the wall and floor, consistent with the room lighting. Ensure grounding shadows at the base near the gold stand for physical realism.

Environment Integration:
Maintain the stylish dressing room background: hanging clothes on wooden hangers, soft carpet, marble floor, shoes and accessories subtly blurred in the foreground. The garment must feel fully embedded in this luxury boutique setting.

Technical Details:
Shallow depth of field matching the original scene — mannequin and garment in sharp focus, background softly blurred.
8K resolution, ultra-detailed fabric texture, cinematic warm lighting, high-fashion editorial catalog quality, realistic skin-like mannequin texture, premium interior photography aesthetic.

In case the garment from [Image B] is a shoe, it should be placed on the floor in front of the mannequin, with appropriate shadows and lighting to match the scene's ambiance and maintain photorealism.

IMPORTANT: The output image MUST be in portrait orientation with a 3:4 aspect ratio (e.g., 768x1024 or 1536x2048). Do NOT produce a square or landscape image.
"""

PROMPT_HANGER = """
A hyper-realistic studio photography composition merging [Image A] and [Image B].

If the item from [Image B] is a garment (shirt, jacket, dress, etc.):
Place the garment onto the wooden hanger held by the hand in [Image A].

Physics and Fit:
The garment must drape naturally from the hanger's shoulders, showing organic tension folds and soft creases caused by gravity. The fabric should wrap slightly around the hanger's frame to show volume.

Lighting and Color:
Apply the lighting scheme from [Image A] to the garment: a strong directional warm light coming from the left, creating soft highlights on the left side of the fabric and deep, rich shadows in the folds on the right. Preserve the garment’s original texture and color from [Image B], subtly tinted by the amber glow of the scene.

Shadow Integration:
Render precise contact shadows where the hanger touches the fabric. The garment should cast a soft, diffused shadow onto the grey wall behind it, matching the shadow cast by the hand and arm in the original photo.

Technical Details:
Maintain the shallow depth of field from [Image A], keeping the hand and garment in sharp focus while the grey background remains in soft bokeh. 8k resolution, cinematic lighting, high-fashion catalog quality.

If the item from [Image B] is a shoe or footwear:
Do NOT include any hanger, hand, or arm in the final image.
Place the shoes naturally on the floor within the environment of [Image A], positioned realistically as a product display.

The shoes must be oriented naturally in relation to the mannequin, aligned as if worn or placed in front of it, with correct left/right positioning and realistic forward direction.

The shoes must respect physical grounding with accurate contact shadows on the floor.
Apply the exact same lighting scheme from [Image A]: strong warm directional light from the left, creating realistic highlights and soft shadows.
Preserve the original texture, materials, and color of the shoes from [Image B], subtly influenced by the ambient warmth of the scene.
Maintain shallow depth of field consistent with [Image A], with the shoes in sharp focus and the background softly blurred.
8k resolution, cinematic lighting, high-fashion catalog quality.

IMPORTANT: The output image MUST be in portrait orientation with a 3:4 aspect ratio (e.g., 768x1024 or 1536x2048). Do NOT produce a square or landscape image.
"""


def generate_image(
    client,
    background_path: str,
    clothing_path: str,
    clothing_name: str,
    output_path: str,
    type: str = "dummy"
) -> str | None:
    """
    Generate a photo-realistic image of a background with a specific clothing item using Gemini's multimodal capabilities.
    """
    print(f"  Chargement des images...")

    background_img = load_image_as_pil(background_path)
    background_img = resize_if_needed(background_img)
    background_img = prepare_for_gemini(background_img)

    clothing_img = load_image_as_pil(clothing_path)
    clothing_img = resize_if_needed(clothing_img)
    clothing_img = prepare_for_gemini(clothing_img)

    if type == "dummy":
        prompt_text = PROMPT_DUMMY.replace("{clothing_name}", clothing_name)
    else:
        prompt_text = PROMPT_HANGER.replace("{clothing_name}", clothing_name)

    try:
        print(f"  Envoi à Gemini...")

        response = client.models.generate_content(
            model=IMAGE_MODEL,
            contents=[
                prompt_text,
                background_img,
                clothing_img,
            ],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
                temperature=0.4,
            ),
        )

        image_saved = False
        text_response = ""

        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                image_data = part.inline_data.data
                generated_img = PILImage.open(io.BytesIO(image_data))
                generated_img.save(output_path, quality=95)
                print(f"  ✓ Image sauvegardée : {output_path}")
                image_saved = True

            elif part.text:
                text_response += part.text

        if text_response:
            print(f"  Réponse texte Gemini : {text_response[:200]}")

        if not image_saved:
            print(f"  ✗ Aucune image dans la réponse de Gemini.")
            print(f"    Réponse complète : {response.text if hasattr(response, 'text') else 'N/A'}")
            return None

        return output_path

    except Exception as e:
        print(f"  ✗ Erreur Gemini : {e}")
        import traceback
        traceback.print_exc()
        return None