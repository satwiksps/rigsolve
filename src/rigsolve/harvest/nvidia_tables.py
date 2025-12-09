"""Parse NVIDIA's driver/CUDA compatibility tables without hard-coded claims."""

from __future__ import annotations

import os
import re
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

from rigsolve.matrix.provenance import Source, VerificationTier
from rigsolve.matrix.schema import DriverConstraintFact

from .cache import CachedHTTPClient, HarvestHTTPError

MINOR_COMPATIBILITY_URL = (
    "https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html"
)


class NvidiaHarvestError(RuntimeError):
    pass


class _TableText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_cell = False
        self._cell: list[str] = []
        self._row: list[str] = []
        self.rows: list[tuple[str, ...]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "tr":
            self._row = []
        elif tag.lower() in {"td", "th"}:
            self._in_cell = True
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"td", "th"} and self._in_cell:
            value = " ".join("".join(self._cell).split())
            self._row.append(value)
            self._in_cell = False
        elif tag.lower() == "tr" and self._row:
            self.rows.append(tuple(self._row))
            self._row = []


_CUDA_CELL = re.compile(r"CUDA\s+(?P<cuda>\d+(?:\.\d+)?)(?P<x>\.x)?", re.IGNORECASE)
_MINIMUM = re.compile(r">=?\s*(?P<version>\d+(?:\.\d+){0,2})")


def extract_table_rows(document: str) -> tuple[tuple[str, ...], ...]:
    if "<table" not in document.lower():
        rows: list[tuple[str, ...]] = []
        for line in document.splitlines():
            cells = tuple(cell.strip() for cell in re.split(r"\s*\|\s*|\t+", line) if cell.strip())
            if cells:
                rows.append(cells)
        return tuple(rows)
    parser = _TableText()
    parser.feed(document)
    return tuple(parser.rows)


def parse_driver_table(
    document: str,
    *,
    source: Source,
    compatibility: str = "minor-compatible",
    platforms: tuple[str, ...] = ("linux", "windows"),
) -> tuple[DriverConstraintFact, ...]:
    """Extract rows like ``CUDA 12.x | >= 525 | < 580``.

    The current minor-compatibility table uses driver branch floors shared by
    platform.  Archived release-note tables can pass platform column names via
    ``platforms`` (typically Linux, Windows) to retain exact patch floors.
    """

    facts: list[DriverConstraintFact] = []
    for row in extract_table_rows(document):
        cuda_index = next(
            (index for index, cell in enumerate(row) if _CUDA_CELL.search(cell)), None
        )
        if cuda_index is None:
            continue
        cuda_match = _CUDA_CELL.search(row[cuda_index])
        assert cuda_match is not None
        label = cuda_match.group("cuda") + (".x" if cuda_match.group("x") else "")
        versions: list[str] = []
        for cell in row[cuda_index + 1 :]:
            match = _MINIMUM.search(cell)
            if match:
                versions.append(match.group("version"))
        if not versions:
            continue
        if len(versions) == 1:
            minimum = {platform: versions[0] for platform in platforms}
        else:
            minimum = {
                platform: version for platform, version in zip(platforms, versions, strict=False)
            }
        facts.append(
            DriverConstraintFact(
                kind="driver-min",
                compatibility=compatibility,
                cuda_runtime=label,
                min_driver=minimum,
                note=(
                    "Parsed from NVIDIA's table. Minor compatibility has feature "
                    "caveats, including PTX JIT requirements; this is a floor, not "
                    "a guarantee for every application."
                    if compatibility == "minor-compatible"
                    else "Corresponding toolkit driver floor from NVIDIA release notes."
                ),
                tier=VerificationTier.DERIVED,
                source=source,
            )
        )
    if not facts:
        raise NvidiaHarvestError("no CUDA driver rows found in NVIDIA table")
    unique = {fact.key: fact for fact in facts}
    return tuple(sorted(unique.values(), key=lambda fact: fact.cuda_runtime))


class NvidiaTableHarvester:
    def __init__(
        self,
        cache_dir: str | os.PathLike[str],
        *,
        client: CachedHTTPClient | None = None,
    ) -> None:
        self.client = client or CachedHTTPClient(Path(cache_dir) / "nvidia")

    def driver_table(
        self,
        url: str = MINOR_COMPATIBILITY_URL,
        *,
        harvested: date | str | None = None,
        compatibility: str = "minor-compatible",
        platforms: tuple[str, ...] = ("linux", "windows"),
        offline: bool = False,
    ) -> tuple[DriverConstraintFact, ...]:
        try:
            response = self.client.get(url, offline=offline)
        except HarvestHTTPError as exc:
            raise NvidiaHarvestError(str(exc)) from exc
        source = Source(
            kind="nvidia-docs",
            url=url,
            harvested=harvested or date.today(),
            etag=response.etag,
        )
        return parse_driver_table(
            response.text(),
            source=source,
            compatibility=compatibility,
            platforms=platforms,
        )


__all__ = [
    "MINOR_COMPATIBILITY_URL",
    "NvidiaHarvestError",
    "NvidiaTableHarvester",
    "extract_table_rows",
    "parse_driver_table",
]
