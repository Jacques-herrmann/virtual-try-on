"""Journal technique dans <données>/logs/vto.log (les messages client restent à part)."""

import logging
from logging.handlers import RotatingFileHandler

from vto.core import paths

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(console: bool = False, level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    log_file = paths.logs_dir() / "vto.log"
    if not any(getattr(h, "baseFilename", None) == str(log_file) for h in root.handlers):
        handler = RotatingFileHandler(
            log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root.addHandler(handler)
    if console and not any(type(h) is logging.StreamHandler for h in root.handlers):
        stream = logging.StreamHandler()
        stream.setFormatter(logging.Formatter("%(message)s"))
        stream.setLevel(logging.WARNING)
        root.addHandler(stream)
