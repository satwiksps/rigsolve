"""TOML loading, validation, merging, indexing, and statistics."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from importlib import resources
from pathlib import Path
from types import MappingProxyType
from typing import Any, TypeVar

from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from rigsolve._atomic import atomic_write

from .provenance import VerificationTier
from .schema import (
    ArchitectureConstraintFact,
    CouplingFact,
    DriverConstraintFact,
    Fact,
    KnownBrokenFact,
    MatrixData,
    MatrixMetadata,
    MatrixValidationError,
    SourceBuildFact,
    TestedAgainstFact,
    TorchBuildFact,
    WheelFact,
)

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - selected on the minimum supported runtime
    import tomli as tomllib


_F = TypeVar("_F", bound=Fact)


@dataclass(frozen=True, slots=True)
class MatrixStats:
    matrix_version: str
    fact_count: int
    family_counts: tuple[tuple[str, int], ...]
    package_counts: tuple[tuple[str, int], ...]
    tier_counts: tuple[tuple[int, int], ...]
    source_counts: tuple[tuple[str, int], ...]
    oldest_harvest: date | None
    newest_harvest: date | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "matrix_version": self.matrix_version,
            "fact_count": self.fact_count,
            "families": dict(self.family_counts),
            "packages": dict(self.package_counts),
            "tiers": {str(key): value for key, value in self.tier_counts},
            "sources": dict(self.source_counts),
            "oldest_harvest": (self.oldest_harvest.isoformat() if self.oldest_harvest else None),
            "newest_harvest": (self.newest_harvest.isoformat() if self.newest_harvest else None),
        }


def _version_key(value: str) -> Version:
    try:
        return Version(value)
    except InvalidVersion:  # schema validation normally makes this unreachable
        return Version("0")


def _driver_key(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def cuda_lines_compatible(left: str, right: str) -> bool:
    """Compare CUDA labels without inventing patch-level compatibility.

    A package-specific major label such as flash-attn's ``cu12`` matches a
    concrete PyTorch build line such as ``12.8``.  Two concrete minor labels
    must match through the minor component.
    """

    def parts(label: str) -> tuple[int, ...] | None:
        value = label.lower().removesuffix(".x")
        if value.startswith("cu"):
            digits = value[2:]
            if not digits.isdigit():
                return None
            if len(digits) == 2:
                value = digits
            elif len(digits) == 3:
                value = f"{digits[:2]}.{digits[2]}"
            else:
                return None
        tokens = value.split(".")
        if not 1 <= len(tokens) <= 3 or any(not token.isdigit() for token in tokens):
            return None
        return tuple(int(token) for token in tokens)

    left_parts = parts(left)
    right_parts = parts(right)
    if left_parts is None or right_parts is None:
        return False
    if left_parts[0] != right_parts[0]:
        return False
    if len(left_parts) == 1 or len(right_parts) == 1:
        return True
    return left_parts[1] == right_parts[1]


def _torch_versions_compatible(left: str, right: str) -> bool:
    left_release = Version(left).release
    right_release = Version(right).release
    return left_release[:2] == right_release[:2]


def _scoped_version_matches(expected: str, actual: str) -> bool:
    expected_version = Version(expected)
    actual_version = Version(actual)
    if expected_version.local is not None:
        return expected_version == actual_version
    return expected_version.public == actual_version.public


def _scoped_torch_matches(expected: str, actual: str) -> bool:
    expected_version = Version(expected)
    actual_version = Version(actual)
    if (
        expected_version.pre,
        expected_version.dev,
        expected_version.post,
    ) != (actual_version.pre, actual_version.dev, actual_version.post):
        return False
    if expected_version.local is not None and expected_version != actual_version:
        return False
    expected_release = expected_version.release
    actual_release = actual_version.release
    return len(actual_release) >= len(expected_release) and (
        actual_release[: len(expected_release)] == expected_release
    )


def _scoped_cuda_matches(expected: str, actual: str) -> bool:
    expected_parts = expected.removesuffix(".x").split(".")
    actual_parts = actual.removesuffix(".x").split(".")
    return len(actual_parts) >= len(expected_parts) and (
        actual_parts[: len(expected_parts)] == expected_parts
    )


def _python_to_tag(value: str) -> str:
    if value.startswith(("cp", "pp", "py")):
        return value
    parts = value.split(".")
    if len(parts) == 2 and all(part.isdigit() for part in parts):
        return f"cp{parts[0]}{parts[1]}"
    return value


def _fact_preference(fact: Fact) -> tuple[int, date, str]:
    return int(fact.tier), fact.source.harvested_date, repr(fact)


class MatrixStore:
    """An immutable matrix plus lookup indexes used by the solver and checker."""

    def __init__(self, data: MatrixData, *, validate: bool = True) -> None:
        if validate:
            validate_matrix(data)
        self._data = data

        wheel_index: defaultdict[str, list[WheelFact]] = defaultdict(list)
        build_index: defaultdict[str, list[TorchBuildFact]] = defaultdict(list)
        broken_index: defaultdict[str, list[KnownBrokenFact]] = defaultdict(list)
        source_build_index: defaultdict[str, list[SourceBuildFact]] = defaultdict(list)

        for wheel in data.wheels:
            wheel_index[wheel.package].append(wheel)
        for build in data.torch_builds:
            build_index[build.package].append(build)
        for broken in data.known_broken:
            package = dict(broken.match_items).get("package")
            broken_index[str(package) if package else "*"].append(broken)
        for source_build in data.source_builds:
            source_build_index[source_build.package].append(source_build)

        def freeze_index(
            index: Mapping[str, list[_F]], sort_key: Any
        ) -> Mapping[str, tuple[_F, ...]]:
            return MappingProxyType(
                {key: tuple(sorted(values, key=sort_key)) for key, values in sorted(index.items())}
            )

        self._wheels_by_package = freeze_index(
            wheel_index,
            lambda f: (_version_key(f.version), f.cuda_line or "", f.python or "", f.url),
        )
        self._builds_by_package = freeze_index(
            build_index,
            lambda f: (_version_key(f.version), f.cuda_line, f.index_url),
        )
        self._broken_by_package = freeze_index(broken_index, lambda f: f.id)
        self._source_builds_by_package = freeze_index(
            source_build_index, lambda f: (f.version_spec, f.package)
        )

    @property
    def data(self) -> MatrixData:
        return self._data

    @property
    def metadata(self) -> MatrixMetadata:
        return self._data.metadata

    @property
    def matrix_version(self) -> str:
        return self.metadata.matrix_version

    @property
    def digest(self) -> str:
        """SHA-256 of the canonical TOML representation."""

        return hashlib.sha256(dump_matrix(self).encode("utf-8")).hexdigest()

    @property
    def facts(self) -> tuple[Fact, ...]:
        return self._data.facts

    @property
    def wheels(self) -> tuple[WheelFact, ...]:
        return self._data.wheels

    @property
    def torch_builds(self) -> tuple[TorchBuildFact, ...]:
        return self._data.torch_builds

    @property
    def tested_against(self) -> tuple[TestedAgainstFact, ...]:
        return self._data.tested_against

    @property
    def constraints(self) -> tuple[DriverConstraintFact, ...]:
        return self._data.constraints

    @property
    def couplings(self) -> tuple[CouplingFact, ...]:
        return self._data.couplings

    @property
    def known_broken(self) -> tuple[KnownBrokenFact, ...]:
        return self._data.known_broken

    @property
    def architectures(self) -> tuple[ArchitectureConstraintFact, ...]:
        return self._data.architectures

    @property
    def source_builds(self) -> tuple[SourceBuildFact, ...]:
        return self._data.source_builds

    @property
    def packages(self) -> tuple[str, ...]:
        names: set[str] = set(self._wheels_by_package)
        names.update(self._builds_by_package)
        names.update(self._source_builds_by_package)
        for fact in self._data.couplings:
            names.update(fact.packages)
        return tuple(sorted(names))

    def find_wheels(
        self,
        package: str,
        *,
        version: str | None = None,
        cuda_line: str | None = None,
        torch: str | None = None,
        cxx11abi: bool | None = None,
        python: str | None = None,
        abi: str | None = None,
        platform: str | None = None,
        arch: str | None = None,
        minimum_tier: int | VerificationTier = VerificationTier.DERIVED,
        include_yanked: bool = False,
    ) -> tuple[WheelFact, ...]:
        """Return wheel facts matching only explicitly known dimensions."""

        name = canonicalize_name(package)
        required_tier = VerificationTier.coerce(minimum_tier)
        python_tag = _python_to_tag(python) if python is not None else None
        matches: list[WheelFact] = []
        for fact in self._wheels_by_package.get(name, ()):
            if fact.yanked and not include_yanked:
                continue
            if version is not None and Version(fact.version) != Version(version):
                continue
            if cuda_line is not None and (
                fact.cuda_line is None or not cuda_lines_compatible(fact.cuda_line, cuda_line)
            ):
                continue
            if torch is not None and (
                fact.torch is None or not _torch_versions_compatible(fact.torch, torch)
            ):
                continue
            if cxx11abi is not None and fact.cxx11abi is not cxx11abi:
                continue
            if python_tag is not None and (
                fact.python is None or python_tag not in fact.python.split(".")
            ):
                continue
            if abi is not None and (fact.abi is None or abi not in fact.abi.split(".")):
                continue
            if platform is not None and (
                fact.platform is None or platform not in fact.platform.split(".")
            ):
                continue
            if arch is not None and (not fact.archs or arch.lower() not in fact.archs):
                continue
            if fact.tier < required_tier:
                continue
            matches.append(fact)
        return tuple(matches)

    # A concise synonym that reads naturally in constraint builders.
    wheels_for = find_wheels

    def torch_builds_for(
        self,
        version: str | None = None,
        *,
        cuda_line: str | None = None,
        python: str | None = None,
        platform: str | None = None,
        minimum_tier: int | VerificationTier = VerificationTier.DERIVED,
    ) -> tuple[TorchBuildFact, ...]:
        required_tier = VerificationTier.coerce(minimum_tier)
        matches: list[TorchBuildFact] = []
        for fact in self._builds_by_package.get("torch", ()):
            if version is not None and Version(fact.version) != Version(version):
                continue
            if cuda_line is not None and not cuda_lines_compatible(fact.cuda_line, cuda_line):
                continue
            if python is not None and fact.pythons and python not in fact.pythons:
                continue
            if platform is not None and fact.platforms and platform not in fact.platforms:
                continue
            if fact.tier < required_tier:
                continue
            matches.append(fact)
        return tuple(matches)

    def compatible_release_sets(self, package: str | None = None) -> tuple[CouplingFact, ...]:
        name = canonicalize_name(package) if package else None
        return tuple(
            fact
            for fact in self._data.couplings
            if fact.kind == "compatible-release-set" and (name is None or name in fact.packages)
        )

    def known_broken_for(self, assignment: Mapping[str, Any]) -> tuple[KnownBrokenFact, ...]:
        """Return negative facts whose complete match table fits ``assignment``."""

        normalized = dict(assignment)
        if isinstance(normalized.get("package"), str):
            normalized["package"] = canonicalize_name(normalized["package"])
        package = normalized.get("package")
        candidates = [*self._broken_by_package.get("*", ())]
        if package:
            candidates.extend(self._broken_by_package.get(str(package), ()))
        result: list[KnownBrokenFact] = []
        for fact in candidates:

            def dimension_matches(key: str, expected: Any) -> bool:
                if key not in normalized:
                    return False
                actual = normalized[key]
                actual_values = (
                    tuple(actual)
                    if isinstance(actual, (list, tuple, set, frozenset))
                    else (actual,)
                )
                return any(scalar_matches(key, expected, value) for value in actual_values)

            def scalar_matches(key: str, expected: Any, actual: Any) -> bool:
                if key == "torch" and isinstance(expected, str) and isinstance(actual, str):
                    try:
                        return _scoped_torch_matches(expected, actual)
                    except InvalidVersion:
                        return expected == actual
                if key == "version" and isinstance(expected, str) and isinstance(actual, str):
                    try:
                        return _scoped_version_matches(expected, actual)
                    except InvalidVersion:
                        return expected == actual
                if (
                    key in {"cuda", "cuda_line"}
                    and isinstance(expected, str)
                    and isinstance(actual, str)
                ):
                    return _scoped_cuda_matches(expected, actual)
                return bool(actual == expected)

            if all(dimension_matches(key, value) for key, value in fact.match_items):
                result.append(fact)
        return tuple(result)

    def source_builds_for(self, package: str) -> tuple[SourceBuildFact, ...]:
        return self._source_builds_by_package.get(canonicalize_name(package), ())

    def driver_minimum(
        self,
        cuda_runtime: str,
        platform: str = "linux",
        *,
        compatibility: str = "minor-compatible",
    ) -> str | None:
        candidates: list[str] = []
        for fact in self._data.constraints:
            if fact.compatibility != compatibility:
                continue
            if cuda_lines_compatible(fact.cuda_runtime, cuda_runtime):
                minimum = fact.minimum_for(platform)
                if minimum:
                    candidates.append(minimum)
        if not candidates:
            return None
        return max(candidates, key=_driver_key)

    def stats(self) -> MatrixStats:
        family_counts = {
            "wheel": len(self.wheels),
            "torch_build": len(self.torch_builds),
            "tested_against": len(self.tested_against),
            "constraint": len(self.constraints),
            "couple": len(self.couplings),
            "known_broken": len(self.known_broken),
            "architecture": len(self.architectures),
            "source_build": len(self.source_builds),
        }
        packages: Counter[str] = Counter()
        tiers: Counter[int] = Counter()
        sources: Counter[str] = Counter()
        dates: list[date] = []
        for fact in self.facts:
            if hasattr(fact, "package"):
                packages[str(fact.package)] += 1
            elif isinstance(fact, CouplingFact):
                packages.update(fact.packages)
            tiers[int(fact.tier)] += 1
            sources[fact.source.kind] += 1
            dates.append(fact.source.harvested_date)
        return MatrixStats(
            matrix_version=self.matrix_version,
            fact_count=len(self.facts),
            family_counts=tuple(sorted(family_counts.items())),
            package_counts=tuple(sorted(packages.items())),
            tier_counts=tuple(sorted(tiers.items())),
            source_counts=tuple(sorted(sources.items())),
            oldest_harvest=min(dates) if dates else None,
            newest_harvest=max(dates) if dates else None,
        )

    def merge(self, *others: MatrixStore | MatrixData, conflict: str = "newer") -> MatrixStore:
        return merge_matrices(self, *others, conflict=conflict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> MatrixStore:
        return cls(matrix_from_mapping(value))

    @classmethod
    def from_toml(cls, text: str | bytes) -> MatrixStore:
        if isinstance(text, bytes):
            text = text.decode("utf-8")
        try:
            value = tomllib.loads(text)
        except (tomllib.TOMLDecodeError, UnicodeError) as exc:
            raise MatrixValidationError(f"invalid matrix TOML: {exc}") from exc
        return cls.from_mapping(value)

    @classmethod
    def load(cls, source: Any = None) -> MatrixStore:
        return load_matrix(source)


_TOP_LEVEL = {
    "meta",
    "wheel",
    "torch_build",
    "tested_against",
    "constraint",
    "couple",
    "known_broken",
    "architecture",
    "source_build",
}


def _fact_list(value: Mapping[str, Any], key: str, fact_type: Any) -> tuple[_F, ...]:
    raw = value.get(key, [])
    if not isinstance(raw, list):
        raise MatrixValidationError(f"top-level {key} must be an array of tables")
    result: list[_F] = []
    for index, item in enumerate(raw):
        try:
            parsed: _F = fact_type.from_mapping(item)
            result.append(parsed)
        except (MatrixValidationError, TypeError, ValueError) as exc:
            if isinstance(exc, MatrixValidationError):
                raise MatrixValidationError(f"{key}[{index}]: {exc}") from exc
            raise MatrixValidationError(f"{key}[{index}] is invalid: {exc}") from exc
    return tuple(result)


def matrix_from_mapping(value: Mapping[str, Any]) -> MatrixData:
    if not isinstance(value, Mapping):
        raise MatrixValidationError("matrix root must be a TOML table")
    unknown = set(value) - _TOP_LEVEL
    if unknown:
        raise MatrixValidationError(
            "unknown top-level matrix table(s): " + ", ".join(sorted(map(str, unknown)))
        )
    if "meta" not in value:
        raise MatrixValidationError("matrix is missing required [meta] table")
    data = MatrixData(
        metadata=MatrixMetadata.from_mapping(value["meta"]),
        wheels=_fact_list(value, "wheel", WheelFact),
        torch_builds=_fact_list(value, "torch_build", TorchBuildFact),
        tested_against=_fact_list(value, "tested_against", TestedAgainstFact),
        constraints=_fact_list(value, "constraint", DriverConstraintFact),
        couplings=_fact_list(value, "couple", CouplingFact),
        known_broken=_fact_list(value, "known_broken", KnownBrokenFact),
        architectures=_fact_list(value, "architecture", ArchitectureConstraintFact),
        source_builds=_fact_list(value, "source_build", SourceBuildFact),
    )
    validate_matrix(data)
    return data


def validate_matrix(data: MatrixData) -> None:
    """Validate cross-fact invariants in addition to each frozen dataclass."""

    families: tuple[tuple[str, Sequence[Fact]], ...] = (
        ("wheel", data.wheels),
        ("torch_build", data.torch_builds),
        ("tested_against", data.tested_against),
        ("constraint", data.constraints),
        ("couple", data.couplings),
        ("known_broken", data.known_broken),
        ("architecture", data.architectures),
        ("source_build", data.source_builds),
    )
    errors: list[str] = []
    for family, facts in families:
        seen: dict[Any, int] = {}
        for index, fact in enumerate(facts):
            key = fact.key
            if key in seen:
                errors.append(
                    f"duplicate {family} fact at indexes {seen[key]} and {index}: {key!r}"
                )
            else:
                seen[key] = index
            if fact.source.harvested_date > data.metadata.generated_date:
                errors.append(
                    f"{family}[{index}] was harvested after meta.generated "
                    f"({fact.source.harvested_date} > {data.metadata.generated_date})"
                )
            if (
                isinstance(fact, WheelFact)
                and fact.tier is VerificationTier.RUNS
                and not fact.archs
            ):
                errors.append(
                    f"wheel[{index}] is tier 3 but does not record the architecture it ran on"
                )
    if errors:
        raise MatrixValidationError("matrix validation failed:\n- " + "\n- ".join(errors))


def _coerce_store(value: MatrixStore | MatrixData) -> MatrixStore:
    return value if isinstance(value, MatrixStore) else MatrixStore(value)


def _merge_family(stores: Sequence[MatrixStore], family: str, *, conflict: str) -> tuple[Any, ...]:
    selected: dict[Any, Fact] = {}
    for store in stores:
        for fact in getattr(store, family):
            key = fact.key
            previous = selected.get(key)
            if previous is None or previous == fact:
                selected[key] = fact
                continue
            if conflict == "error":
                raise MatrixValidationError(
                    f"conflicting {family} fact for {key!r}: {previous!r} vs {fact!r}"
                )
            if conflict == "incoming":
                selected[key] = fact
            elif conflict == "newer":
                selected[key] = max((previous, fact), key=_fact_preference)
            else:
                raise ValueError("conflict must be 'newer', 'incoming', or 'error'")
    return tuple(sorted(selected.values(), key=lambda fact: repr(fact.key)))


def merge_matrices(
    base: MatrixStore | MatrixData,
    *others: MatrixStore | MatrixData,
    conflict: str = "newer",
) -> MatrixStore:
    stores = [_coerce_store(base), *(_coerce_store(item) for item in others)]
    newest = max(
        stores,
        key=lambda store: (store.metadata.generated_date, store.matrix_version),
    )
    data = MatrixData(
        metadata=newest.metadata,
        wheels=_merge_family(stores, "wheels", conflict=conflict),
        torch_builds=_merge_family(stores, "torch_builds", conflict=conflict),
        tested_against=_merge_family(stores, "tested_against", conflict=conflict),
        constraints=_merge_family(stores, "constraints", conflict=conflict),
        couplings=_merge_family(stores, "couplings", conflict=conflict),
        known_broken=_merge_family(stores, "known_broken", conflict=conflict),
        architectures=_merge_family(stores, "architectures", conflict=conflict),
        source_builds=_merge_family(stores, "source_builds", conflict=conflict),
    )
    return MatrixStore(data)


def load_bundled_matrix() -> MatrixStore:
    try:
        resource = resources.files("rigsolve.data").joinpath("matrix.toml")
        return MatrixStore.from_toml(resource.read_bytes())
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        raise MatrixValidationError("bundled compatibility matrix is missing") from exc


# Public spelling used by the CLI and solver integration.
load_bundled = load_bundled_matrix


def load_matrix(source: Any = None) -> MatrixStore:
    """Load a bundled matrix, a path, TOML text/bytes, or a parsed mapping."""

    if source is None:
        return load_bundled_matrix()
    if isinstance(source, MatrixStore):
        return source
    if isinstance(source, MatrixData):
        return MatrixStore(source)
    if isinstance(source, Mapping):
        return MatrixStore.from_mapping(source)
    if isinstance(source, bytes):
        return MatrixStore.from_toml(source)
    if isinstance(source, os.PathLike):
        path = Path(source)
        try:
            return MatrixStore.from_toml(path.read_bytes())
        except OSError as exc:
            raise MatrixValidationError(f"cannot read matrix {path}: {exc}") from exc
    if isinstance(source, str):
        if "\n" in source or source.lstrip().startswith("["):
            return MatrixStore.from_toml(source)
        path = Path(source)
        try:
            return MatrixStore.from_toml(path.read_bytes())
        except OSError as exc:
            raise MatrixValidationError(f"cannot read matrix {path}: {exc}") from exc
    raise TypeError(f"unsupported matrix source: {type(source).__name__}")


def _toml_key(value: str) -> str:
    if value.replace("-", "_").isalnum() and value[0].isalnum():
        return value
    return json.dumps(value, ensure_ascii=False)


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, date):
        return json.dumps(value.isoformat())
    if isinstance(value, Mapping):
        body = ", ".join(
            f"{_toml_key(str(key))} = {_toml_value(item)}" for key, item in value.items()
        )
        return "{ " + body + " }"
    if isinstance(value, (tuple, list)):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise TypeError(f"cannot encode {type(value).__name__} as TOML")


def dump_matrix(matrix: MatrixStore | MatrixData) -> str:
    """Serialize a matrix to deterministic, review-friendly TOML."""

    data = matrix.data if isinstance(matrix, MatrixStore) else matrix
    validate_matrix(data)
    lines: list[str] = ["[meta]"]
    for key, value in data.metadata.to_mapping().items():
        lines.append(f"{_toml_key(key)} = {_toml_value(value)}")

    families: tuple[tuple[str, Sequence[Any]], ...] = (
        ("wheel", data.wheels),
        ("torch_build", data.torch_builds),
        ("tested_against", data.tested_against),
        ("constraint", data.constraints),
        ("couple", data.couplings),
        ("known_broken", data.known_broken),
        ("architecture", data.architectures),
        ("source_build", data.source_builds),
    )
    for family, facts in families:
        for fact in facts:
            mapping = fact.to_mapping()
            source = mapping.pop("source")
            lines.extend(("", f"[[{family}]]"))
            for key, value in mapping.items():
                lines.append(f"{_toml_key(key)} = {_toml_value(value)}")
            lines.append(f"[{family}.source]")
            for key, value in source.items():
                lines.append(f"{_toml_key(key)} = {_toml_value(value)}")
    return "\n".join(lines) + "\n"


def save_matrix(path: str | os.PathLike[str], matrix: MatrixStore | MatrixData) -> Path:
    """Atomically write a validated matrix without risking a partial cache file."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = dump_matrix(matrix)
    atomic_write(destination, payload, create_parent=False)
    return destination


__all__ = [
    "MatrixStats",
    "MatrixStore",
    "cuda_lines_compatible",
    "dump_matrix",
    "load_bundled",
    "load_bundled_matrix",
    "load_matrix",
    "matrix_from_mapping",
    "merge_matrices",
    "save_matrix",
    "validate_matrix",
]
