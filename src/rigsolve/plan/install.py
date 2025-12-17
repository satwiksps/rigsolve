"""Immutable, serialisable installation plans."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from typing import Any
from urllib.parse import urlparse, urlunparse

from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import InvalidVersion, Version


@dataclass(frozen=True, slots=True)
class InstallStep:
    package: str
    version: str
    artifact_url: str | None = None
    artifact_sha256: str | None = None
    index_url: str | None = None
    dependencies: tuple[str, ...] = ()
    build_requirements: tuple[str, ...] = ()
    environment: tuple[tuple[str, str], ...] = ()
    flags: tuple[str, ...] = ()
    source_build: bool = False
    build_estimate: str | None = None
    ram_gb_per_job: float | None = None
    tier: int = 0
    provenance: tuple[str, ...] = ()
    cuda_line: str | None = None
    torch_version: str | None = None
    cxx11_abi: bool | None = None
    python_tag: str | None = None
    platform_tag: str | None = None

    def __post_init__(self) -> None:
        if not self.package or not self.version:
            raise ValueError("install steps require a package and version")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", self.package):
            raise ValueError(f"invalid package name: {self.package!r}")
        try:
            Version(self.version)
        except InvalidVersion as error:
            raise ValueError(f"invalid package version: {self.version!r}") from error
        if not 0 <= self.tier <= 3:
            raise ValueError("verification tier must be between 0 and 3")
        if self.artifact_url and self.source_build:
            raise ValueError("a source-build step cannot also name a wheel URL")
        if self.ram_gb_per_job is not None:
            if (
                isinstance(self.ram_gb_per_job, bool)
                or not isinstance(self.ram_gb_per_job, (int, float))
                or not isfinite(self.ram_gb_per_job)
                or self.ram_gb_per_job <= 0
            ):
                raise ValueError("RAM per build job must be a positive finite number")
            if not self.source_build:
                raise ValueError("RAM per build job is only valid for source-build steps")
            object.__setattr__(self, "ram_gb_per_job", float(self.ram_gb_per_job))
        if self.artifact_sha256 is not None:
            if self.artifact_url is None:
                raise ValueError("an artifact hash requires an artifact URL")
            if not re.fullmatch(r"[0-9a-fA-F]{64}", self.artifact_sha256):
                raise ValueError("artifact SHA-256 must contain 64 hex characters")
        for label, url in (("artifact", self.artifact_url), ("index", self.index_url)):
            if url is not None:
                parsed = urlparse(url)
                if parsed.scheme != "https" or not parsed.netloc:
                    raise ValueError(f"{label} URL must be absolute HTTPS")
        for name, value in self.environment:
            if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", name):
                raise ValueError(f"unsafe environment variable name: {name!r}")
            if any(character in value for character in "\x00\r\n"):
                raise ValueError(f"environment variable {name} contains a control character")
        if any(
            not flag.startswith("-") or any(character in flag for character in "\x00\r\n")
            for flag in self.flags
        ):
            raise ValueError("install flags must be option strings")
        for requirement in self.build_requirements:
            try:
                Requirement(requirement)
            except InvalidRequirement as error:
                raise ValueError(f"invalid build requirement: {requirement!r}") from error

    @property
    def requirement(self) -> str:
        if self.artifact_url:
            if not self.artifact_sha256:
                return self.artifact_url
            parsed = urlparse(self.artifact_url)
            hash_fragment = f"sha256={self.artifact_sha256.lower()}"
            fragment = f"{parsed.fragment}&{hash_fragment}" if parsed.fragment else hash_fragment
            return urlunparse(parsed._replace(fragment=fragment))
        return f"{self.package}=={self.version}"


@dataclass(frozen=True, slots=True)
class InstallPlan:
    requested: tuple[str, ...]
    steps: tuple[InstallStep, ...]
    matrix_version: str
    matrix_digest: str
    target: Mapping[str, Any] = field(default_factory=dict)
    preference: str = "verified"
    constraint_tiers: tuple[int, ...] = ()
    warnings: tuple[str, ...] = ()
    weakest_tier: int = field(init=False)

    def __post_init__(self) -> None:
        packages = [step.package for step in self.steps]
        if len(packages) != len(set(packages)):
            raise ValueError("an install plan may contain only one step per package")
        available = set(packages)
        for step in self.steps:
            missing = set(step.dependencies).difference(available)
            if missing:
                raise ValueError(f"{step.package} depends on absent plan steps: {sorted(missing)}")
        if any(
            not isinstance(tier, int) or isinstance(tier, bool) or not 0 <= tier <= 3
            for tier in self.constraint_tiers
        ):
            raise ValueError("constraint tiers must be integers from 0 to 3")
        object.__setattr__(
            self,
            "weakest_tier",
            min(
                (*self.constraint_tiers, *(step.tier for step in self.steps)),
                default=0,
            ),
        )

    def ordered_steps(self) -> tuple[InstallStep, ...]:
        """Return a stable topological ordering and reject dependency cycles."""

        by_name = {step.package: step for step in self.steps}
        remaining = set(by_name)
        emitted: list[InstallStep] = []
        complete: set[str] = set()
        while remaining:
            ready = sorted(
                name for name in remaining if set(by_name[name].dependencies).issubset(complete)
            )
            if not ready:
                cycle = ", ".join(sorted(remaining))
                raise ValueError(f"install dependency cycle: {cycle}")
            for name in ready:
                emitted.append(by_name[name])
                complete.add(name)
                remaining.remove(name)
        return tuple(emitted)
