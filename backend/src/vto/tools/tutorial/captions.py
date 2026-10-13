"""Sous-titres WebVTT à partir des instants relevés pendant le tournage."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Cue:
    start: float  # secondes depuis le début de la vidéo brute
    end: float
    text: str


def _timestamp(seconds: float) -> str:
    ms = round(seconds * 1000)
    hours, ms = divmod(ms, 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"


def to_webvtt(cues: list[Cue], offset: float = 0.0) -> str:
    """`offset` : durée coupée au début de la vidéo (les sous-titres avant sont retirés)."""
    blocks = []
    previous_end = 0.0
    for cue in cues:
        if cue.start < previous_end:
            raise ValueError(f"sous-titres qui se chevauchent : {cue.text!r}")
        previous_end = cue.end
        start, end = max(cue.start - offset, 0.0), cue.end - offset
        if end <= start:
            continue
        blocks.append(f"{_timestamp(start)} --> {_timestamp(end)}\n{cue.text}\n")
    return "WEBVTT\n\n" + "\n".join(blocks)
