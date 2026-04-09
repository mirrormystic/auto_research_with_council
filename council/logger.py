"""Logging configuration for council."""

import logging
import sys
from pathlib import Path


def setup_logger(log_file: str = "council.log") -> logging.Logger:
    """Configure and return the council logger. Writes to file + stderr."""
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

    # Stderr handler — INFO and above
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    return logger


log = setup_logger()
