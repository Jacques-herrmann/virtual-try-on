import base64
from types import SimpleNamespace

import httpx
import pytest
from PIL import Image

from vto.core import errors
from vto.core.generation import client as gc
from vto.core.models import Listing


class FakeSdkError(Exception):
    def __init__(self, status_code, message=""):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (FakeSdkError(401, "API key not valid"), errors.InvalidApiKey),
        (FakeSdkError(403, "permission denied"), errors.InvalidApiKey),
        (FakeSdkError(403, "Your project has been denied access."), errors.ProjectBlocked),
        (FakeSdkError(400, "API key not valid. Please pass a valid key."), errors.InvalidApiKey),
        (FakeSdkError(404, "model not found"), errors.ModelUnavailable),
        (FakeSdkError(429, "Rate limit, retry later"), errors.TransientError),
        (FakeSdkError(429, "You exceeded your quota, check billing"), errors.QuotaExceeded),
        (FakeSdkError(500, "internal"), errors.TransientError),
        (FakeSdkError(503, "overloaded"), errors.TransientError),
        (httpx.ConnectTimeout("timeout"), errors.TransientError),
        (FakeSdkError(400, "bad request"), errors.VtoError),
    ],
)
def test_map_sdk_error(exc, expected):
    mapped = gc.map_sdk_error(exc)
    assert type(mapped) is expected
    assert mapped.__cause__ is None  # le chaînage est fait par l'appelant


def test_map_sdk_error_supports_legacy_code_attribute():
    exc = Exception("x")
    exc.code = 401
    assert isinstance(gc.map_sdk_error(exc), errors.InvalidApiKey)


class Counter:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        item = self.outcomes.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def test_retry_then_success():
    delays = []
    fn = Counter(errors.TransientError(), "ok")
    assert gc.with_retry(fn, sleep=delays.append) == "ok"
    assert fn.calls == 2 and len(delays) == 1


def test_retry_on_no_image():
    fn = Counter(errors.NoImageReturned(), b"img")
    assert gc.with_retry(fn, sleep=lambda d: None) == b"img"


def test_no_retry_on_invalid_key():
    fn = Counter(errors.InvalidApiKey(), "ok")
    with pytest.raises(errors.InvalidApiKey):
        gc.with_retry(fn, sleep=lambda d: None)
    assert fn.calls == 1


def test_gives_up_after_attempts():
    delays = []
    fn = Counter(errors.TransientError(), errors.TransientError(), errors.TransientError("last"))
    with pytest.raises(errors.TransientError, match="last"):
        gc.with_retry(fn, attempts=3, base_delay=2, sleep=delays.append)
    assert fn.calls == 3
    assert len(delays) == 2
    assert 1.6 <= delays[0] <= 2.4 and 3.2 <= delays[1] <= 4.8


# --- GeminiClient avec un SDK simulé ---------------------------------------------


class FakeInteractions:
    def __init__(self, result):
        self.result = result
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def make_client(result):
    interactions = FakeInteractions(result)
    sdk = SimpleNamespace(interactions=interactions)
    return gc.GeminiClient("key", sdk=sdk, sleep=lambda d: None), interactions


IMG = Image.new("RGB", (8, 8))


def test_generate_image_request_and_response():
    payload = base64.b64encode(b"jpegdata").decode()
    result = SimpleNamespace(output_image=SimpleNamespace(data=payload), output_text=None)
    client, sdk = make_client(result)
    assert client.generate_image("m-img", "prompt", [IMG, IMG]) == b"jpegdata"
    kw = sdk.kwargs
    assert kw["model"] == "m-img"
    assert kw["input"][0] == {"type": "text", "text": "prompt"}
    assert [p["type"] for p in kw["input"][1:]] == ["image", "image"]
    assert kw["input"][1]["mime_type"] == "image/jpeg"
    assert kw["response_format"] == {"type": "image", "aspect_ratio": "3:4"}
    assert kw["timeout"] == gc.REQUEST_TIMEOUT


def test_generate_image_without_image_raises():
    result = SimpleNamespace(output_image=None, output_text="je ne peux pas")
    client, _ = make_client(result)
    with pytest.raises(errors.NoImageReturned):
        client.generate_image("m", "p", [IMG])


def test_generate_json_parses_schema():
    result = SimpleNamespace(output_text='{"title": "t", "description": "d"}')
    client, sdk = make_client(result)
    listing = client.generate_json("m-txt", "p", [IMG], Listing)
    assert listing == Listing(title="t", description="d")
    fmt = sdk.kwargs["response_format"]
    assert fmt["type"] == "text" and fmt["mime_type"] == "application/json"
    assert fmt["schema"]["properties"]["title"]


def test_generate_json_invalid_output():
    client, _ = make_client(SimpleNamespace(output_text="pas du json"))
    with pytest.raises(errors.InvalidModelOutput):
        client.generate_json("m", "p", [IMG], Listing)


def test_sdk_errors_are_mapped_and_chained():
    client, _ = make_client(FakeSdkError(401, "bad key"))
    with pytest.raises(errors.InvalidApiKey) as info:
        client.generate_image("m", "p", [IMG])
    assert isinstance(info.value.__cause__, FakeSdkError)
