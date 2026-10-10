import io

from PIL import Image

from vto.core import images


def test_load_applies_exif_orientation(tmp_path):
    path = tmp_path / "rotated.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation : rotation de 90°
    Image.new("RGB", (40, 20)).save(path, exif=exif)
    assert images.load_image(path).size == (20, 40)


def test_load_converts_to_rgb(tmp_path):
    path = tmp_path / "alpha.png"
    Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(path)
    assert images.load_image(path).mode == "RGB"


def test_load_reads_avif(tmp_path):
    path = tmp_path / "x.avif"
    Image.new("RGB", (16, 16), "red").save(path)
    assert images.load_image(path).size == (16, 16)


def test_resize_max_keeps_small_images():
    img = Image.new("RGB", (800, 600))
    assert images.resize_max(img).size == (800, 600)


def test_resize_max_downscales_keeping_ratio():
    img = Image.new("RGB", (4000, 3000))
    assert images.resize_max(img).size == (1536, 1152)


def test_is_supported_image():
    for name in ("a.JPG", "b.webp", "c.avif", "d.jpeg", "e.png"):
        assert images.is_supported_image(name)
    assert not images.is_supported_image("notes.txt")


def test_to_jpeg_bytes_and_save_jpeg(tmp_path):
    img = Image.new("RGB", (10, 10), "blue")
    assert Image.open(io.BytesIO(images.to_jpeg_bytes(img))).format == "JPEG"
    out = tmp_path / "sub" / "o.jpg"
    images.save_jpeg(Image.new("RGB", (10, 10)), out)
    assert Image.open(out).format == "JPEG"
