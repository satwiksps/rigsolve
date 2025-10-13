"""Frozen, provenance-enforced schema for rigsolve's compatibility matrix."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType
from typing import Any, TypeAlias, cast
from urllib.parse import urlparse

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from rigsolve.errors import MatrixValidationError

from .provenance import ProvenanceError, Source, VerificationTier

SCHEMA_VERSION = 1


def _schema_error(message: str) -> MatrixValidationError:
    return MatrixValidationError(message)


def _check_keys(
    value: Mapping[str, Any], *, allowed: Iterable[str], required: Iterable[str], where: str
) -> None:
    if not isinstance(value, Mapping):
        raise MatrixValidationError(f"{where} must be a TOML table")
    allowed_set = set(allowed)
    unknown = set(value) - allowed_set
    if unknown:
        raise MatrixValidationError(
            f"unknown {where} field(s): " + ", ".join(sorted(map(str, unknown)))
        )
    missing = set(required) - set(value)
    if missing:
        raise MatrixValidationError(
            f"{where} missing required field(s): " + ", ".join(sorted(missing))
        )


def _source(value: Any, where: str) -> Source:
    if isinstance(value, Source):
        return value
    try:
        return Source.from_mapping(value)
    except ProvenanceError as exc:
        raise _schema_error(f"invalid {where}.source: {exc}") from exc


def _tier(value: Any, where: str) -> VerificationTier:
    try:
        return VerificationTier.coerce(value)
    except ProvenanceError as exc:
        raise _schema_error(f"invalid {where}.tier: {exc}") from exc


def _package(value: Any, where: str = "package") -> str:
    if not isinstance(value, str) or not value.strip():
        raise MatrixValidationError(f"{where} must be a non-empty package name")
    return canonicalize_name(value.strip())


def _version(value: Any, where: str = "version") -> str:
    if not isinstance(value, str) or not value.strip():
        raise MatrixValidationError(f"{where} must be a non-empty PEP 440 version")
    try:
        return str(Version(value.strip()))
    except InvalidVersion as exc:
        raise _schema_error(f"{where} is not a valid PEP 440 version: {value!r}") from exc


_CUDA_RE = re.compile(r"^\d+(?:\.\d+){0,2}(?:\.x)?$")
_PYTHON_TAG_RE = re.compile(r"^(?:cp|pp|py)\d+[a-z]?(?:\.(?:cp|pp|py)\d+[a-z]?)*$")
_PLATFORM_RE = re.compile(r"^[A-Za-z0-9_.]+$")
_ARCH_RE = re.compile(r"^(?:sm|compute)_\d+[a-z]?$", re.IGNORECASE)
_DRIVER_RE = re.compile(r"^\d+(?:\.\d+){0,2}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_VERIFICATION_SOURCE_TIERS = {
    "install-test": VerificationTier.INSTALLS,
    "import-test": VerificationTier.IMPORTS,
    "gpu-run": VerificationTier.RUNS,
}
_NATIVE_GPU_PACKAGES = frozenset(
    {
        "bitsandbytes",
        "flash-attn",
        "flashinfer-python",
        "torchaudio",
        "torch",
        "torchvision",
        "triton",
        "vllm",
        "xformers",
    }
)
_TORCH_EXTENSION_PACKAGES = frozenset(
    {
        "flash-attn",
        "flashinfer-python",
        "torchaudio",
        "torchvision",
        "vllm",
        "xformers",
    }
)


def _cuda(value: Any, where: str, *, allow_x: bool = False) -> str:
    if not isinstance(value, str):
        raise MatrixValidationError(f"{where} must be a CUDA version string")
    result = value.strip().lower()
    if not _CUDA_RE.fullmatch(result) or (result.endswith(".x") and not allow_x):
        suffix = " (for example '12.4')" if not allow_x else ""
        raise MatrixValidationError(f"{where} must be a CUDA version{suffix}")
    return result


def _url(value: Any, where: str) -> str:
    if not isinstance(value, str):
        raise MatrixValidationError(f"{where} must be an absolute HTTPS URL")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise MatrixValidationError(f"{where} must be an absolute HTTPS URL")
    return value


def _require_derived_tier(tier: VerificationTier, where: str) -> None:
    if tier is not VerificationTier.DERIVED:
        raise MatrixValidationError(
            f"{where}.tier must be 0 because {where} facts do not bind executed "
            "verification to an immutable artifact"
        )


def _validate_wheel_verification(
    tier: VerificationTier,
    source: Source,
    sha256: str | None,
    archs: tuple[str, ...],
    *,
    package: str,
    python: str | None,
    abi: str | None,
    platform: str | None,
    cuda_line: str | None,
    torch: str | None,
) -> None:
    if tier is VerificationTier.DERIVED:
        return
    if sha256 is None:
        raise MatrixValidationError("verified wheel facts require wheel.sha256")
    source_tier = _VERIFICATION_SOURCE_TIERS.get(source.kind)
    if source_tier is None or source_tier < tier:
        expected = {
            VerificationTier.INSTALLS: "install-test, import-test, or gpu-run",
            VerificationTier.IMPORTS: "import-test or gpu-run",
            VerificationTier.RUNS: "gpu-run",
        }[tier]
        raise MatrixValidationError(
            f"wheel tier {int(tier)} requires execution provenance with "
            f"source.kind set to {expected}"
        )
    if python is None or abi is None or platform is None:
        raise MatrixValidationError(
            "verified wheel facts require wheel.python, wheel.abi, and wheel.platform"
        )
    if package in _NATIVE_GPU_PACKAGES and cuda_line is None:
        raise MatrixValidationError(f"verified {package} wheel facts require wheel.cuda_line")
    if package in _TORCH_EXTENSION_PACKAGES and torch is None:
        raise MatrixValidationError(f"verified {package} wheel facts require wheel.torch")
    if tier is VerificationTier.RUNS and not archs:
        raise MatrixValidationError(
            "wheel tier 3 requires at least one architecture recorded in wheel.archs"
        )


def _string_tuple(value: Any, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise MatrixValidationError(f"{where} must be an array of strings")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise MatrixValidationError(f"{where} must contain non-empty strings")
    return tuple(item.strip() for item in value)


def _freeze_value(value: Any, where: str) -> Any:
    if isinstance(value, Mapping):
        return tuple(
            (str(key), _freeze_value(item, f"{where}.{key}"))
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item, where) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise MatrixValidationError(f"{where} contains an unsupported value: {value!r}")


def _thaw_value(value: Any) -> Any:
    if isinstance(value, tuple):
        if all(
            isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str)
            for item in value
        ):
            return {key: _thaw_value(item) for key, item in value}
        return [_thaw_value(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class MatrixMetadata:
    schema_version: int
    matrix_version: str
    generated: date | str
    description: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise MatrixValidationError(
                f"unsupported matrix schema {self.schema_version}; expected {SCHEMA_VERSION}"
            )
        if not isinstance(self.matrix_version, str) or not self.matrix_version.strip():
            raise MatrixValidationError("meta.matrix_version must be non-empty")
        object.__setattr__(self, "matrix_version", self.matrix_version.strip())
        generated = self.generated
        if isinstance(generated, str):
            try:
                generated = date.fromisoformat(generated)
            except ValueError as exc:
                raise _schema_error("meta.generated must be an ISO date") from exc
        if not isinstance(generated, date):
            raise MatrixValidationError("meta.generated must be an ISO date")
        object.__setattr__(self, "generated", generated)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> MatrixMetadata:
        _check_keys(
            value,
            allowed={"schema_version", "matrix_version", "generated", "description"},
            required={"schema_version", "matrix_version", "generated"},
            where="meta",
        )
        return cls(**dict(value))

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "matrix_version": self.matrix_version,
            "generated": self.generated_date.isoformat(),
        }
        if self.description:
            result["description"] = self.description
        return result

    @property
    def generated_date(self) -> date:
        """The validated generation date, narrowed for static type checkers."""

        return cast(date, self.generated)


@dataclass(frozen=True, slots=True)
class WheelFact:
    package: str
    version: str
    url: str
    source: Source
    cuda_line: str | None = None
    torch: str | None = None
    cxx11abi: bool | None = None
    python: str | None = None
    abi: str | None = None
    platform: str | None = None
    archs: tuple[str, ...] = ()
    filename: str | None = None
    build_tag: str | None = None
    size: int | None = None
    sha256: str | None = None
    yanked: bool = False
    yanked_reason: str | None = None
    tier: VerificationTier = VerificationTier.DERIVED

    def __post_init__(self) -> None:
        object.__setattr__(self, "package", _package(self.package, "wheel.package"))
        object.__setattr__(self, "version", _version(self.version, "wheel.version"))
        object.__setattr__(self, "url", _url(self.url, "wheel.url"))
        object.__setattr__(self, "source", _source(self.source, "wheel"))
        object.__setattr__(self, "tier", _tier(self.tier, "wheel"))
        if self.cuda_line is not None:
            object.__setattr__(self, "cuda_line", _cuda(self.cuda_line, "wheel.cuda_line"))
        if self.torch is not None:
            object.__setattr__(self, "torch", _version(self.torch, "wheel.torch"))
        if self.cxx11abi is not None and not isinstance(self.cxx11abi, bool):
            raise MatrixValidationError("wheel.cxx11abi must be true or false")
        if self.python is not None and not _PYTHON_TAG_RE.fullmatch(self.python):
            raise MatrixValidationError("wheel.python must be a PEP 425 interpreter tag")
        if self.abi is not None and not _PLATFORM_RE.fullmatch(self.abi):
            raise MatrixValidationError("wheel.abi must be a PEP 425 ABI tag")
        if self.platform is not None and not _PLATFORM_RE.fullmatch(self.platform):
            raise MatrixValidationError("wheel.platform must be a PEP 425 platform tag")
        archs = _string_tuple(self.archs, "wheel.archs")
        if any(not _ARCH_RE.fullmatch(arch) for arch in archs):
            raise MatrixValidationError("wheel.archs entries must look like sm_89")
        object.__setattr__(self, "archs", tuple(dict.fromkeys(a.lower() for a in archs)))
        if self.filename is not None and (
            not self.filename.endswith(".whl") or "/" in self.filename or "\\" in self.filename
        ):
            raise MatrixValidationError("wheel.filename must be a wheel basename")
        if self.size is not None and (
            isinstance(self.size, bool) or not isinstance(self.size, int) or self.size < 0
        ):
            raise MatrixValidationError("wheel.size must be a non-negative integer")
        if self.sha256 is not None:
            digest = self.sha256.lower().removeprefix("sha256:")
            if not _SHA256_RE.fullmatch(digest):
                raise MatrixValidationError("wheel.sha256 must contain 64 hex characters")
            object.__setattr__(self, "sha256", digest)
        if not isinstance(self.yanked, bool):
            raise MatrixValidationError("wheel.yanked must be true or false")
        if self.yanked_reason is not None and not isinstance(self.yanked_reason, str):
            raise MatrixValidationError("wheel.yanked_reason must be a string")
        if self.yanked_reason and not self.yanked:
            raise MatrixValidationError("wheel.yanked_reason requires wheel.yanked = true")
        _validate_wheel_verification(
            self.tier,
            self.source,
            self.sha256,
            self.archs,
            package=self.package,
            python=self.python,
            abi=self.abi,
            platform=self.platform,
            cuda_line=self.cuda_line,
            torch=self.torch,
        )

    @property
    def key(self) -> tuple[Any, ...]:
        return (
            self.package,
            self.version,
            self.cuda_line,
            self.torch,
            self.cxx11abi,
            self.python,
            self.abi,
            self.platform,
            self.filename or self.url,
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> WheelFact:
        allowed = {
            "package",
            "version",
            "url",
            "source",
            "cuda_line",
            "torch",
            "cxx11abi",
            "python",
            "abi",
            "platform",
            "source_build",
            "archs",
            "filename",
            "build_tag",
            "size",
            "sha256",
            "tier",
            "yanked",
            "yanked_reason",
        }
        _check_keys(
            value,
            allowed=allowed,
            required={"package", "version", "url", "source", "tier"},
            where="wheel",
        )
        data = dict(value)
        data["source"] = _source(data["source"], "wheel")
        return cls(**data)

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {"package": self.package, "version": self.version}
        for name in (
            "cuda_line",
            "torch",
            "cxx11abi",
            "python",
            "abi",
            "platform",
        ):
            value = getattr(self, name)
            if value is not None:
                result[name] = value
        if self.archs:
            result["archs"] = list(self.archs)
        result["url"] = self.url
        for name in ("filename", "build_tag", "size", "sha256"):
            value = getattr(self, name)
            if value is not None:
                result[name] = value
        if self.yanked:
            result["yanked"] = True
            if self.yanked_reason:
                result["yanked_reason"] = self.yanked_reason
        result["tier"] = int(self.tier)
        result["source"] = self.source.to_mapping()
        return result


@dataclass(frozen=True, slots=True)
class TorchBuildFact:
    version: str
    cuda_line: str
    index_url: str
    source: Source
    package: str = "torch"
    cuda_exact: str | None = None
    cxx11abi: bool | None = None
    pythons: tuple[str, ...] = ()
    platforms: tuple[str, ...] = ()
    support: str = "build-axis"
    tier: VerificationTier = VerificationTier.DERIVED

    def __post_init__(self) -> None:
        object.__setattr__(self, "package", _package(self.package, "torch_build.package"))
        object.__setattr__(self, "version", _version(self.version, "torch_build.version"))
        object.__setattr__(self, "cuda_line", _cuda(self.cuda_line, "torch_build.cuda_line"))
        object.__setattr__(self, "index_url", _url(self.index_url, "torch_build.index_url"))
        object.__setattr__(self, "source", _source(self.source, "torch_build"))
        object.__setattr__(self, "tier", _tier(self.tier, "torch_build"))
        _require_derived_tier(self.tier, "torch_build")
        if self.cuda_exact is not None:
            exact = _cuda(self.cuda_exact, "torch_build.cuda_exact")
            if exact.split(".")[:2] != self.cuda_line.split(".")[:2]:
                raise MatrixValidationError(
                    "torch_build.cuda_exact must belong to torch_build.cuda_line"
                )
            object.__setattr__(self, "cuda_exact", exact)
        if self.cxx11abi is not None and not isinstance(self.cxx11abi, bool):
            raise MatrixValidationError("torch_build.cxx11abi must be true or false")
        pythons = _string_tuple(self.pythons, "torch_build.pythons")
        for python in pythons:
            if not re.fullmatch(r"\d+\.\d+(?:t)?", python):
                raise MatrixValidationError("torch_build.pythons entries must look like '3.12'")
        object.__setattr__(self, "pythons", tuple(dict.fromkeys(pythons)))
        platforms = _string_tuple(self.platforms, "torch_build.platforms")
        object.__setattr__(self, "platforms", tuple(dict.fromkeys(platforms)))
        if self.support not in {"build-axis", "stable", "experimental"}:
            raise MatrixValidationError(
                "torch_build.support must be build-axis, stable, or experimental"
            )

    @property
    def key(self) -> tuple[str, str, str, str]:
        return self.package, self.version, self.cuda_line, self.index_url

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> TorchBuildFact:
        allowed = {
            "package",
            "version",
            "cuda_line",
            "cuda_exact",
            "index_url",
            "cxx11abi",
            "pythons",
            "platforms",
            "tier",
            "source",
            "support",
        }
        _check_keys(
            value,
            allowed=allowed,
            required={"version", "cuda_line", "index_url", "source", "tier"},
            where="torch_build",
        )
        data = dict(value)
        data["source"] = _source(data["source"], "torch_build")
        return cls(**data)

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "package": self.package,
            "version": self.version,
            "cuda_line": self.cuda_line,
        }
        if self.cuda_exact is not None:
            result["cuda_exact"] = self.cuda_exact
        result["index_url"] = self.index_url
        if self.cxx11abi is not None:
            result["cxx11abi"] = self.cxx11abi
        if self.pythons:
            result["pythons"] = list(self.pythons)
        if self.platforms:
            result["platforms"] = list(self.platforms)
        result["support"] = self.support
        result["tier"] = int(self.tier)
        result["source"] = self.source.to_mapping()
        return result


@dataclass(frozen=True, slots=True)
class TestedAgainstFact:
    package: str
    version: str
    cuda_exact: str
    source: Source
    note: str = ""
    tier: VerificationTier = VerificationTier.DERIVED

    def __post_init__(self) -> None:
        object.__setattr__(self, "package", _package(self.package, "tested_against.package"))
        object.__setattr__(self, "version", _version(self.version, "tested_against.version"))
        object.__setattr__(self, "cuda_exact", _cuda(self.cuda_exact, "tested_against.cuda_exact"))
        object.__setattr__(self, "source", _source(self.source, "tested_against"))
        object.__setattr__(self, "tier", _tier(self.tier, "tested_against"))
        _require_derived_tier(self.tier, "tested_against")
        if not isinstance(self.note, str):
            raise MatrixValidationError("tested_against.note must be a string")

    @property
    def key(self) -> tuple[str, str, str]:
        return self.package, self.version, self.cuda_exact

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> TestedAgainstFact:
        _check_keys(
            value,
            allowed={"package", "version", "cuda_exact", "note", "tier", "source"},
            required={"package", "version", "cuda_exact", "source"},
            where="tested_against",
        )
        data = dict(value)
        data.setdefault("tier", 0)
        data["source"] = _source(data["source"], "tested_against")
        return cls(**data)

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "package": self.package,
            "version": self.version,
            "cuda_exact": self.cuda_exact,
        }
        if self.note:
            result["note"] = self.note
        result["tier"] = int(self.tier)
        result["source"] = self.source.to_mapping()
        return result


@dataclass(frozen=True, slots=True)
class DriverConstraintFact:
    cuda_runtime: str
    min_driver: tuple[tuple[str, str], ...] | Mapping[str, str]
    source: Source
    kind: str = "driver-min"
    compatibility: str = "minor-compatible"
    note: str = ""
    tier: VerificationTier = VerificationTier.DERIVED

    def __post_init__(self) -> None:
        if self.kind != "driver-min":
            raise MatrixValidationError("constraint.kind must be 'driver-min'")
        if self.compatibility not in {"minor-compatible", "toolkit-corresponding"}:
            raise MatrixValidationError(
                "constraint.compatibility must be minor-compatible or toolkit-corresponding"
            )
        object.__setattr__(
            self,
            "cuda_runtime",
            _cuda(self.cuda_runtime, "constraint.cuda_runtime", allow_x=True),
        )
        drivers = self.min_driver
        if isinstance(drivers, Mapping):
            drivers = tuple(sorted((str(k).lower(), str(v)) for k, v in drivers.items()))
        elif isinstance(drivers, (list, tuple)):
            drivers = tuple((str(k).lower(), str(v)) for k, v in drivers)
        else:
            raise MatrixValidationError("constraint.min_driver must be a platform table")
        if not drivers:
            raise MatrixValidationError("constraint.min_driver cannot be empty")
        for platform, version in drivers:
            if platform not in {"linux", "windows"}:
                raise MatrixValidationError(
                    "constraint.min_driver supports only linux and windows keys"
                )
            if not _DRIVER_RE.fullmatch(version):
                raise MatrixValidationError(
                    f"constraint.min_driver.{platform} is not a driver version"
                )
        object.__setattr__(self, "min_driver", tuple(sorted(drivers)))
        object.__setattr__(self, "source", _source(self.source, "constraint"))
        object.__setattr__(self, "tier", _tier(self.tier, "constraint"))
        _require_derived_tier(self.tier, "constraint")
        if not isinstance(self.note, str):
            raise MatrixValidationError("constraint.note must be a string")

    @property
    def key(self) -> tuple[str, str]:
        return self.kind, f"{self.compatibility}:{self.cuda_runtime}"

    @property
    def drivers(self) -> Mapping[str, str]:
        return MappingProxyType(dict(self.min_driver))

    def minimum_for(self, platform: str) -> str | None:
        return dict(self.min_driver).get(platform.lower())

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DriverConstraintFact:
        _check_keys(
            value,
            allowed={
                "kind",
                "compatibility",
                "cuda_runtime",
                "min_driver",
                "note",
                "tier",
                "source",
            },
            required={"kind", "cuda_runtime", "min_driver", "source"},
            where="constraint",
        )
        data = dict(value)
        data.setdefault("tier", 0)
        data["source"] = _source(data["source"], "constraint")
        return cls(**data)

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "kind": self.kind,
            "compatibility": self.compatibility,
            "cuda_runtime": self.cuda_runtime,
            "min_driver": dict(self.min_driver),
        }
        if self.note:
            result["note"] = self.note
        result["tier"] = int(self.tier)
        result["source"] = self.source.to_mapping()
        return result


@dataclass(frozen=True, slots=True)
class CouplingFact:
    kind: str
    packages: tuple[str, ...]
    source: Source
    versions: tuple[tuple[str, str], ...] | Mapping[str, str] = ()
    note: str = ""
    tier: VerificationTier = VerificationTier.DERIVED

    def __post_init__(self) -> None:
        if self.kind not in {"exact-version-lockstep", "compatible-release-set"}:
            raise MatrixValidationError(
                "couple.kind must be exact-version-lockstep or compatible-release-set"
            )
        normalized_packages = tuple(_package(p, "couple.packages") for p in self.packages)
        if len(normalized_packages) < 2 or len(set(normalized_packages)) != len(
            normalized_packages
        ):
            raise MatrixValidationError("couple.packages must contain distinct package names")
        packages = tuple(sorted(normalized_packages))
        object.__setattr__(self, "packages", packages)
        raw_versions = self.versions
        if isinstance(raw_versions, Mapping):
            version_pairs = tuple(
                (_package(k, "couple.versions"), _version(v, "couple.versions"))
                for k, v in raw_versions.items()
            )
        elif isinstance(raw_versions, (list, tuple)):
            version_pairs = tuple(
                (_package(k, "couple.versions"), _version(v, "couple.versions"))
                for k, v in raw_versions
            )
        else:
            raise MatrixValidationError("couple.versions must be a package/version table")
        if len({package for package, _ in version_pairs}) != len(version_pairs):
            raise MatrixValidationError("couple.versions must contain distinct package names")
        version_map = dict(version_pairs)
        if self.kind == "compatible-release-set" and set(version_map) != set(packages):
            raise MatrixValidationError(
                "compatible-release-set must give one version for every package"
            )
        if set(version_map) - set(packages):
            raise MatrixValidationError("couple.versions contains an unlisted package")
        versions = tuple(
            (package, version_map[package]) for package in packages if package in version_map
        )
        object.__setattr__(self, "versions", versions)
        object.__setattr__(self, "source", _source(self.source, "couple"))
        object.__setattr__(self, "tier", _tier(self.tier, "couple"))
        _require_derived_tier(self.tier, "couple")

    @property
    def key(self) -> tuple[Any, ...]:
        return self.kind, self.packages, self.versions

    @property
    def version_map(self) -> Mapping[str, str]:
        return MappingProxyType(dict(self.versions))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> CouplingFact:
        _check_keys(
            value,
            allowed={"kind", "packages", "versions", "note", "tier", "source"},
            required={"kind", "packages", "source"},
            where="couple",
        )
        data = dict(value)
        data.setdefault("versions", {})
        data.setdefault("tier", 0)
        data["source"] = _source(data["source"], "couple")
        return cls(**data)

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {"kind": self.kind, "packages": list(self.packages)}
        if self.versions:
            result["versions"] = dict(self.versions)
        if self.note:
            result["note"] = self.note
        result["tier"] = int(self.tier)
        result["source"] = self.source.to_mapping()
        return result


@dataclass(frozen=True, slots=True)
class KnownBrokenFact:
    id: str
    description: str
    match: tuple[tuple[str, Any], ...] | Mapping[str, Any]
    workaround: str
    source: Source
    tier: VerificationTier = VerificationTier.DERIVED

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", self.id):
            raise MatrixValidationError("known_broken.id must be a lowercase slug")
        if not isinstance(self.description, str) or not self.description.strip():
            raise MatrixValidationError("known_broken.description cannot be empty")
        if not isinstance(self.workaround, str) or not self.workaround.strip():
            raise MatrixValidationError("known_broken.workaround cannot be empty")
        match = self.match
        if isinstance(match, Mapping):
            match = tuple(
                (str(key), _freeze_value(value, f"known_broken.match.{key}"))
                for key, value in sorted(match.items())
            )
        elif isinstance(match, (tuple, list)):
            match = tuple((str(k), _freeze_value(v, f"known_broken.match.{k}")) for k, v in match)
        else:
            raise MatrixValidationError("known_broken.match must be a TOML table")
        if not match:
            raise MatrixValidationError("known_broken.match cannot be empty")
        allowed_match_keys = {
            "package",
            "version",
            "torch",
            "cuda_line",
            "cxx11abi",
            "python",
            "platform",
            "source_build",
        }
        unknown_match_keys = {key for key, _ in match}.difference(allowed_match_keys)
        if unknown_match_keys:
            raise MatrixValidationError(
                "known_broken.match has unknown field(s): " + ", ".join(sorted(unknown_match_keys))
            )
        normalized: list[tuple[str, Any]] = []
        for key, value in match:
            if key == "package":
                if not isinstance(value, str):
                    raise MatrixValidationError("known_broken.match.package must be a string")
                value = _package(value, "known_broken.match.package")
            elif key in {"version", "torch"}:
                if not isinstance(value, str):
                    raise MatrixValidationError(f"known_broken.match.{key} must be a string")
                value = _version(value, f"known_broken.match.{key}")
            elif key == "cuda_line":
                value = _cuda(value, "known_broken.match.cuda_line", allow_x=True)
            elif key == "cxx11abi" and not isinstance(value, bool):
                raise MatrixValidationError("known_broken.match.cxx11abi must be true or false")
            elif key == "source_build" and not isinstance(value, bool):
                raise MatrixValidationError("known_broken.match.source_build must be true or false")
            elif key == "python" and (
                not isinstance(value, str) or not _PYTHON_TAG_RE.fullmatch(value)
            ):
                raise MatrixValidationError(
                    "known_broken.match.python must be a PEP 425 interpreter tag"
                )
            elif key == "platform" and (
                not isinstance(value, str) or not _PLATFORM_RE.fullmatch(value)
            ):
                raise MatrixValidationError(
                    "known_broken.match.platform must be a PEP 425 platform tag"
                )
            normalized.append((key, value))
        object.__setattr__(self, "match", tuple(normalized))
        object.__setattr__(self, "source", _source(self.source, "known_broken"))
        object.__setattr__(self, "tier", _tier(self.tier, "known_broken"))
        _require_derived_tier(self.tier, "known_broken")

    @property
    def key(self) -> str:
        return self.id

    @property
    def match_map(self) -> Mapping[str, Any]:
        return MappingProxyType({key: _thaw_value(value) for key, value in self.match_items})

    @property
    def match_items(self) -> tuple[tuple[str, Any], ...]:
        """The frozen match table, narrowed after ``__post_init__``."""

        return cast(tuple[tuple[str, Any], ...], self.match)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> KnownBrokenFact:
        _check_keys(
            value,
            allowed={"id", "description", "match", "workaround", "tier", "source"},
            required={"id", "description", "match", "workaround", "source"},
            where="known_broken",
        )
        data = dict(value)
        data.setdefault("tier", 0)
        data["source"] = _source(data["source"], "known_broken")
        return cls(**data)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "match": {key: _thaw_value(value) for key, value in self.match_items},
            "workaround": self.workaround,
            "tier": int(self.tier),
            "source": self.source.to_mapping(),
        }


@dataclass(frozen=True, slots=True)
class ArchitectureConstraintFact:
    arch: str
    source: Source
    cuda_min: str | None = None
    cuda_max: str | None = None
    note: str = ""
    tier: VerificationTier = VerificationTier.DERIVED

    def __post_init__(self) -> None:
        if not isinstance(self.arch, str) or not _ARCH_RE.fullmatch(self.arch):
            raise MatrixValidationError("architecture.arch must look like sm_90")
        object.__setattr__(self, "arch", self.arch.lower())
        if self.cuda_min is None and self.cuda_max is None:
            raise MatrixValidationError("architecture requires cuda_min or cuda_max")
        if self.cuda_min is not None:
            object.__setattr__(self, "cuda_min", _cuda(self.cuda_min, "architecture.cuda_min"))
        if self.cuda_max is not None:
            object.__setattr__(self, "cuda_max", _cuda(self.cuda_max, "architecture.cuda_max"))
        object.__setattr__(self, "source", _source(self.source, "architecture"))
        object.__setattr__(self, "tier", _tier(self.tier, "architecture"))
        _require_derived_tier(self.tier, "architecture")

    @property
    def key(self) -> tuple[str, str | None, str | None]:
        return self.arch, self.cuda_min, self.cuda_max

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ArchitectureConstraintFact:
        _check_keys(
            value,
            allowed={"arch", "cuda_min", "cuda_max", "note", "tier", "source"},
            required={"arch", "source"},
            where="architecture",
        )
        data = dict(value)
        data.setdefault("tier", 0)
        data["source"] = _source(data["source"], "architecture")
        return cls(**data)

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {"arch": self.arch}
        if self.cuda_min is not None:
            result["cuda_min"] = self.cuda_min
        if self.cuda_max is not None:
            result["cuda_max"] = self.cuda_max
        if self.note:
            result["note"] = self.note
        result["tier"] = int(self.tier)
        result["source"] = self.source.to_mapping()
        return result


@dataclass(frozen=True, slots=True)
class SourceBuildFact:
    package: str
    source: Source
    version_spec: str = ""
    requirements: tuple[str, ...] = ()
    flags: tuple[str, ...] = ()
    estimate_minutes: int | None = None
    ram_gb_per_job: float | None = None
    note: str = ""
    tier: VerificationTier = VerificationTier.DERIVED

    def __post_init__(self) -> None:
        object.__setattr__(self, "package", _package(self.package, "source_build.package"))
        object.__setattr__(self, "source", _source(self.source, "source_build"))
        if not isinstance(self.version_spec, str):
            raise MatrixValidationError("source_build.version_spec must be a PEP 440 specifier")
        try:
            normalized_spec = str(SpecifierSet(self.version_spec))
        except InvalidSpecifier as exc:
            raise MatrixValidationError(
                f"source_build.version_spec is invalid: {self.version_spec!r}"
            ) from exc
        object.__setattr__(self, "version_spec", normalized_spec)
        object.__setattr__(
            self, "requirements", _string_tuple(self.requirements, "source_build.requirements")
        )
        object.__setattr__(self, "flags", _string_tuple(self.flags, "source_build.flags"))
        if self.estimate_minutes is not None and (
            isinstance(self.estimate_minutes, bool) or self.estimate_minutes <= 0
        ):
            raise MatrixValidationError("source_build.estimate_minutes must be positive")
        if self.ram_gb_per_job is not None and self.ram_gb_per_job <= 0:
            raise MatrixValidationError("source_build.ram_gb_per_job must be positive")
        object.__setattr__(self, "tier", _tier(self.tier, "source_build"))
        _require_derived_tier(self.tier, "source_build")

    @property
    def key(self) -> tuple[str, str]:
        return self.package, self.version_spec

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> SourceBuildFact:
        _check_keys(
            value,
            allowed={
                "package",
                "version_spec",
                "requirements",
                "flags",
                "estimate_minutes",
                "ram_gb_per_job",
                "note",
                "tier",
                "source",
            },
            required={"package", "source"},
            where="source_build",
        )
        data = dict(value)
        data.setdefault("tier", 0)
        data["source"] = _source(data["source"], "source_build")
        return cls(**data)

    def to_mapping(self) -> dict[str, Any]:
        result: dict[str, Any] = {"package": self.package}
        for name in (
            "version_spec",
            "requirements",
            "flags",
            "estimate_minutes",
            "ram_gb_per_job",
            "note",
        ):
            value = getattr(self, name)
            if value not in (None, "", ()):
                result[name] = list(value) if isinstance(value, tuple) else value
        result["tier"] = int(self.tier)
        result["source"] = self.source.to_mapping()
        return result


Fact: TypeAlias = (
    WheelFact
    | TorchBuildFact
    | TestedAgainstFact
    | DriverConstraintFact
    | CouplingFact
    | KnownBrokenFact
    | ArchitectureConstraintFact
    | SourceBuildFact
)


@dataclass(frozen=True, slots=True)
class MatrixData:
    metadata: MatrixMetadata
    wheels: tuple[WheelFact, ...] = field(default_factory=tuple)
    torch_builds: tuple[TorchBuildFact, ...] = field(default_factory=tuple)
    tested_against: tuple[TestedAgainstFact, ...] = field(default_factory=tuple)
    constraints: tuple[DriverConstraintFact, ...] = field(default_factory=tuple)
    couplings: tuple[CouplingFact, ...] = field(default_factory=tuple)
    known_broken: tuple[KnownBrokenFact, ...] = field(default_factory=tuple)
    architectures: tuple[ArchitectureConstraintFact, ...] = field(default_factory=tuple)
    source_builds: tuple[SourceBuildFact, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, MatrixMetadata):
            raise MatrixValidationError("matrix metadata must be MatrixMetadata")
        expected = (
            ("wheels", WheelFact),
            ("torch_builds", TorchBuildFact),
            ("tested_against", TestedAgainstFact),
            ("constraints", DriverConstraintFact),
            ("couplings", CouplingFact),
            ("known_broken", KnownBrokenFact),
            ("architectures", ArchitectureConstraintFact),
            ("source_builds", SourceBuildFact),
        )
        for name, fact_type in expected:
            facts = tuple(getattr(self, name))
            if any(not isinstance(fact, fact_type) for fact in facts):
                raise MatrixValidationError(f"matrix.{name} contains the wrong fact type")
            object.__setattr__(self, name, facts)
        coupling_kinds: dict[tuple[str, ...], set[str]] = {}
        for coupling in self.couplings:
            package_set = tuple(sorted(coupling.packages))
            coupling_kinds.setdefault(package_set, set()).add(coupling.kind)
        mixed = [packages for packages, kinds in coupling_kinds.items() if len(kinds) > 1]
        if mixed:
            packages = ", ".join(mixed[0])
            raise MatrixValidationError(
                f"coupling package set {packages} mixes incompatible coupling kinds"
            )

    @property
    def facts(self) -> tuple[Fact, ...]:
        return (
            *self.wheels,
            *self.torch_builds,
            *self.tested_against,
            *self.constraints,
            *self.couplings,
            *self.known_broken,
            *self.architectures,
            *self.source_builds,
        )


# Compatibility aliases make the public vocabulary pleasant while keeping
# explicit ``Fact`` suffixes in tracebacks and generated documentation.
Wheel = WheelFact
TorchBuild = TorchBuildFact
TestedAgainst = TestedAgainstFact
Constraint = DriverConstraintFact
Couple = CouplingFact
KnownBroken = KnownBrokenFact
ArchitectureConstraint = ArchitectureConstraintFact
SourceBuild = SourceBuildFact
Matrix = MatrixData


__all__ = [
    "SCHEMA_VERSION",
    "ArchitectureConstraint",
    "ArchitectureConstraintFact",
    "Constraint",
    "Couple",
    "CouplingFact",
    "DriverConstraintFact",
    "Fact",
    "KnownBroken",
    "KnownBrokenFact",
    "Matrix",
    "MatrixData",
    "MatrixMetadata",
    "MatrixValidationError",
    "SourceBuild",
    "SourceBuildFact",
    "TestedAgainst",
    "TestedAgainstFact",
    "TorchBuild",
    "TorchBuildFact",
    "Wheel",
    "WheelFact",
]
