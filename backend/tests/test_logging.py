import logging

from vto.core import paths
from vto.core.logging import setup_logging


def test_messages_go_to_log_file(data_dir):
    root = logging.getLogger()
    before = list(root.handlers)
    try:
        setup_logging()
        setup_logging()  # idempotent
        logging.getLogger("vto.test").info("bonjour journal")
        for h in root.handlers:
            h.flush()
        log_file = paths.logs_dir() / "vto.log"
        assert "bonjour journal" in log_file.read_text(encoding="utf-8")
        assert sum(getattr(h, "baseFilename", None) == str(log_file) for h in root.handlers) == 1
    finally:
        for h in root.handlers[:]:
            if h not in before:
                h.close()
                root.removeHandler(h)
