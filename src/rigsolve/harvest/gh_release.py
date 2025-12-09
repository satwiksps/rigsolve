"""Harvest tier-0 wheel-existence facts from GitHub release assets."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote

from rigsolve.matrix.provenance import Source, VerificationTier
from rigsolve.matrix.schema import MatrixValidationError, WheelFact

from .cache import CachedHTTPClient, HarvestHTTPError
from .normalise import WheelFilenameError, normalise_wheel_filename

GITHUB_API = "https://api.github.com"


class GitHubHarvestError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class GitHubReleaseHarvest:
    repo: str
    tag: str
    release_url: str
    wheels: tuple[WheelFact, ...]
    skipped_assets: tuple[str, ...] = ()


def _mapping(value: Any, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise GitHubHarvestError(f"GitHub response {where} must be an object")
    return value


def parse_release_payload(
    payload: Mapping[str, Any] | str | bytes,
    *,
    repo: str,
    harvested: date | str,
    etag: str | None = None,
    expected_package: str | None = None,
    strict_wheels: bool = True,
) -> GitHubReleaseHarvest:
    """Turn one GitHub release API response into provenance-bearing facts."""

    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise GitHubHarvestError(f"invalid GitHub JSON: {exc}") from exc
    release = _mapping(payload, "root")
    tag = release.get("tag_name")
    release_url = release.get("html_url")
    if not isinstance(tag, str) or not tag:
        raise GitHubHarvestError("GitHub release is missing tag_name")
    if not isinstance(release_url, str) or not release_url.startswith("https://"):
        raise GitHubHarvestError("GitHub release is missing an HTTPS html_url")
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise GitHubHarvestError("GitHub release assets must be an array")

    source = Source(
        kind="gh-release",
        repo=repo,
        tag=tag,
        url=release_url,
        harvested=harvested,
        etag=etag,
    )
    wheels: list[WheelFact] = []
    skipped: list[str] = []
    for index, raw_asset in enumerate(assets):
        asset = _mapping(raw_asset, f"assets[{index}]")
        name = asset.get("name")
        url = asset.get("browser_download_url")
        if not isinstance(name, str) or not name.lower().endswith(".whl"):
            if isinstance(name, str):
                skipped.append(name)
            continue
        if not isinstance(url, str) or not url.startswith("https://"):
            raise GitHubHarvestError(f"wheel asset {name!r} has no HTTPS download URL")
        try:
            normalized = normalise_wheel_filename(name, expected_distribution=expected_package)
        except WheelFilenameError as exc:
            if strict_wheels:
                raise GitHubHarvestError(str(exc)) from exc
            skipped.append(name)
            continue
        digest = asset.get("digest")
        sha256: str | None = None
        if isinstance(digest, str) and digest.lower().startswith("sha256:"):
            sha256 = digest.split(":", 1)[1]
        size = asset.get("size")
        if not isinstance(size, int) or isinstance(size, bool):
            size = None
        try:
            wheels.append(
                normalized.to_fact(
                    url=url,
                    source=source,
                    tier=VerificationTier.DERIVED,
                    size=size,
                    sha256=sha256,
                )
            )
        except MatrixValidationError as exc:
            raise GitHubHarvestError(f"invalid fact for asset {name!r}: {exc}") from exc
    return GitHubReleaseHarvest(
        repo=repo,
        tag=tag,
        release_url=release_url,
        wheels=tuple(sorted(wheels, key=lambda fact: fact.filename or fact.url)),
        skipped_assets=tuple(sorted(skipped)),
    )


class GitHubReleaseHarvester:
    def __init__(
        self,
        cache_dir: str | os.PathLike[str],
        *,
        token: str | None = None,
        client: CachedHTTPClient | None = None,
    ) -> None:
        self.client = client or CachedHTTPClient(Path(cache_dir) / "github")
        self.token = token or os.environ.get("GITHUB_TOKEN")

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def release(
        self,
        repo: str,
        tag: str,
        *,
        harvested: date | str | None = None,
        expected_package: str | None = None,
        offline: bool = False,
    ) -> GitHubReleaseHarvest:
        encoded_tag = quote(tag, safe="")
        url = f"{GITHUB_API}/repos/{repo}/releases/tags/{encoded_tag}"
        try:
            response = self.client.get(url, headers=self._headers(), offline=offline)
        except HarvestHTTPError as exc:
            raise GitHubHarvestError(str(exc)) from exc
        return parse_release_payload(
            response.body,
            repo=repo,
            harvested=harvested or date.today(),
            etag=response.etag,
            expected_package=expected_package,
        )

    def latest(
        self,
        repo: str,
        *,
        harvested: date | str | None = None,
        expected_package: str | None = None,
        offline: bool = False,
    ) -> GitHubReleaseHarvest:
        url = f"{GITHUB_API}/repos/{repo}/releases/latest"
        try:
            response = self.client.get(url, headers=self._headers(), offline=offline)
        except HarvestHTTPError as exc:
            raise GitHubHarvestError(str(exc)) from exc
        return parse_release_payload(
            response.body,
            repo=repo,
            harvested=harvested or date.today(),
            etag=response.etag,
            expected_package=expected_package,
        )


def harvest_release(
    repo: str,
    tag: str,
    *,
    cache_dir: str | os.PathLike[str],
    expected_package: str | None = None,
    token: str | None = None,
) -> tuple[WheelFact, ...]:
    return (
        GitHubReleaseHarvester(cache_dir, token=token)
        .release(repo, tag, expected_package=expected_package)
        .wheels
    )


__all__ = [
    "GITHUB_API",
    "GitHubHarvestError",
    "GitHubReleaseHarvest",
    "GitHubReleaseHarvester",
    "harvest_release",
    "parse_release_payload",
]
