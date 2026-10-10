from vto.core import errors


def test_errors_carry_french_user_message():
    e = errors.InvalidApiKey()
    assert isinstance(e, errors.VtoError)
    assert "clé Gemini est invalide" in e.user_message
    assert str(e) == e.user_message


def test_no_background_message_names_scene_and_type():
    e = errors.NoBackground("Mannequin", "robe")
    assert "Mannequin" in e.user_message and "robe" in e.user_message


def test_invalid_transition_keeps_states():
    e = errors.InvalidTransition("draft", "published")
    assert (e.from_, e.to) == ("draft", "published")
