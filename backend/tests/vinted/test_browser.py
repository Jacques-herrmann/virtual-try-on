import pytest
from playwright.sync_api import Error

from samples import minimal
from vto.core import paths
from vto.core.errors import VtoError
from vto.vinted import browser
from vto.vinted.schema import VintedData

# Messages relevés le 2026-10-11 (Playwright 1.63, Windows 11).
NOT_FOUND = (
    "BrowserType.launch_persistent_context: Chromium distribution '{channel}' is not found at "
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe\n"
    'Run "playwright install {channel}"'
)
# Profil déjà ouvert, fenêtre visible : Chrome confie l'ouverture à l'instance existante et
# sort avec le code 0 ; en headless il sortirait avec le code 21.
PROFILE_LOCKED = (
    "BrowserType.launch_persistent_context: Target page, context or browser has been closed\n"
    "Browser logs:\n\n<launching> chrome.exe --user-data-dir=...\n"
    "  - [pid=22112] <process did exit: exitCode=0, signal=null>"
)


class FakeChromium:
    def __init__(self, outcomes):
        self.outcomes = outcomes  # canal → contexte renvoyé ou exception levée
        self.launches = []

    def launch_persistent_context(self, user_data_dir, **kwargs):
        self.launches.append((user_data_dir, kwargs))
        outcome = self.outcomes[kwargs["channel"]]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakePlaywright:
    def __init__(self, **outcomes):
        self.chromium = FakeChromium(outcomes)


def missing(channel):
    return Error(NOT_FOUND.format(channel=channel))


def test_uses_chrome_first(data_dir):
    pw = FakePlaywright(chrome="ctx-chrome", msedge="ctx-edge")
    assert browser.open_context(pw) == "ctx-chrome"
    user_data_dir, kwargs = pw.chromium.launches[0]
    assert user_data_dir == str(paths.browser_profile_dir())
    assert kwargs["channel"] == "chrome"
    assert kwargs["headless"] is False
    assert kwargs["locale"] == "fr-FR"
    assert kwargs["no_viewport"] is True
    assert "--start-maximized" in kwargs["args"]


def test_falls_back_to_edge(data_dir):
    pw = FakePlaywright(chrome=missing("chrome"), msedge="ctx-edge")
    assert browser.open_context(pw) == "ctx-edge"
    assert [k["channel"] for _, k in pw.chromium.launches] == ["chrome", "msedge"]


def test_no_browser(data_dir):
    pw = FakePlaywright(chrome=missing("chrome"), msedge=missing("msedge"))
    with pytest.raises(browser.BrowserMissing) as exc:
        browser.open_context(pw)
    assert isinstance(exc.value, VtoError)
    assert "Chrome" in exc.value.user_message


def test_profile_in_use(data_dir):
    pw = FakePlaywright(chrome=Error(PROFILE_LOCKED), msedge="ctx-edge")
    with pytest.raises(browser.ProfileInUse):
        browser.open_context(pw)
    assert len(pw.chromium.launches) == 1  # inutile d'essayer Edge sur le même profil


def test_other_errors_propagate(data_dir):
    pw = FakePlaywright(chrome=Error("BrowserType.launch_persistent_context: boom"))
    with pytest.raises(Error):
        browser.open_context(pw)


class FakeLocator:
    def __init__(self, visible):
        self.visible = visible

    @property
    def first(self):
        return self

    def is_visible(self):
        return self.visible


class FakePage:
    def __init__(self, url, logged_in):
        self.url = url
        self.logged_in = logged_in
        self.visited = []

    def goto(self, url):
        self.visited.append(url)
        self.url = url

    def locator(self, selector):
        return FakeLocator(self.logged_in and selector == "#logged_in")

    def wait_for_timeout(self, ms):
        pass


@pytest.fixture
def data():
    return VintedData.model_validate(minimal())


def test_is_logged_in_goes_home_first(data):
    page = FakePage("about:blank", logged_in=True)
    assert browser.is_logged_in(page, data, timeout=0) is True
    assert page.visited == ["https://www.vinted.fr"]


def test_is_logged_in_stays_on_vinted(data):
    page = FakePage("https://www.vinted.fr/items/new", logged_in=False)
    assert browser.is_logged_in(page, data, timeout=0) is False
    assert page.visited == []
