"""Small conditional HTTP cache shared by offline matrix harvesters."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class HarvestHTTPError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FetchResult:
    url: str
    body: bytes
    status: int
    from_cache: bool
    not_modified: bool
    etag: str | None = None
    last_modified: str | None = None

    def json(self) -> object:
        return json.loads(self.body.decode("utf-8"))

    def text(self, encoding: str = "utf-8") -> str:
        return self.body.decode(encoding)


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(handle, "wb") as temporary:
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        with suppress(FileNotFoundError):
            os.unlink(temporary_name)
        raise


class CachedHTTPClient:
    """urllib-based HTTP client with per-URL ETag/Last-Modified caching."""

    def __init__(
        self,
        cache_dir: str | os.PathLike[str],
        *,
        user_agent: str = "rigsolve-harvester/0.1",
        timeout: float = 30.0,
        max_bytes: int = 64 * 1024 * 1024,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_bytes = max_bytes

    def _paths(self, url: str) -> tuple[Path, Path]:
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{key}.body", self.cache_dir / f"{key}.json"

    @staticmethod
    def _metadata(path: Path) -> dict[str, str]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {}
        if not isinstance(value, dict):
            return {}
        return {str(key): str(item) for key, item in value.items() if item is not None}

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        offline: bool = False,
    ) -> FetchResult:
        body_path, metadata_path = self._paths(url)
        metadata = self._metadata(metadata_path)
        if offline:
            try:
                body = body_path.read_bytes()
            except OSError as exc:
                raise HarvestHTTPError(f"no cached response for {url}") from exc
            return FetchResult(
                url=url,
                body=body,
                status=200,
                from_cache=True,
                not_modified=False,
                etag=metadata.get("etag"),
                last_modified=metadata.get("last_modified"),
            )

        request_headers = {"User-Agent": self.user_agent}
        if metadata.get("etag"):
            request_headers["If-None-Match"] = metadata["etag"]
        if metadata.get("last_modified"):
            request_headers["If-Modified-Since"] = metadata["last_modified"]
        if headers:
            request_headers.update(headers)
        try:
            with urlopen(Request(url, headers=request_headers), timeout=self.timeout) as response:
                declared_length = response.headers.get("Content-Length")
                if declared_length and int(declared_length) > self.max_bytes:
                    raise HarvestHTTPError(f"response for {url} exceeds cache limit")
                body = response.read(self.max_bytes + 1)
                if len(body) > self.max_bytes:
                    raise HarvestHTTPError(f"response for {url} exceeds cache limit")
                etag = response.headers.get("ETag")
                last_modified = response.headers.get("Last-Modified")
                status = getattr(response, "status", 200)
        except HTTPError as exc:
            if exc.code != 304:
                raise HarvestHTTPError(f"HTTP {exc.code} fetching {url}") from exc
            try:
                body = body_path.read_bytes()
            except OSError as cache_exc:
                raise HarvestHTTPError(
                    f"server returned 304 but cached body for {url} is missing"
                ) from cache_exc
            return FetchResult(
                url=url,
                body=body,
                status=304,
                from_cache=True,
                not_modified=True,
                etag=metadata.get("etag"),
                last_modified=metadata.get("last_modified"),
            )
        except (URLError, OSError, TimeoutError) as exc:
            raise HarvestHTTPError(f"cannot fetch {url}: {exc}") from exc

        _atomic_bytes(body_path, body)
        _atomic_bytes(
            metadata_path,
            (
                json.dumps(
                    {
                        "url": url,
                        "etag": etag,
                        "last_modified": last_modified,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8"),
        )
        return FetchResult(
            url=url,
            body=body,
            status=status,
            from_cache=False,
            not_modified=False,
            etag=etag,
            last_modified=last_modified,
        )


__all__ = ["CachedHTTPClient", "FetchResult", "HarvestHTTPError"]
