"""Harvest wheel tags and hashes from the official PyPI JSON API."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote

from packaging.utils import canonicalize_name

from rigsolve.matrix.provenance import Source, VerificationTier
from rigsolve.matrix.schema import WheelFact

from .cache import CachedHTTPClient, HarvestHTTPError
from .normalise import WheelFilenameError, normalise_wheel_filename

PYPI_API = "https://pypi.org/pypi"


class PyPIHarvestError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PyPIHarvest:
    package: str
    version: str
    project_url: str
    wheels: tuple[WheelFact, ...]
    sdist_urls: tuple[str, ...]

    @property
    def wheel_count(self) -> int:
        return len(self.wheels)

    @property
    def source_only(self) -> bool:
        return not self.wheels and bool(self.sdist_urls)


def _object(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PyPIHarvestError(f"PyPI JSON {where} must be an object")
    return value


def parse_pypi_payload(
    payload: Mapping[str, Any] | str | bytes,
    *,
    harvested: date | str,
    api_url: str | None = None,
    etag: str | None = None,
) -> PyPIHarvest:
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise PyPIHarvestError(f"invalid PyPI JSON: {exc}") from exc
    root = _object(payload, "root")
    info = _object(root.get("info"), "info")
    name = info.get("name")
    version = info.get("version")
    if not isinstance(name, str) or not name:
        raise PyPIHarvestError("PyPI JSON info.name is missing")
    if not isinstance(version, str) or not version:
        raise PyPIHarvestError("PyPI JSON info.version is missing")
    package = canonicalize_name(name)
    json_url = api_url or f"{PYPI_API}/{quote(package)}/{quote(version)}/json"
    project_url = f"https://pypi.org/project/{quote(package)}/{quote(version)}/"
    source = Source(
        kind="pypi-json",
        url=json_url,
        harvested=harvested,
        etag=etag,
    )
    urls = root.get("urls")
    if not isinstance(urls, list):
        raise PyPIHarvestError("PyPI JSON urls must be an array")
    wheels: list[WheelFact] = []
    sdists: list[str] = []
    for index, raw_file in enumerate(urls):
        file = _object(raw_file, f"urls[{index}]")
        filename = file.get("filename")
        url = file.get("url")
        package_type = file.get("packagetype")
        if not isinstance(filename, str) or not isinstance(url, str):
            raise PyPIHarvestError(f"PyPI urls[{index}] lacks filename or url")
        if package_type == "sdist":
            sdists.append(url)
            continue
        if package_type != "bdist_wheel" and not filename.lower().endswith(".whl"):
            continue
        try:
            normalized = normalise_wheel_filename(
                filename,
                expected_distribution=package,
                expected_version=version,
            )
        except WheelFilenameError as exc:
            raise PyPIHarvestError(str(exc)) from exc
        digests = file.get("digests")
        sha256 = digests.get("sha256") if isinstance(digests, Mapping) else None
        size = file.get("size")
        if not isinstance(size, int) or isinstance(size, bool):
            size = None
        yanked = bool(file.get("yanked", False))
        reason = file.get("yanked_reason")
        if not isinstance(reason, str) or not reason:
            reason = None
        wheels.append(
            normalized.to_fact(
                url=url,
                source=source,
                tier=VerificationTier.DERIVED,
                size=size,
                sha256=sha256 if isinstance(sha256, str) else None,
                yanked=yanked,
                yanked_reason=reason,
            )
        )
    return PyPIHarvest(
        package=package,
        version=version,
        project_url=project_url,
        wheels=tuple(sorted(wheels, key=lambda fact: fact.filename or fact.url)),
        sdist_urls=tuple(sorted(sdists)),
    )


class PyPIHarvester:
    def __init__(
        self,
        cache_dir: str | os.PathLike[str],
        *,
        client: CachedHTTPClient | None = None,
    ) -> None:
        self.client = client or CachedHTTPClient(Path(cache_dir) / "pypi")

    def package(
        self,
        package: str,
        version: str | None = None,
        *,
        harvested: date | str | None = None,
        offline: bool = False,
    ) -> PyPIHarvest:
        name = canonicalize_name(package)
        suffix = f"/{quote(version)}" if version else ""
        url = f"{PYPI_API}/{quote(name)}{suffix}/json"
        try:
            response = self.client.get(
                url,
                headers={"Accept": "application/json"},
                offline=offline,
            )
        except HarvestHTTPError as exc:
            raise PyPIHarvestError(str(exc)) from exc
        return parse_pypi_payload(
            response.body,
            harvested=harvested or date.today(),
            api_url=url,
            etag=response.etag,
        )


def harvest_pypi(
    package: str,
    version: str | None = None,
    *,
    cache_dir: str | os.PathLike[str],
) -> tuple[WheelFact, ...]:
    return PyPIHarvester(cache_dir).package(package, version).wheels


__all__ = [
    "PYPI_API",
    "PyPIHarvest",
    "PyPIHarvestError",
    "PyPIHarvester",
    "harvest_pypi",
    "parse_pypi_payload",
]
