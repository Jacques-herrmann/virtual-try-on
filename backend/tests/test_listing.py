from collections import deque

import pytest
from PIL import Image

from fakes import FakeClient
from vto.core import paths
from vto.core.config import Settings
from vto.core.errors import InvalidModelOutput
from vto.core.generation.listing import generate_listing
from vto.core.models import Listing, SceneResult

MODEL_LISTING = Listing(
    title="Robe bleue", description="Jolie robe.", brand="H&M", size="S",
    condition="Bon état", color=["Bleu"], price=8.0,
)


def client_returning(listing=MODEL_LISTING):
    return FakeClient(json_responses=deque([listing.model_copy()]))


def test_prompt_contains_settings_prompt_and_known_info(data_dir, make_article):
    article = make_article("robe", brand="Zara", notes="petite tache au dos")
    client = client_returning()
    generate_listing(client, Settings(listing_prompt="PROMPT", text_model="txt"), article)
    call = client.calls[0]
    assert call.model == "txt"
    assert call.prompt.startswith("PROMPT")
    assert "Marque : Zara" in call.prompt
    assert "petite tache au dos" in call.prompt
    assert "Taille" not in call.prompt.split("PROMPT", 1)[1]  # champs vides omis


def test_uses_original_photo_only_when_nothing_generated(data_dir, make_article):
    client = client_returning()
    generate_listing(client, Settings(), make_article())
    assert client.calls[0].n_images == 1


def test_uses_first_ok_generated_image_plus_original(data_dir, make_article):
    article = make_article()
    gen = paths.article_dir(article.id) / "generated" / "cintre.jpg"
    gen.parent.mkdir()
    Image.new("RGB", (8, 8)).save(gen)
    article.scenes = [
        SceneResult(scene="mannequin", status="error", error="x"),
        SceneResult(scene="cintre", status="ok", image="generated/cintre.jpg"),
    ]
    client = client_returning()
    generate_listing(client, Settings(), article)
    assert client.calls[0].n_images == 2


def test_user_fields_override_model(data_dir, make_article):
    article = make_article("robe", brand="Zara", price=12.0, condition="Très bon état")
    listing = generate_listing(client_returning(), Settings(), article)
    assert (listing.brand, listing.price, listing.condition) == ("Zara", 12.0, "Très bon état")
    assert listing.size == "S"  # non saisi : valeur du modèle conservée


def test_user_color_becomes_a_one_item_list(data_dir, make_article):
    listing = generate_listing(client_returning(), Settings(), make_article("robe", color="Rouge"))
    assert listing.color == ["Rouge"]


def test_signature_appended(data_dir, make_article):
    listing = generate_listing(client_returning(), Settings(signature="Merci !"), make_article())
    assert listing.description == "Jolie robe.\n\nMerci !"


def test_no_signature_leaves_description(data_dir, make_article):
    listing = generate_listing(client_returning(), Settings(), make_article())
    assert listing.description == "Jolie robe."


def test_invalid_output_propagates(data_dir, make_article):
    client = FakeClient(json_responses=deque([InvalidModelOutput()]))
    with pytest.raises(InvalidModelOutput):
        generate_listing(client, Settings(), make_article())
