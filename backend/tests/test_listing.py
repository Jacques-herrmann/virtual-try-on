from collections import deque

import pytest
from PIL import Image
from pydantic import ValidationError

from fakes import FakeClient
from vto.core import paths
from vto.core.config import Settings
from vto.core.errors import InvalidModelOutput
from vto.core.generation.listing import generate_listing
from vto.core.models import Listing, ListingChoices, SceneResult

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


def test_user_color_is_a_hint_not_an_override(data_dir, make_article):
    client = client_returning()
    listing = generate_listing(client, Settings(), make_article("robe", color="bleu marine"))
    assert listing.color == ["Bleu"]  # proposition du modèle
    assert "Couleur : bleu marine" in client.calls[0].prompt


CHOICES = ListingChoices(
    categories={"1779": "Femmes › Vêtements › Robes", "1780": "Femmes › Vêtements › Jupes"},
    colors=["Noir", "Bleu", "Rouge"],
)


def schema_property(schema, name):
    props = schema.model_json_schema()["properties"]
    prop = props[name]
    return next((p for p in prop.get("anyOf", []) if p.get("type") != "null"), prop)


def test_choices_constrain_category_and_colors(data_dir, make_article):
    client = client_returning(MODEL_LISTING.model_copy(update={"category": "1779"}))
    listing = generate_listing(client, Settings(), make_article(), CHOICES)
    schema = client.calls[0].schema
    assert schema_property(schema, "category")["enum"] == ["1779", "1780"]
    color = schema_property(schema, "color")
    assert color["items"]["enum"] == ["Noir", "Bleu", "Rouge"]
    assert color["maxItems"] == 2
    assert type(listing) is Listing
    assert (listing.category, listing.color) == ("1779", ["Bleu"])


def test_single_choice_is_still_an_enum(data_dir, make_article):
    client = client_returning(MODEL_LISTING.model_copy(update={"category": "1779"}))
    choices = ListingChoices(categories={"1779": "Femmes › Robes"}, colors=["Bleu"])
    generate_listing(client, Settings(), make_article(), choices)
    schema = client.calls[0].schema
    assert schema_property(schema, "category")["enum"] == ["1779"]
    assert schema_property(schema, "color")["items"]["enum"] == ["Bleu"]


def test_choices_are_listed_in_prompt(data_dir, make_article):
    client = client_returning()
    generate_listing(client, Settings(), make_article(), CHOICES)
    prompt = client.calls[0].prompt
    assert "1779 : Femmes › Vêtements › Robes" in prompt
    assert "Noir, Bleu, Rouge" in prompt


def test_model_output_outside_choices_is_rejected(data_dir, make_article):
    client = client_returning(MODEL_LISTING.model_copy(update={"category": "9999"}))
    with pytest.raises(ValidationError):
        generate_listing(client, Settings(), make_article(), CHOICES)


def test_without_choices_schema_is_listing(data_dir, make_article):
    client = client_returning()
    generate_listing(client, Settings(), make_article())
    assert client.calls[0].schema is Listing
    assert "Catégories possibles" not in client.calls[0].prompt


def test_empty_choices_leave_fields_empty(data_dir, make_article):
    client = client_returning(MODEL_LISTING.model_copy(update={"color": []}))
    listing = generate_listing(
        client, Settings(), make_article(), ListingChoices(categories={}, colors=[])
    )
    assert listing.category is None and listing.color == []


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
