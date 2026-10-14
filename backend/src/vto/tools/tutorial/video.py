"""Post-production avec ffmpeg : coupe, mixage du son, encodage léger, affiche, flous."""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# mp4 H.264 lisible par WebView2 ; +faststart : la lecture commence avant la fin du chargement.
VIDEO = ["-c:v", "libx264", "-preset", "slow", "-crf", "28", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart"]
ENCODE = [*VIDEO, "-an"]
AUDIO = ["-c:a", "aac", "-b:a", "128k"]

MUSIC_VOLUME = 0.2
MUSIC_FADE = 2.0  # secondes de fondu en fin de vidéo


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


@dataclass(frozen=True)
class Sound:
    at: float  # secondes dans la vidéo finale (après la coupe)
    file: Path
    volume: float = 1.0


@dataclass
class Soundtrack:
    voices: list[Sound]
    effects: list[Sound]
    music: Path | None = None


def _mix(labels: list[str], out: str) -> str:
    if len(labels) == 1:
        return f"{labels[0]}anull[{out}]"
    return f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=longest[{out}]"


def mix_graph(track: Soundtrack, duration: float, first_input: int = 1) -> tuple[list[str], str]:
    """Entrées ffmpeg (après la vidéo, entrée 0) et graphe de filtres produisant [aout].

    Chaque son est décalé à son instant ; la musique est bouclée, baissée sous la voix
    (compression en side-chain), puis fondue en fin de vidéo.
    """
    inputs: list[str] = []
    index: dict[Path, int] = {}
    uses: dict[Path, int] = {}
    for sound in [*track.voices, *track.effects]:
        if sound.file not in index:
            index[sound.file] = first_input + len(index)
            inputs += ["-i", str(sound.file)]
        uses[sound.file] = uses.get(sound.file, 0) + 1

    parts = []
    for file, n in uses.items():
        outs = "".join(f"[s{index[file]}_{k}]" for k in range(n))
        split = f"asplit={n}" if n > 1 else "anull"
        parts.append(f"[{index[file]}:a]{split}{outs}")
    taken = dict.fromkeys(uses, 0)

    def place(sounds: list[Sound], prefix: str) -> list[str]:
        labels = []
        for i, sound in enumerate(sounds):
            src = f"[s{index[sound.file]}_{taken[sound.file]}]"
            taken[sound.file] += 1
            ms = max(round(sound.at * 1000), 0)
            parts.append(f"{src}adelay={ms}:all=1,volume={sound.volume}[{prefix}{i}]")
            labels.append(f"[{prefix}{i}]")
        return labels

    voice, effects = place(track.voices, "v"), place(track.effects, "e")
    final = []
    if voice:
        parts.append(_mix(voice, "voice"))
        if track.music is not None:
            parts.append("[voice]asplit=2[voiceout][voicekey]")
            final.append("[voiceout]")
        else:
            final.append("[voice]")
    if effects:
        parts.append(_mix(effects, "fx"))
        final.append("[fx]")
    if track.music is not None:
        m = first_input + len(index)
        inputs += ["-stream_loop", "-1", "-i", str(track.music)]
        parts.append(f"[{m}:a]atrim=0:{duration:.3f},volume={MUSIC_VOLUME}[bed]")
        if voice:
            parts.append("[bed][voicekey]sidechaincompress=threshold=0.02:ratio=8:attack=20:"
                         "release=400[ducked]")
        else:
            parts.append("[bed]anull[ducked]")
        fade_start = max(duration - MUSIC_FADE, 0)
        parts.append(f"[ducked]afade=t=out:st={fade_start:.3f}:d={MUSIC_FADE}[music]")
        final.append("[music]")
    if not final:
        raise ValueError("bande son vide")
    parts.append(_mix(final, "mixed"))
    parts.append(f"[mixed]atrim=0:{duration:.3f}[aout]")
    return inputs, ";".join(parts)


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        [shutil.which("ffprobe") or "ffprobe", "-v", "error", "-show_entries",
         "format=duration", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def finalize(
    raw: Path, mp4: Path, poster: Path | None, *, trim: float = 0.0,
    soundtrack: Soundtrack | None = None,
) -> None:
    """Coupe les `trim` premières secondes, mixe le son, encode, puis extrait l'affiche."""
    mp4.parent.mkdir(parents=True, exist_ok=True)
    source = ["-ss", f"{trim:.3f}", "-i", str(raw)]
    if soundtrack is None or not (soundtrack.voices or soundtrack.effects or soundtrack.music):
        _run([*source, *ENCODE, str(mp4)])
    else:
        duration = probe_duration(raw) - trim
        inputs, graph = mix_graph(soundtrack, duration)
        _run([*source, *inputs, "-filter_complex", graph, "-map", "0:v", "-map", "[aout]",
              *VIDEO, *AUDIO, str(mp4)])
    if poster is not None:
        _run(["-ss", "1.5", "-i", str(mp4), "-frames:v", "1", "-q:v", "4", str(poster)])


def edit(source: Path, mp4: Path, *, crop: Box | None, blurs: list[Blur]) -> None:
    """Vidéo enregistrée à la main (clé Gemini) : flous, recadrage, encodage."""
    mp4.parent.mkdir(parents=True, exist_ok=True)
    _run([
        "-i", str(source), "-filter_complex", blur_filter(blurs, crop), "-map", "[out]",
        *ENCODE, str(mp4),
    ])
