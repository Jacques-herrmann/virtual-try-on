import base64
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from vto.licensing import token as token_mod
from vto.licensing.token import InvalidToken, verify_token

FIXTURE = json.loads(
    (Path(__file__).parents[3] / "worker" / "test" / "fixtures" / "token.json").read_text(
        encoding="utf-8"
    )
)
KEYS = {FIXTURE["kid"]: FIXTURE["public_key"]}
KEY = FIXTURE["key"]
DEV = FIXTURE["payload"]["dev"]
IAT = FIXTURE["payload"]["iat"]


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def sign(claims: dict, private=None) -> str:
    private = private or Ed25519PrivateKey.from_private_bytes(bytes(range(1, 33)))
    payload = b64url(json.dumps(claims, separators=(",", ":")).encode())
    return f"{payload}.{b64url(private.sign(payload.encode()))}"


def claims(**over):
    return {**FIXTURE["payload"], **over}


def test_shared_vector_signed_by_the_worker_is_valid():
    c = verify_token(FIXTURE["token"], public_keys=KEYS)
    assert c.kid == "test"
    assert c.dev == DEV
    assert c.status == "active"
    assert c.period_end == FIXTURE["payload"]["period_end"]
    assert c.exp == FIXTURE["payload"]["exp"]
    assert c.usable(key=KEY, device_id=DEV, now=IAT + 10)


def test_test_signer_reproduces_the_vector():
    assert sign(FIXTURE["payload"]) == FIXTURE["token"]


def test_forged_signature_is_rejected():
    payload, sig = FIXTURE["token"].split(".")
    flipped = ("B" if sig[0] == "A" else "A") + sig[1:]
    with pytest.raises(InvalidToken):
        verify_token(f"{payload}.{flipped}", public_keys=KEYS)


def test_token_signed_by_another_key_is_rejected():
    other = Ed25519PrivateKey.generate()
    with pytest.raises(InvalidToken):
        verify_token(sign(claims(), other), public_keys=KEYS)


def test_modified_payload_is_rejected():
    sig = FIXTURE["token"].split(".")[1]
    payload = b64url(json.dumps(claims(exp=2_000_000_000), separators=(",", ":")).encode())
    with pytest.raises(InvalidToken):
        verify_token(f"{payload}.{sig}", public_keys=KEYS)


def test_unknown_kid_is_rejected():
    with pytest.raises(InvalidToken):
        verify_token(sign(claims(kid="k9")), public_keys=KEYS)


@pytest.mark.parametrize("garbage", ["", "abc", "a.b.c", "!!!.???", "e30.AAAA"])
def test_garbage_is_rejected(garbage):
    with pytest.raises(InvalidToken):
        verify_token(garbage, public_keys=KEYS)


def test_other_device_is_not_usable():
    c = verify_token(FIXTURE["token"], public_keys=KEYS)
    assert not c.usable(key=KEY, device_id="autre-pc", now=IAT)


def test_other_key_is_not_usable():
    c = verify_token(FIXTURE["token"], public_keys=KEYS)
    assert not c.usable(key="KAL-0000-0000-0000-0000", device_id=DEV, now=IAT)


def test_expired_token_is_not_usable():
    c = verify_token(FIXTURE["token"], public_keys=KEYS)
    assert c.usable(key=KEY, device_id=DEV, now=c.exp - 1)
    assert not c.usable(key=KEY, device_id=DEV, now=c.exp)
    assert c.is_expired(now=c.exp)


@pytest.mark.parametrize("status", ["canceled", "unpaid", "incomplete_expired", "paused"])
def test_ended_subscription_is_not_usable(status):
    c = verify_token(sign(claims(status=status)), public_keys=KEYS)
    assert c.subscription_ended
    assert not c.usable(key=KEY, device_id=DEV, now=IAT)


@pytest.mark.parametrize("status", ["trialing", "active", "past_due"])
def test_running_subscription_is_usable(status):
    c = verify_token(sign(claims(status=status)), public_keys=KEYS)
    assert not c.subscription_ended
    assert c.usable(key=KEY, device_id=DEV, now=IAT)


def test_production_keys_are_embedded():
    assert token_mod.PUBLIC_KEYS, "aucune clé publique de production embarquée"
    for kid, raw in token_mod.PUBLIC_KEYS.items():
        assert kid != "test"
        assert len(base64.b64decode(raw)) == 32
