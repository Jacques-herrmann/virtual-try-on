import shutil

import pytest

from samples import minimal
from vto.core import paths
from vto.core.errors import VtoError
from vto.vinted import browser
from vto.vinted.schema import VintedData


class FakeProcess:
    def __init__(self, args, exits=False):
        self.args = args
        self.exits = exits  # True : le navigateur confie l'ouverture à une instance existante
        self.terminated = False
        self.killed = False

    def poll(self):
        return 0 if self.exits or self.terminated or self.killed else None

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return 0


class FakeCdpSession:
    def __init__(self, log):
        self.log = log

    def send(self, method):
        self.log.append(method)


class FakeContext:
    def __init__(self):
        self.pages = ["page"]

    def new_page(self):
        return "nouvelle page"


class FakeBrowser:
    def __init__(self):
        self.contexts = [FakeContext()]
        self.sent = []

    def new_browser_cdp_session(self):
        return FakeCdpSession(self.sent)


class FakeChromium:
    def __init__(self):
        self.endpoints = []
        self.kwargs = []
        self.browser = FakeBrowser()

    def connect_over_cdp(self, endpoint, **kwargs):
        self.endpoints.append(endpoint)
        self.kwargs.append(kwargs)
        return self.browser


class FakePlaywright:
    def __init__(self):
        self.chromium = FakeChromium()


@pytest.fixture
def launcher(monkeypatch, data_dir):
    """Remplace la recherche de l'exécutable, le lancement du processus et l'attente du port."""
    state = type("State", (), {})()
    state.installed = {"chrome": "C:/Chrome/chrome.exe", "msedge": "C:/Edge/msedge.exe"}
    state.processes = []
    state.exits = False
    state.port_ready = True

    monkeypatch.setattr(browser, "find_executable", lambda name: state.installed.get(name))

    def popen(args, **kwargs):
        process = FakeProcess(args, exits=state.exits)
        state.processes.append(process)
        return process

    monkeypatch.setattr(browser.subprocess, "Popen", popen)
    monkeypatch.setattr(browser, "free_port", lambda: 49152)
    def wait_for_port(port, process, timeout):
        return state.port_ready and process.poll() is None

    monkeypatch.setattr(browser, "_wait_for_port", wait_for_port)
    return state


def test_launches_real_chrome_on_dedicated_profile(launcher):
    pw = FakePlaywright()
    session = browser.open_context(pw)
    args = launcher.processes[0].args
    assert args[0] == "C:/Chrome/chrome.exe"
    assert f"--user-data-dir={paths.browser_profile_dir()}" in args
    assert "--remote-debugging-port=49152" in args
    assert "--no-first-run" in args and "--no-default-browser-check" in args
    assert not any("automation" in a.lower() for a in args)
    assert pw.chromium.endpoints == ["http://127.0.0.1:49152"]
    assert pw.chromium.kwargs[0]["no_defaults"] is True
    assert session.pages == ["page"]
    assert session.new_page() == "nouvelle page"


def test_falls_back_to_edge(launcher):
    del launcher.installed["chrome"]
    browser.open_context(FakePlaywright())
    assert launcher.processes[0].args[0] == "C:/Edge/msedge.exe"


def test_no_browser(launcher):
    launcher.installed.clear()
    with pytest.raises(browser.BrowserMissing) as exc:
        browser.open_context(FakePlaywright())
    assert isinstance(exc.value, VtoError)
    assert launcher.processes == []


def test_profile_in_use(launcher):
    # Profil déjà ouvert : le nouveau processus confie l'ouverture à l'instance existante et
    # quitte aussitôt ; le port de débogage n'ouvre jamais.
    launcher.exits = True
    pw = FakePlaywright()
    with pytest.raises(browser.ProfileInUse):
        browser.open_context(pw)
    assert pw.chromium.endpoints == []


def test_port_never_ready(launcher):
    launcher.port_ready = False
    with pytest.raises(VtoError):
        browser.open_context(FakePlaywright())
    assert launcher.processes[0].killed


def test_extra_args(launcher):
    browser.open_context(FakePlaywright(), extra_args=["--headless=new"])
    assert "--headless=new" in launcher.processes[0].args


def test_close_quits_browser(launcher):
    pw = FakePlaywright()
    session = browser.open_context(pw)
    session.close()
    assert pw.chromium.browser.sent == ["Browser.close"]
    assert launcher.processes[0].terminated is False  # fermeture propre suffisante


def test_find_executable_uses_known_locations(monkeypatch, tmp_path):
    exe = tmp_path / "Google" / "Chrome" / "Application" / "chrome.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path))
    monkeypatch.delenv("PROGRAMFILES(X86)", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert browser.find_executable("chrome") == str(exe)
    assert browser.find_executable("msedge") is None


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

    def goto(self, url, **kwargs):
        self.visited.append((url, kwargs.get("wait_until")))
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
    # Vinted n'émet pas toujours « load » : on n'attend que le document.
    assert page.visited == [("https://www.vinted.fr", "domcontentloaded")]


def test_is_logged_in_stays_on_vinted(data):
    page = FakePage("https://www.vinted.fr/items/new", logged_in=False)
    assert browser.is_logged_in(page, data, timeout=0) is False
    assert page.visited == []


@pytest.mark.browser
def test_real_chrome_starts_and_quits(data_dir):
    """Lance le vrai Chrome (ou Edge) installé, sans fenêtre, puis le ferme."""
    from playwright.sync_api import sync_playwright

    if not (browser.find_executable("chrome") or browser.find_executable("msedge")):
        pytest.skip("ni Chrome ni Edge installé")
    with sync_playwright() as pw:
        session = browser.open_context(pw, extra_args=["--headless=new"])
        try:
            page = session.pages[0] if session.pages else session.new_page()
            assert page.evaluate("navigator.webdriver") is False
        finally:
            session.close()
        assert session.process.poll() is not None
