"""Logging configuration for council."""

import logging
import os
import sys
from pathlib import Path


def setup_logger(log_file: str = "council.log") -> logging.Logger:
    """Configure and return the council logger.

    File: everything (DEBUG+) — full audit trail in council.log
    Stderr: only warnings/errors — display.py handles all pretty output

    Set COUNCIL_LOG_LEVEL=DEBUG to see everything on stderr too.
    """
    logger = logging.getLogger("council")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d [%(thread)d] %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler — everything
    fh = logging.FileHandler(log_file, mode="a")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Stderr handler — warnings/errors only (display.py handles pretty output)
    stderr_level = os.environ.get("COUNCIL_LOG_LEVEL", "WARNING").upper()
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(getattr(logging, stderr_level, logging.WARNING))
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    return logger


log = setup_logger()
