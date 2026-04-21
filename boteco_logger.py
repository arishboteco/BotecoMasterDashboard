"""Centralized logging configuration for Boteco Dashboard."""

import logging
import os
import sys


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure root logger with console and optional file handlers."""
    root = logging.getLogger("boteco")
    if root.handlers:
        return root

    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)

    log_file = os.environ.get("BOTECO_LOG_FILE")
    if log_file:
        os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)

    return root


def get_logger(name: str) -> logging.Logger:
    """Get a logger scoped to the given module name."""
    return logging.getLogger(f"boteco.{name.split('.')[-1]}")
