"""Icône de l'app (`packaging/icon.ico`) et favicon du front, rendus depuis `brand/app-icon.svg`.

    python packaging/make_icon.py

Le SVG est rendu par Chromium (Playwright, déjà une dépendance de l'app), puis PIL
assemble l'ICO multi-tailles.
"""

import io
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "brand" / "app-icon.svg"
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def render(svg: str, size: int) -> Image.Image:
    sized = svg.replace("<svg ", f'<svg width="{size}" height="{size}" ', 1)
    html = (
        "<html><body style='margin:0;background:transparent'>"
        f"<div style='width:{size}px;height:{size}px'>{sized}</div></body></html>"
    )
    box = {"x": 0, "y": 0, "width": size, "height": size}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": size, "height": size})
        page.set_content(html)
        png = page.screenshot(omit_background=True, clip=box)
        browser.close()
    return Image.open(io.BytesIO(png)).convert("RGBA")


def main() -> None:
    svg = SOURCE.read_text(encoding="utf-8")
    # Chaque taille est rendue à part : un 16 px rendu directement reste plus net
    # qu'un 256 px réduit.
    images = {size: render(svg, size) for size in ICO_SIZES}
    # L'exécutable (PyInstaller) et la fenêtre de l'app (lancée depuis les sources aussi).
    targets = (Path(__file__).with_name("icon.ico"), ROOT / "backend" / "src" / "vto" / "icon.ico")
    for target in targets:
        images[256].save(
            target,
            sizes=[(s, s) for s in ICO_SIZES],
            append_images=[images[s] for s in ICO_SIZES if s != 256],
        )
    render(svg, 64).save(ROOT / "frontend" / "public" / "favicon.png")
    print("packaging/icon.ico, backend/src/vto/icon.ico, frontend/public/favicon.png")


if __name__ == "__main__":
    main()
