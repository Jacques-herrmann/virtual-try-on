"""Voix off ElevenLabs, mise en cache : seul un texte nouveau ou modifié est facturé.

Réglage `tools/tutorial/voice.json` (commité) : {"voice_id": "...", "model_id": "..."}.
Clé `ELEVENLABS_API_KEY` dans l'environnement ou `.env` (jamais commitée), utile seulement
quand un texte manque dans le cache.
"""

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import httpx

API = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
DEFAULT_MODEL = "eleven_multilingual_v2"


class VoiceError(Exception):
    pass


@dataclass(frozen=True)
class VoiceConfig:
    voice_id: str
    model_id: str = DEFAULT_MODEL

    @classmethod
    def load(cls, file: Path) -> "VoiceConfig | None":
        """None sans fichier : la vidéo est tournée sans voix off."""
        if not file.is_file():
            return None
        data = json.loads(file.read_text(encoding="utf-8"))
        return cls(voice_id=data["voice_id"], model_id=data.get("model_id", DEFAULT_MODEL))


def cache_path(folder: Path, config: VoiceConfig, text: str) -> Path:
    digest = hashlib.sha256(f"{config.voice_id}\n{config.model_id}\n{text}".encode()).hexdigest()
    return folder / f"{digest[:16]}.mp3"


def synthesize(
    texts: list[str],
    folder: Path,
    config: VoiceConfig,
    *,
    api_key: str | None = None,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Path]:
    """Un fichier mp3 par texte, depuis le cache ou ElevenLabs."""
    api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")
    files: dict[str, Path] = {}
    missing = [t for t in dict.fromkeys(texts) if not cache_path(folder, config, t).is_file()]
    if missing and not api_key:
        raise VoiceError(
            f"{len(missing)} phrase(s) sans voix en cache : ELEVENLABS_API_KEY manquante "
            "(fichier .env)."
        )
    with httpx.Client(transport=transport, timeout=60) as client:
        for text in dict.fromkeys(texts):
            path = cache_path(folder, config, text)
            if not path.is_file():
                response = client.post(
                    API.format(voice_id=config.voice_id),
                    params={"output_format": "mp3_44100_128"},
                    headers={"xi-api-key": api_key, "accept": "audio/mpeg"},
                    json={"text": text, "model_id": config.model_id},
                )
                if response.status_code != 200:
                    raise VoiceError(
                        f"ElevenLabs a refusé la phrase « {text[:40]}… » : "
                        f"HTTP {response.status_code} {response.text[:200]}"
                    )
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(response.content)
            files[text] = path
    return files


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
         str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())
