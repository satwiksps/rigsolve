"""Provenance and verification levels for compatibility facts.

The matrix deliberately treats provenance as part of a fact's identity rather
than optional documentation.  Constructing a :class:`Source` without both a
harvest date and a stable upstream locator is therefore an error.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import IntEnum
from typing import Any, cast
from urllib.parse import urlparse


class ProvenanceError(ValueError):
    """Raised when a matrix source cannot be audited."""


class VerificationTier(IntEnum):
    """How much has actually been demonstrated about a fact.

    Tier zero is intentionally named ``DERIVED`` rather than ``VERIFIED``: an
    asset name proves only that the asset exists and parses, not that it works.
    """

    DERIVED = 0
    INSTALLS = 1
    IMPORTS = 2
    RUNS = 3

    @property
    def label(self) -> str:
        return {
            self.DERIVED: "derived",
            self.INSTALLS: "installs",
            self.IMPORTS: "imports",
            self.RUNS: "runs",
        }[self]

    @property
    def verified(self) -> bool:
        """Whether evidence goes beyond merely observing an artifact."""

        return self is not self.DERIVED

    @classmethod
    def coerce(cls, value: int | str | VerificationTier) -> VerificationTier:
        if isinstance(value, cls):
            return value
        if isinstance(value, bool):
            raise ProvenanceError("verification tier must be an integer from 0 to 3")
        if isinstance(value, str) and not value.isdigit():
            by_name = {
                "derived": cls.DERIVED,
                "installs": cls.INSTALLS,
                "imports": cls.IMPORTS,
                "runs": cls.RUNS,
            }
            try:
                return by_name[value.strip().lower()]
            except KeyError as exc:
                raise ProvenanceError(f"unknown verification tier: {value!r}") from exc
        try:
            return cls(int(value))
        except (TypeError, ValueError) as exc:
            raise ProvenanceError("verification tier must be an integer from 0 to 3") from exc


_KIND_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_REPO_RE = re.compile(r"^[^/\s]+/[^/\s]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _parse_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ProvenanceError("source.harvested must be an ISO date (YYYY-MM-DD)")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ProvenanceError("source.harvested must be an ISO date (YYYY-MM-DD)") from exc
    if parsed.isoformat() != value:
        raise ProvenanceError("source.harvested must use canonical YYYY-MM-DD form")
    return parsed


@dataclass(frozen=True, slots=True)
class Source:
    """An auditable upstream source for one matrix fact."""

    kind: str
    harvested: date | str
    url: str | None = None
    repo: str | None = None
    tag: str | None = None
    path: str | None = None
    confirmed_by: int | None = None
    etag: str | None = None
    sha256: str | None = None
    references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        kind = self.kind.strip() if isinstance(self.kind, str) else ""
        if not _KIND_RE.fullmatch(kind):
            raise ProvenanceError("source.kind must be a lowercase slug such as 'gh-release'")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "harvested", _parse_date(self.harvested))

        if not self.url and not self.repo:
            raise ProvenanceError("source requires at least one of url or repo")
        if self.url:
            parsed = urlparse(self.url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ProvenanceError("source.url must be an absolute HTTP(S) URL")
        if self.repo and not _REPO_RE.fullmatch(self.repo):
            raise ProvenanceError("source.repo must have owner/name form")
        if self.tag is not None and not self.tag.strip():
            raise ProvenanceError("source.tag cannot be empty")
        if self.path is not None and not self.path.strip():
            raise ProvenanceError("source.path cannot be empty")
        if self.confirmed_by is not None and (
            isinstance(self.confirmed_by, bool) or self.confirmed_by < 1
        ):
            raise ProvenanceError("source.confirmed_by must be a positive integer")
        if self.sha256 is not None:
            digest = self.sha256.lower()
            if digest.startswith("sha256:"):
                digest = digest[7:]
            if not _SHA256_RE.fullmatch(digest):
                raise ProvenanceError("source.sha256 must contain 64 hexadecimal characters")
            object.__setattr__(self, "sha256", digest)
        references = tuple(self.references)
        for reference in references:
            parsed = urlparse(reference)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ProvenanceError("source.references entries must be absolute HTTP(S) URLs")
        object.__setattr__(self, "references", tuple(dict.fromkeys(references)))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> Source:
        if not isinstance(value, Mapping):
            raise ProvenanceError("fact.source must be a TOML table")
        allowed = {
            "kind",
            "harvested",
            "url",
            "repo",
            "tag",
            "path",
            "confirmed_by",
            "etag",
            "sha256",
            "references",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ProvenanceError(
                "unknown source field(s): " + ", ".join(sorted(map(str, unknown)))
            )
        missing = {"kind", "harvested"} - set(value)
        if missing:
            raise ProvenanceError("source missing required field(s): " + ", ".join(sorted(missing)))
        return cls(**dict(value))

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "kind": self.kind,
            "harvested": self.harvested_date.isoformat(),
        }
        for name in (
            "url",
            "repo",
            "tag",
            "path",
            "confirmed_by",
            "etag",
            "sha256",
        ):
            value = getattr(self, name)
            if value is not None:
                result[name] = value
        if self.references:
            result["references"] = list(self.references)
        return result

    def citation(self) -> str:
        """Return a compact, deterministic citation suitable for explanations."""

        locator = self.repo or self.url or "unknown"
        detail = self.tag or self.path
        if detail:
            locator = f"{locator} {detail}"
        evidence = f", +{len(self.references)} evidence link(s)" if self.references else ""
        return f"{self.kind} {locator}, harvested {self.harvested_date.isoformat()}{evidence}"

    @property
    def harvested_date(self) -> date:
        """The validated date, narrowed for static type checkers."""

        return cast(date, self.harvested)


# A short compatibility alias used by downstream code and older matrix drafts.
Tier = VerificationTier


__all__ = [
    "ProvenanceError",
    "Source",
    "Tier",
    "VerificationTier",
]
