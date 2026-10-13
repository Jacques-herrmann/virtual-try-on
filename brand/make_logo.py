"""Génère les SVG de la marque Wearo à partir de Plus Jakarta Sans 800.

Les lettres sont converties en chemins : les SVG n'ont besoin d'aucune police.
À relancer seulement si le dessin du logo change :

    pip install fonttools brotli
    python brand/make_logo.py

Lit la police installée par `npm ci` dans `frontend/` et écrit `brand/*.svg`
ainsi que leurs copies utilisées par le front (`frontend/src/assets/`).
"""

import math
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONT = (
    ROOT / "frontend/node_modules/@fontsource/plus-jakarta-sans/files"
    / "plus-jakarta-sans-latin-800-normal.woff2"
)
INK = "#2E1F2B"
APRICOT = "#E8774A"

# Le « o » cintre, en unités de la police (1 em = units_per_em) : un cercle épais
# surmonté d'un crochet, comme sur la planche validée.
O_RADIUS = 0.19
O_STROKE = 0.107
O_CENTER_Y = 0.256  # au-dessus de la ligne de base
HOOK_STROKE = 0.06
HOOK_RADIUS = 0.072
NECK = 0.045
TRACKING = -0.04


def word_paths(font: TTFont, text: str) -> tuple[str, float]:
    """Chemin SVG (y vers le bas, ligne de base à 0) et largeur d'avance du mot."""
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    upm = font["head"].unitsPerEm
    x = 0.0
    parts = []
    for char in text:
        name = cmap[ord(char)]
        pen = SVGPathPen(glyphs)
        glyphs[name].draw(TransformPen(pen, (1 / upm, 0, 0, -1 / upm, x, 0)))
        parts.append(pen.getCommands())
        x += font["hmtx"][name][0] / upm + TRACKING
    return " ".join(parts), x


def o_hanger(cx: float, color: str) -> str:
    """Le « o » cintre centré horizontalement en `cx` (unités em, y vers le bas).

    Un court col monte du sommet du cercle puis s'enroule en crochet ouvert vers
    le bas à gauche, comme le crochet d'un cintre.
    """
    cy = -O_CENTER_Y
    neck = cy - O_RADIUS - NECK
    end_x = cx - HOOK_RADIUS * math.cos(math.radians(15))
    end_y = neck - HOOK_RADIUS + HOOK_RADIUS * math.sin(math.radians(15))
    hook = (
        f"M{cx:.4f} {cy - O_RADIUS:.4f} V{neck:.4f} "
        f"A{HOOK_RADIUS} {HOOK_RADIUS} 0 1 0 {end_x:.4f} {end_y:.4f}"
    )
    return (
        f'<path d="{hook}" fill="none" stroke="{color}" stroke-width="{HOOK_STROKE}" '
        f'stroke-linecap="round"/>'
        f'<circle cx="{cx:.4f}" cy="{cy:.4f}" r="{O_RADIUS}" fill="none" stroke="{color}" '
        f'stroke-width="{O_STROKE}"/>'
    )


def o_bounds() -> tuple[float, float, float, float]:
    """Boîte (x0, y0, x1, y1) du « o » cintre dessiné avec cx = 0."""
    cy = -O_CENTER_Y
    neck = cy - O_RADIUS - NECK
    return (
        -O_RADIUS - O_STROKE / 2,
        neck - 2 * HOOK_RADIUS - HOOK_STROKE / 2,
        O_RADIUS + O_STROKE / 2,
        cy + O_RADIUS + O_STROKE / 2,
    )


def centered_o(height: float, color: str) -> str:
    """Le « o » cintre mis à l'échelle (`height` en fraction du carré) et centré."""
    x0, y0, x1, y1 = o_bounds()
    scale = height / (y1 - y0)
    return (
        f'<g transform="translate(0.5 0.5) scale({scale:.4f}) '
        f'translate({-(x0 + x1) / 2:.4f} {-(y0 + y1) / 2:.4f})">{o_hanger(0, color)}</g>'
    )


def svg(view: tuple[float, float, float, float], body: str, label: str) -> str:
    x, y, w, h = view
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x:.4f} {y:.4f} {w:.4f} {h:.4f}" '
        f'role="img" aria-label="{label}">{body}</svg>\n'
    )


def main() -> None:
    font = TTFont(FONT)
    letters, advance = word_paths(font, "wear")
    o_cx = advance + 0.02 + O_RADIUS + O_STROKE / 2
    _, y0, x1, _ = o_bounds()
    right = o_cx + x1
    top = min(y0, -0.76)  # le crochet ou les hampes des lettres
    bottom = 0.02  # « wear » et le « o » reposent sur la ligne de base
    pad = 0.04
    view = (-pad, top - pad, right + 2 * pad, bottom - top + 2 * pad)

    outputs = {
        "logo.svg": svg(view, f'<path d="{letters}" fill="{INK}"/>' + o_hanger(o_cx, APRICOT), "Wearo"),
        "logo-light.svg": svg(view, f'<path d="{letters}" fill="#FBF7F2"/>' + o_hanger(o_cx, "#EF8D5D"), "Wearo"),
    }

    # Pictogramme seul et icône d'app : le « o » cintre centré dans un carré unité.
    outputs["logo-mark.svg"] = svg((0, 0, 1, 1), centered_o(0.86, APRICOT), "Wearo")
    outputs["app-icon.svg"] = svg(
        (0, 0, 1, 1),
        f'<rect width="1" height="1" rx="0.23" fill="{APRICOT}"/>' + centered_o(0.66, INK),
        "Wearo",
    )

    assets = ROOT / "frontend/src/assets"
    assets.mkdir(exist_ok=True)
    for name, content in outputs.items():
        (ROOT / "brand" / name).write_text(content, encoding="utf-8")
        if name in ("logo.svg", "logo-mark.svg"):
            (assets / name).write_text(content, encoding="utf-8")
        print(f"brand/{name}")


if __name__ == "__main__":
    main()
