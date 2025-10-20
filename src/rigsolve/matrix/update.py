"""Conditional, cached downloads for ``rigsolve matrix update``."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from rigsolve.errors import MatrixError

from .schema import MatrixValidationError
from .store import MatrixStore, load_matrix, save_matrix

DEFAULT_UPDATE_URL = (
    "https://raw.githubusercontent.com/satwiksps/rigsolve/main/src/rigsolve/data/matrix.toml"
)
_MAX_MATRIX_BYTES = 32 * 1024 * 1024


class MatrixUpdateError(MatrixError):
    """A matrix update failed without modifying the installed cache."""


@dataclass(frozen=True, slots=True)
class MatrixUpdateResult:
    store: MatrixStore
    changed: bool
    not_modified: bool
    url: str
    etag: str | None = None
    last_modified: str | None = None
    cache_path: Path | None = None


def default_cache_dir() -> Path:
    override = os.environ.get("RIGSOLVE_CACHE_DIR")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA")
        if root:
            return Path(root) / "rigsolve"
    root = os.environ.get("XDG_CACHE_HOME")
    if root:
        return Path(root) / "rigsolve"
    return Path.home() / ".cache" / "rigsolve"


def _atomic_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as temporary:
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        with suppress(FileNotFoundError):
            os.unlink(temporary_name)
        raise


def _read_metadata(path: Path) -> dict[str, str]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(value) for key, value in parsed.items() if value is not None}


def fetch_update(
    url: str = DEFAULT_UPDATE_URL,
    *,
    current: MatrixStore | None = None,
    cache_dir: str | os.PathLike[str] | None = None,
    destination: str | os.PathLike[str] | None = None,
    merge: bool = True,
    timeout: float = 20.0,
    headers: Mapping[str, str] | None = None,
) -> MatrixUpdateResult:
    """Fetch and validate an update using ETag/Last-Modified revalidation.

    Neither the cache nor ``destination`` is replaced until the complete
    response has parsed and passed schema validation.
    """

    root = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    matrix_path = root / "matrix.toml"
    metadata_path = root / "matrix.http.json"
    metadata = _read_metadata(metadata_path)
    request_headers = {
        "Accept": "application/toml, text/plain;q=0.9",
        "User-Agent": "rigsolve-matrix-updater/0.1",
    }
    if metadata.get("url") == url:
        if metadata.get("etag"):
            request_headers["If-None-Match"] = metadata["etag"]
        if metadata.get("last_modified"):
            request_headers["If-Modified-Since"] = metadata["last_modified"]
    if headers:
        request_headers.update(headers)

    response_headers: Mapping[str, str]
    try:
        with urlopen(Request(url, headers=request_headers), timeout=timeout) as response:
            length = response.headers.get("Content-Length")
            if length and int(length) > _MAX_MATRIX_BYTES:
                raise MatrixUpdateError("remote matrix exceeds the 32 MiB safety limit")
            payload = response.read(_MAX_MATRIX_BYTES + 1)
            if len(payload) > _MAX_MATRIX_BYTES:
                raise MatrixUpdateError("remote matrix exceeds the 32 MiB safety limit")
            response_headers = response.headers
    except HTTPError as exc:
        if exc.code != 304:
            raise MatrixUpdateError(f"matrix update returned HTTP {exc.code}") from exc
        if not matrix_path.exists():
            raise MatrixUpdateError("server returned 304 but no cached matrix exists") from exc
        cached = load_matrix(matrix_path)
        selected = current.merge(cached) if current is not None and merge else cached
        if destination is not None:
            save_matrix(destination, selected)
        return MatrixUpdateResult(
            store=selected,
            changed=False,
            not_modified=True,
            url=url,
            etag=metadata.get("etag"),
            last_modified=metadata.get("last_modified"),
            cache_path=matrix_path,
        )
    except (URLError, OSError, TimeoutError) as exc:
        raise MatrixUpdateError(f"cannot fetch matrix update: {exc}") from exc

    try:
        remote = MatrixStore.from_toml(payload)
    except MatrixValidationError as exc:
        raise MatrixUpdateError(f"remote matrix failed validation: {exc}") from exc

    old_digest: str | None = None
    if matrix_path.exists():
        with suppress(MatrixValidationError):
            old_digest = load_matrix(matrix_path).digest
    save_matrix(matrix_path, remote)
    etag = response_headers.get("ETag")
    last_modified = response_headers.get("Last-Modified")
    _atomic_text(
        metadata_path,
        json.dumps(
            {"url": url, "etag": etag, "last_modified": last_modified},
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    selected = current.merge(remote) if current is not None and merge else remote
    if destination is not None:
        save_matrix(destination, selected)
    return MatrixUpdateResult(
        store=selected,
        changed=old_digest != remote.digest,
        not_modified=False,
        url=url,
        etag=etag,
        last_modified=last_modified,
        cache_path=matrix_path,
    )


def load_with_cached_update(
    bundled: MatrixStore | None = None,
    *,
    cache_dir: str | os.PathLike[str] | None = None,
) -> MatrixStore:
    """Merge a previously validated cache over the bundled offline matrix."""

    base = bundled or load_matrix()
    path = (Path(cache_dir) if cache_dir is not None else default_cache_dir()) / "matrix.toml"
    if not path.exists():
        return base
    try:
        return base.merge(load_matrix(path))
    except MatrixValidationError:
        # A corrupt user cache must never make offline diagnosis unusable.
        return base


__all__ = [
    "DEFAULT_UPDATE_URL",
    "MatrixUpdateError",
    "MatrixUpdateResult",
    "default_cache_dir",
    "fetch_update",
    "load_with_cached_update",
]
