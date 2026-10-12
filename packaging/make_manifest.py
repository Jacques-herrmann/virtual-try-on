"""Génère `latest.json` pour une Release (appelé par la CI).

    python packaging/make_manifest.py --installer packaging/Output/VirtualTryOn-Setup-X.Y.Z.exe \
        --version X.Y.Z [--notes-file notes.txt] --out latest.json
"""

import argparse
import hashlib
import json
from pathlib import Path

from vto.updates.manifest import Manifest

REPO = "Jacques-herrmann/virtual-try-on"
DEFAULT_MINIMUM_FILE = Path(__file__).with_name("minimum_version.txt")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--minimum-file", type=Path, default=DEFAULT_MINIMUM_FILE)
    parser.add_argument("--notes-file", type=Path)
    parser.add_argument("--repo", default=REPO)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    notes = args.notes_file.read_text(encoding="utf-8").strip() if args.notes_file else ""
    data = {
        "version": args.version,
        "minimum_version": args.minimum_file.read_text(encoding="utf-8").strip(),
        "url": f"https://github.com/{args.repo}/releases/download/v{args.version}/"
        f"{args.installer.name}",
        "sha256": sha256(args.installer),
        "notes": notes,
    }
    try:
        # Même validation que l'app : un manifeste refusé par l'app ne doit jamais être publié.
        Manifest(**data)
    except ValueError as exc:
        raise SystemExit(f"Manifeste invalide : {exc}") from exc
    args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
