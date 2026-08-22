"""Internal crash-safe file replacement."""

from __future__ import annotations

import os
import tempfile
from contextlib import suppress
from pathlib import Path


def atomic_write(path: Path, payload: str | bytes, *, create_parent: bool = True) -> None:
    if create_parent:
        path.parent.mkdir(parents=True, exist_ok=True)
    content = payload.encode("utf-8") if isinstance(payload, str) else payload
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(handle, "wb") as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        with suppress(FileNotFoundError):
            os.unlink(temporary_name)
        raise
