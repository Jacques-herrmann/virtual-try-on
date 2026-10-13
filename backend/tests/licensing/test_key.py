import json
from pathlib import Path

import pytest

from vto.licensing.key import key_hint, license_hash, normalize_key

# Cas partagés avec le Worker : les deux implémentations doivent normaliser pareil.
CASES = json.loads(
    (Path(__file__).parents[3] / "worker" / "test" / "fixtures" / "keys.json").read_text(
        encoding="utf-8"
    )
)["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["input"] or "<vide>" for c in CASES])
def test_normalize_key_matches_worker(case):
    assert normalize_key(case["input"]) == case["expected"]


def test_key_hint_shows_only_the_last_group():
    assert key_hint("KAL-ABCD-EFGH-JKMN-WXYZ") == "KAL-…-WXYZ"


def test_license_hash_matches_token_vector():
    fixture = json.loads(
        (Path(__file__).parents[3] / "worker" / "test" / "fixtures" / "token.json").read_text(
            encoding="utf-8"
        )
    )
    assert license_hash(fixture["key"]) == fixture["payload"]["lic"]
