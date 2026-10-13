"""Post-production avec ffmpeg : coupe, encodage léger pour l'app, affiche, flous."""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# mp4 H.264 lisible par WebView2 ; +faststart : la lecture commence avant la fin du chargement.
ENCODE = ["-c:v", "libx264", "-preset", "slow", "-crf", "28", "-pix_fmt", "yuv420p",
          "-movflags", "+faststart", "-an"]


class MissingFfmpeg(Exception):
    pass


@dataclass(frozen=True)
class Box:
    x: int
    y: int
    w: int
    h: int

    @classmethod
    def parse(cls, text: str) -> "Box":
        x, y, w, h = (int(v) for v in text.split(","))
        return cls(x, y, w, h)


@dataclass(frozen=True)
class Blur:
    box: Box
    start: float | None = None  # secondes ; None = toute la vidéo
    end: float | None = None

    @classmethod
    def parse(cls, text: str) -> "Blur":
        """« x,y,w,h » ou « x,y,w,h@début-fin » (secondes)."""
        box, _, span = text.partition("@")
        if not span:
            return cls(Box.parse(box))
        start, end = (float(v) for v in span.split("-"))
        return cls(Box.parse(box), start, end)


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe is None:
        raise MissingFfmpeg("ffmpeg introuvable : l'installer (winget install Gyan.FFmpeg).")
    return exe


def _run(args: list[str]) -> None:
    subprocess.run([_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def blur_filter(blurs: list[Blur], crop: Box | None) -> str:
    """Graphe de filtres : flous (coordonnées de la vidéo d'origine), puis recadrage."""
    parts, current = [], "0:v"
    for i, blur in enumerate(blurs):
        b = blur.box
        enable = (
            f":enable='between(t,{blur.start},{blur.end})'" if blur.start is not None else ""
        )
        parts.append(
            f"[{current}]split[base{i}][src{i}];"
            f"[src{i}]crop={b.w}:{b.h}:{b.x}:{b.y},boxblur=20:2[blur{i}];"
            f"[base{i}][blur{i}]overlay={b.x}:{b.y}{enable}[v{i}]"
        )
        current = f"v{i}"
    tail = f"[{current}]"
    if crop is not None:
        tail += f"crop={crop.w}:{crop.h}:{crop.x}:{crop.y},"
    # Largeur 1280 au plus, dimensions paires (exigées par H.264).
    tail += "scale='min(1280,iw)':-2[out]"
    return ";".join([*parts, tail])


def finalize(raw: Path, mp4: Path, poster: Path | None, *, trim: float = 0.0) -> None:
    """Coupe les `trim` premières secondes, encode, puis extrait l'affiche."""
    mp4.parent.mkdir(parents=True, exist_ok=True)
    _run(["-ss", f"{trim:.3f}", "-i", str(raw), *ENCODE, str(mp4)])
    if poster is not None:
        _run(["-ss", "1.5", "-i", str(mp4), "-frames:v", "1", "-q:v", "4", str(poster)])


def edit(source: Path, mp4: Path, *, crop: Box | None, blurs: list[Blur]) -> None:
    """Vidéo enregistrée à la main (clé Gemini) : flous, recadrage, encodage."""
    mp4.parent.mkdir(parents=True, exist_ok=True)
    _run([
        "-i", str(source), "-filter_complex", blur_filter(blurs, crop), "-map", "[out]",
        *ENCODE, str(mp4),
    ])
