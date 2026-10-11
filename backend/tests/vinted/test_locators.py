import pytest

from vto.vinted.locators import LocatorNotFound, first_visible, resolve
from vto.vinted.schema import CssLocator, LabelLocator, RoleLocator, TextLocator


class FakeLocator:
    def __init__(self, page, call):
        self.page = page
        self.call = call

    @property
    def first(self):
        return self

    def is_visible(self):
        return self.call in self.page.visible


class FakePage:
    """Enregistre les appels ; un localisateur est visible si son appel est dans `visible`."""

    def __init__(self, visible=(), appear_after=None):
        self.visible = set(visible)
        self.calls = []
        self.waits = 0
        self.appear_after = appear_after  # (nombre d'attentes, appel qui devient visible)

    def _record(self, *call):
        self.calls.append(call)
        return FakeLocator(self, call)

    def locator(self, selector):
        return self._record("locator", selector)

    def get_by_label(self, text, exact=False):
        return self._record("label", text, exact)

    def get_by_text(self, text, exact=False):
        return self._record("text", text, exact)

    def get_by_role(self, role, name=None, exact=False):
        return self._record("role", role, name, exact)

    def wait_for_timeout(self, ms):
        self.waits += 1
        if self.appear_after and self.waits >= self.appear_after[0]:
            self.visible.add(self.appear_after[1])


@pytest.mark.parametrize(
    ("alt", "call"),
    [
        (CssLocator(css="[data-testid='title']"), ("locator", "[data-testid='title']")),
        (LabelLocator(label="Titre"), ("label", "Titre", True)),
        (TextLocator(text="Robes"), ("text", "Robes", True)),
        (RoleLocator(role="button", name="Ajouter"), ("role", "button", "Ajouter", True)),
    ],
)
def test_resolve_forms(alt, call):
    page = FakePage()
    resolve(page, alt)
    assert page.calls == [call]


TRICKY = "Robe \"d'été\" {taille} \ ${x}"


@pytest.mark.parametrize(
    ("alt", "call"),
    [
        (LabelLocator(label="{label}"), ("label", TRICKY, True)),
        (TextLocator(text="Marque : {label}"), ("text", f"Marque : {TRICKY}", True)),
        (RoleLocator(role="option", name="{label}"), ("role", "option", TRICKY, True)),
    ],
)
def test_label_is_substituted_literally(alt, call):
    page = FakePage()
    resolve(page, alt, label=TRICKY)
    assert page.calls == [call]


def test_css_is_never_substituted():
    page = FakePage()
    resolve(page, CssLocator(css="[title='{label}']"), label="x")
    assert page.calls == [("locator", "[title='{label}']")]


def test_other_braces_stay_literal_without_label():
    page = FakePage()
    resolve(page, TextLocator(text="{label} {autre}"))
    assert page.calls == [("text", "{label} {autre}", True)]


ALTERNATIVES = [CssLocator(css="#a"), LabelLocator(label="B")]


def test_first_visible_returns_first_visible_in_order():
    page = FakePage(visible={("label", "B", True)})
    found = first_visible(page, "title", ALTERNATIVES, timeout=0)
    assert found.call == ("label", "B", True)


def test_first_visible_prefers_earlier_alternative():
    page = FakePage(visible={("locator", "#a"), ("label", "B", True)})
    assert first_visible(page, "title", ALTERNATIVES, timeout=0).call == ("locator", "#a")


def test_first_visible_waits_until_something_appears():
    page = FakePage(appear_after=(3, ("locator", "#a")))
    found = first_visible(page, "title", ALTERNATIVES, timeout=60_000)
    assert found.call == ("locator", "#a")
    assert page.waits == 3


def test_first_visible_raises_with_name():
    with pytest.raises(LocatorNotFound) as exc:
        first_visible(FakePage(), "brand_option", ALTERNATIVES, timeout=0)
    assert exc.value.name == "brand_option"
    assert "brand_option" in str(exc.value)


def test_first_visible_passes_label():
    page = FakePage(visible={("role", "option", "Zara", True)})
    alts = [RoleLocator(role="option", name="{label}")]
    assert first_visible(page, "brand_option", alts, timeout=0, label="Zara").call[2] == "Zara"
