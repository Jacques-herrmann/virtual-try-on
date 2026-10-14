"""Bruitages d'interface synthétisés (aucun fichier tiers, aucun droit à gérer)."""

import math
import random
import struct
import wave
from pathlib import Path

RATE = 44100


def _write(path: Path, samples: list[float]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(b"".join(
            struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples
        ))
    return path


def click() -> list[float]:
    """Clic de souris doux : petit choc boisé, 40 ms."""
    rng = random.Random(1)
    n = int(RATE * 0.04)
    out = []
    for i in range(n):
        t = i / RATE
        env = math.exp(-t * 180)
        tone = math.sin(2 * math.pi * 1900 * t) * 0.5 + math.sin(2 * math.pi * 3400 * t) * 0.2
        out.append((tone + rng.uniform(-1, 1) * 0.35) * env * 0.5)
    return out


def key() -> list[float]:
    """Frappe de clavier, plus discrète et plus sourde, 25 ms."""
    rng = random.Random(2)
    n = int(RATE * 0.025)
    out, low = [], 0.0
    for i in range(n):
        t = i / RATE
        low += (rng.uniform(-1, 1) - low) * 0.35  # bruit filtré : moins aigu
        out.append((low + math.sin(2 * math.pi * 900 * t) * 0.3) * math.exp(-t * 220) * 0.45)
    return out


def ding() -> list[float]:
    """« C'est prêt » : deux notes claires (mi puis la), 0,9 s."""
    out = []
    for i in range(int(RATE * 0.9)):
        t = i / RATE
        s = 0.0
        for start, freq in ((0.0, 1318.5), (0.12, 1760.0)):
            if t >= start:
                u = t - start
                env = math.exp(-u * 5) * min(u / 0.005, 1.0)
                phase = 2 * math.pi * freq * u
                s += (math.sin(phase) + 0.25 * math.sin(2 * phase)) * env
        out.append(s * 0.28)
    return out


SOUNDS = {"click": click, "key": key, "ding": ding}


def write_all(folder: Path) -> dict[str, Path]:
    return {name: _write(folder / f"{name}.wav", make()) for name, make in SOUNDS.items()}
