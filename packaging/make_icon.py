"""Icône provisoire (`packaging/icon.ico`) en attendant celle du produit."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 256
image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((8, 8, SIZE - 8, SIZE - 8), radius=48, fill=(13, 148, 136))
try:
    font = ImageFont.truetype("segoeuib.ttf", 110)
except OSError:
    font = ImageFont.load_default(110)
draw.text((SIZE / 2, SIZE / 2), "VT", font=font, fill="white", anchor="mm")
image.save(
    Path(__file__).with_name("icon.ico"),
    sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
