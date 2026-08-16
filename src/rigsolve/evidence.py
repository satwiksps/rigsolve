"""Plain-language labels for matrix evidence depth."""

from __future__ import annotations

_LABELS = {
    0: "metadata-backed",
    1: "install-tested",
    2: "import-tested",
    3: "GPU-tested",
}


def evidence_label(value: int) -> str:
    """Return the stable user-facing label for an evidence level."""

    return _LABELS.get(value, f"unknown evidence level {value}")


__all__ = ["evidence_label"]
