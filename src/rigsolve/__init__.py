"""Build-aware dependency resolution for NVIDIA GPU Python stacks."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("rigsolve")
except PackageNotFoundError:  # pragma: no cover - source checkout without installation
    __version__ = "0.1.0"

__all__ = ["__version__"]
