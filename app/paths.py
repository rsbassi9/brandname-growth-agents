"""Filesystem layout helpers.

Legacy data (memory/, outputs/, brand_context/, agent_instructions/) stays where
it is; the DATA_DIR env var relocation behavior from src/settings.py is honored.
Functions (not constants) so tests can point everything at tmp paths via env.
"""

from __future__ import annotations

import os
from pathlib import Path

from .settings import ROOT_DIR

__all__ = [
    "ROOT_DIR",
    "data_root",
    "memory_dir",
    "outputs_dir",
    "brand_context_dir",
    "agent_instructions_dir",
]


def data_root() -> Path:
    raw = os.getenv("DATA_DIR", "")
    return Path(raw).resolve() if raw else ROOT_DIR


def memory_dir() -> Path:
    return data_root() / "memory"


def outputs_dir() -> Path:
    return data_root() / "outputs"


def brand_context_dir() -> Path:
    return ROOT_DIR / "brand_context"


def agent_instructions_dir() -> Path:
    return ROOT_DIR / "agent_instructions"
