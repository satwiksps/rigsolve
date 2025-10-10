"""Bundled, offline-first compatibility data for rigsolve."""

from __future__ import annotations

from importlib.resources import files
from typing import Any


def bundled_matrix_resource() -> Any:
    return files(__name__).joinpath("matrix.toml")


__all__ = ["bundled_matrix_resource"]
