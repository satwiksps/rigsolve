"""Translate matrix facts and a machine profile into an explainable CSP."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, cast

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from rigsolve.detect import MachineProfile, profile_from_target
from rigsolve.errors import UserInputError
from rigsolve.matrix import MatrixStore, SourceBuildFact, cuda_lines_compatible
from rigsolve.plan.install import InstallPlan, InstallStep
from rigsolve.solve.model import CSP, Constraint
from rigsolve.solve.search import solve_csp
from rigsolve.solve.unsat import minimal_unsatisfiable_subset

_NATIVE_GPU_PACKAGES = frozenset(
    {
        "bitsandbytes",
        "flash-attn",
        "flashinfer-python",
        "triton",
        "vllm",
        "xformers",
    }
)
_TORCH_NATIVE_EXTENSIONS = frozenset({"flash-attn", "flashinfer-python", "vllm", "xformers"})


@dataclass(frozen=True, slots=True)
class PackageCandidate:
    package: str
    version: str
    artifact_url: str | None = None
    artifact_sha256: str | None = None
    index_url: str | None = None
    cuda_line: str | None = None
    cuda_exact: str | None = None
    torch_version: str | None = None
    cxx11abi: bool | None = None
    python_tags: tuple[str, ...] = ()
    abi_tags: tuple[str, ...] = ()
    platforms: tuple[str, ...] = ()
    archs: tuple[str, ...] = ()
    tier: int = 0
    citations: tuple[str, ...] = ()
    sources: tuple[Any, ...] = ()
    source_build: bool = False
    source_requirements: tuple[str, ...] = ()
    source_flags: tuple[str, ...] = ()
    estimate_minutes: int | None = None
    ram_gb_per_job: float | None = None

    @property
    def parsed_version(self) -> Version:
        return Version(self.version)

    @property
    def identity(self) -> tuple[Any, ...]:
        return (
            self.package,
            self.version,
            self.artifact_url,
            self.artifact_sha256,
            self.index_url,
            self.cuda_line,
            self.cuda_exact,
            self.torch_version,
            self.cxx11abi,
            self.python_tags,
            self.abi_tags,
            self.platforms,
            self.archs,
            self.source_build,
            self.source_requirements,
            self.source_flags,
            self.estimate_minutes,
            self.ram_gb_per_job,
        )


@dataclass(frozen=True, slots=True)
class CoverageGap:
    package: str
    requested: str
    modeled_versions: tuple[str, ...] = ()
    sources: tuple[Any, ...] = ()


@dataclass(frozen=True, slots=True)
class ResolutionFailure:
    requested: tuple[str, ...]
    missing_packages: tuple[str, ...] = ()
    coverage_gaps: tuple[CoverageGap, ...] = ()
    core: tuple[Constraint, ...] = ()
    suggestions: tuple[str, ...] = ()
    explored_nodes: int = 0


@dataclass(frozen=True, slots=True)
class ResolutionOutcome:
    plan: InstallPlan | None = None
    failure: ResolutionFailure | None = None

    @property
    def satisfiable(self) -> bool:
        return self.plan is not None


def parse_requirements(specs: Sequence[str]) -> tuple[Requirement, ...]:
    if not specs:
        raise UserInputError("at least one package must follow --want")
    result: list[Requirement] = []
    seen: set[str] = set()
    for spec in specs:
        try:
            requirement = Requirement(spec)
        except InvalidRequirement as error:
            raise UserInputError(f"invalid package requirement {spec!r}: {error}") from error
        name = canonicalize_name(requirement.name)
        if requirement.url:
            raise UserInputError(
                "direct URL requirements are not solver inputs; pin a version instead"
            )
        if requirement.extras:
            extras = ", ".join(sorted(requirement.extras))
            raise UserInputError(
                f"extras are not solver inputs ({name}[{extras}]); request the package name only"
            )
        if requirement.marker is not None:
            raise UserInputError(
                "PEP 508 environment markers are not supported as solver inputs; "
                "describe the environment with --target"
            )
        exact = tuple(requirement.specifier)
        if len(exact) == 1 and exact[0].operator in {"==", "==="}:
            try:
                local = Version(exact[0].version).local
            except InvalidVersion:
                local = None
            if local is not None and not re.fullmatch(r"cu\d{2,3}", local):
                raise UserInputError(
                    f"unsupported local version tag '+{local}'; only PyTorch '+cuNNN' "
                    "pins can be mapped to a CUDA build axis"
                )
        if name in seen:
            raise UserInputError(f"package requested more than once: {name}")
        seen.add(name)
        result.append(requirement)
    return tuple(result)


def _merge_candidates(candidates: Sequence[PackageCandidate]) -> tuple[PackageCandidate, ...]:
    merged: dict[tuple[Any, ...], PackageCandidate] = {}
    for candidate in candidates:
        current = merged.get(candidate.identity)
        if current is None:
            merged[candidate.identity] = candidate
            continue
        merged[candidate.identity] = replace(
            current,
            tier=max(current.tier, candidate.tier),
            citations=tuple(dict.fromkeys((*current.citations, *candidate.citations))),
            sources=tuple(dict.fromkeys((*current.sources, *candidate.sources))),
        )
    return tuple(
        sorted(
            merged.values(),
            key=lambda item: (
                item.package,
                item.parsed_version,
                item.cuda_line or "",
                item.python_tags,
                item.abi_tags,
                item.platforms,
                item.artifact_url or "",
            ),
        )
    )


def _base_candidates(store: MatrixStore) -> dict[str, tuple[PackageCandidate, ...]]:
    result: dict[str, list[PackageCandidate]] = {}
    for torch_fact in store.torch_builds:
        result.setdefault(torch_fact.package, []).append(
            PackageCandidate(
                package=torch_fact.package,
                version=torch_fact.version,
                index_url=torch_fact.index_url,
                cuda_line=torch_fact.cuda_line,
                cuda_exact=torch_fact.cuda_exact,
                cxx11abi=torch_fact.cxx11abi,
                python_tags=torch_fact.pythons,
                platforms=torch_fact.platforms,
                tier=int(torch_fact.tier),
                citations=(torch_fact.source.citation(),),
                sources=(torch_fact.source,),
            )
        )
    for wheel_fact in store.wheels:
        if wheel_fact.yanked:
            continue
        result.setdefault(wheel_fact.package, []).append(
            PackageCandidate(
                package=wheel_fact.package,
                version=wheel_fact.version,
                artifact_url=wheel_fact.url,
                artifact_sha256=wheel_fact.sha256,
                cuda_line=wheel_fact.cuda_line,
                torch_version=wheel_fact.torch,
                cxx11abi=wheel_fact.cxx11abi,
                python_tags=(wheel_fact.python,) if wheel_fact.python else (),
                abi_tags=(wheel_fact.abi,) if wheel_fact.abi else (),
                platforms=(wheel_fact.platform,) if wheel_fact.platform else (),
                archs=wheel_fact.archs,
                tier=int(wheel_fact.tier),
                citations=(wheel_fact.source.citation(),),
                sources=(wheel_fact.source,),
            )
        )

    # Compatibility tuples also provide admissible versions for ordinary PyPI
    # packages such as torchvision and torchaudio. They do not create synthetic
    # torch builds, because a torch version without a CUDA build/index is unsafe.
    for coupling_fact in store.couplings:
        for package, version in coupling_fact.version_map.items():
            if package == "torch":
                continue
            result.setdefault(package, []).append(
                PackageCandidate(
                    package=package,
                    version=version,
                    tier=int(coupling_fact.tier),
                    citations=(coupling_fact.source.citation(),),
                    sources=(coupling_fact.source,),
                )
            )
    return {name: _merge_candidates(values) for name, values in result.items()}


def _exact_pin(requirement: Requirement) -> str | None:
    specs = tuple(requirement.specifier)
    if len(specs) == 1 and specs[0].operator in {"==", "==="} and "*" not in specs[0].version:
        try:
            return Version(specs[0].version).public
        except InvalidVersion:
            return None
    return None


def _source_candidates(
    package: str,
    requirement: Requirement,
    store: MatrixStore,
    existing: Sequence[PackageCandidate],
) -> tuple[PackageCandidate, ...]:
    facts = store.source_builds_for(package)
    if not facts:
        return ()
    versions = {candidate.version for candidate in existing}
    exact = _exact_pin(requirement)
    if exact:
        versions.add(exact)
    candidates: list[PackageCandidate] = []
    for fact in facts:
        supported = SpecifierSet(fact.version_spec) if fact.version_spec else SpecifierSet()
        for version in versions:
            parsed = Version(version)
            if parsed not in requirement.specifier or parsed not in supported:
                continue
            candidates.append(_candidate_from_source_build(package, version, fact))
    return _merge_candidates(candidates)


def _local_cuda_pin(requirement: Requirement) -> str | None:
    specs = tuple(requirement.specifier)
    if len(specs) != 1 or specs[0].operator not in {"==", "==="}:
        return None
    try:
        local = Version(specs[0].version).local
    except InvalidVersion:
        return None
    match = re.fullmatch(r"cu(\d{2,3})", local or "")
    if not match:
        return None
    digits = match.group(1)
    if len(digits) == 2:
        return f"{digits[0]}.{digits[1]}"
    return f"{digits[:-1]}.{digits[-1]}"


def _candidate_from_source_build(
    package: str, version: str, fact: SourceBuildFact
) -> PackageCandidate:
    return PackageCandidate(
        package=package,
        version=version,
        tier=int(fact.tier),
        citations=(fact.source.citation(),),
        sources=(fact.source,),
        source_build=True,
        source_requirements=fact.requirements,
        source_flags=fact.flags,
        estimate_minutes=fact.estimate_minutes,
        ram_gb_per_job=fact.ram_gb_per_job,
    )


def _has_compatibility_axes(candidate: PackageCandidate) -> bool:
    """Reject GPU artifacts whose critical build axes are entirely unknown."""

    if candidate.package not in _NATIVE_GPU_PACKAGES or candidate.source_build:
        return True
    if candidate.cuda_line is None and candidate.cuda_exact is None:
        return False
    return not (candidate.package in _TORCH_NATIVE_EXTENSIONS and candidate.torch_version is None)


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", value)
    return tuple(int(part) for part in parts)


def _public_version(value: str) -> Version:
    return Version(Version(value).public)


def _python_matches(
    tags: tuple[str, ...],
    abi_tags: tuple[str, ...],
    python_version: str | None,
    python_abi_tag: str | None = None,
) -> bool:
    if not tags or not python_version:
        return True
    release = _version_tuple(python_version)[:2]
    if len(release) < 2:
        return True
    free_threaded = bool(python_abi_tag and re.fullmatch(r"(?:cp|pp)\d+t", python_abi_tag))
    for tag in tags:
        literal = re.fullmatch(r"(\d+)\.(\d+)(t?)", tag)
        if literal:
            tagged = (int(literal.group(1)), int(literal.group(2)))
            if tagged == release and bool(literal.group(3)) is free_threaded:
                return True
        elif tag.startswith(("cp", "pp")):
            digits = re.fullmatch(r"(cp|pp)(\d)(\d{1,2})(t?)", tag)
            if digits:
                if python_abi_tag and not python_abi_tag.startswith(digits.group(1)):
                    continue
                tagged = (int(digits.group(2)), int(digits.group(3)))
                if bool(digits.group(4)) is not free_threaded:
                    continue
                if tagged == release:
                    return True
                if (
                    not free_threaded
                    and "abi3" in abi_tags
                    and tagged[0] == release[0]
                    and tagged <= release
                ):
                    return True
        elif tag.startswith("py") and tag[2:].isdigit():
            py_digits = tag[2:]
            if len(py_digits) == 1 and int(py_digits) == release[0]:
                return True
            tagged = (int(py_digits[0]), int(py_digits[1:]))
            if tagged[0] == release[0] and tagged <= release:
                return True
    return False


def _normal_arch(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.lower()
    if lowered in {"amd64", "x64", "x86-64"}:
        return "x86_64"
    if lowered in {"arm64", "aarch64"}:
        return "aarch64"
    return lowered


def _platform_matches(tags: tuple[str, ...], profile: MachineProfile) -> bool:
    if not tags or not profile.os:
        return True
    system = profile.os.lower()
    architecture = _normal_arch(profile.architecture)
    for tag in tags:
        lowered = tag.lower()
        if lowered == "any":
            return True
        if system.startswith("linux") and not (
            lowered.startswith("linux_") or lowered.startswith("manylinux")
        ):
            continue
        if system.startswith("win") and not lowered.startswith("win_"):
            continue
        if system.startswith(("darwin", "mac")) and not lowered.startswith("macosx_"):
            continue
        if architecture:
            architecture_tokens = {
                "x86_64": ("x86_64", "amd64", "universal2"),
                "aarch64": ("aarch64", "arm64", "universal2"),
            }.get(architecture, (architecture,))
            if not any(token in lowered for token in architecture_tokens):
                continue
        manylinux = re.match(r"manylinux_(\d+)_(\d+)_", lowered)
        if manylinux and profile.platform.glibc_version:
            required = (int(manylinux.group(1)), int(manylinux.group(2)))
            if _version_tuple(profile.platform.glibc_version)[:2] < required:
                continue
        return True
    return False


def _driver_supports(
    candidate: PackageCandidate, profile: MachineProfile, store: MatrixStore
) -> bool:
    cuda = candidate.cuda_exact or candidate.cuda_line
    if not cuda:
        return True
    maximum = profile.max_cuda_runtime
    if maximum:
        chosen = _version_tuple(cuda)
        supported = _version_tuple(maximum)
        if chosen and supported and chosen[0] > supported[0]:
            return False
    if not profile.driver_version:
        return True
    platform = "windows" if profile.platform.is_wsl else (profile.os or "linux").lower()
    platform = "windows" if platform.startswith("win") else "linux"
    minimum = store.driver_minimum(cuda, platform)
    return minimum is None or _version_tuple(profile.driver_version) >= _version_tuple(minimum)


def _architecture_supports(
    candidate: PackageCandidate, profile: MachineProfile, store: MatrixStore
) -> bool:
    if (
        candidate.archs
        and profile.compute_capabilities
        and not set(profile.compute_capabilities).issubset(candidate.archs)
    ):
        return False
    cuda = candidate.cuda_exact or candidate.cuda_line
    if not cuda:
        return True
    for present in profile.compute_capabilities:
        for fact in store.architectures:
            if fact.arch != present:
                continue
            chosen = _version_tuple(cuda)
            if fact.cuda_min:
                minimum = _version_tuple(fact.cuda_min)
                if chosen and minimum and chosen[0] < minimum[0]:
                    return False
                if len(chosen) >= len(minimum) and chosen[: len(minimum)] < minimum:
                    return False
            if fact.cuda_max:
                maximum = _version_tuple(fact.cuda_max)
                if len(maximum) == 1:
                    if chosen and chosen[0] > maximum[0]:
                        return False
                elif len(chosen) >= len(maximum) and chosen[: len(maximum)] > maximum:
                    return False
    return True


def _torch_release_matches(required: str, actual: str) -> bool:
    required_release = Version(required).release
    actual_release = Version(actual).release
    return actual_release[: len(required_release)] == required_release


def _candidate_mapping(
    candidate: PackageCandidate,
    torch: PackageCandidate | None = None,
    profile: MachineProfile | None = None,
) -> dict[str, Any]:
    python_tags = list(candidate.python_tags)
    platform_tags = list(candidate.platforms)
    if profile is not None:
        if profile.platform.python_abi_tag:
            python_tags.append(profile.platform.python_abi_tag)
        if profile.python_version:
            python_tags.append(profile.python_version)
        if profile.platform.manylinux_tag:
            platform_tags.append(profile.platform.manylinux_tag)
        if profile.os and profile.architecture:
            platform_tags.append(f"{profile.os.lower()}_{_normal_arch(profile.architecture)}")

    def scoped_values(values: Sequence[str]) -> str | tuple[str, ...] | None:
        unique = tuple(dict.fromkeys(values))
        if not unique:
            return None
        return unique[0] if len(unique) == 1 else unique

    return {
        key: value
        for key, value in {
            "package": candidate.package,
            "version": candidate.version,
            "torch": torch.version if torch else candidate.torch_version,
            "cuda_line": candidate.cuda_line,
            "cxx11abi": candidate.cxx11abi,
            "python": scoped_values(python_tags),
            "platform": scoped_values(platform_tags),
            "source_build": candidate.source_build,
        }.items()
        if value is not None
    }


def _requested_names(requirements: Sequence[Requirement]) -> tuple[str, ...]:
    return tuple(canonicalize_name(requirement.name) for requirement in requirements)


def _needed_packages(
    requested: tuple[str, ...],
    candidates: Mapping[str, tuple[PackageCandidate, ...]],
    store: MatrixStore,
    *,
    allow_source_build: bool,
) -> tuple[str, ...]:
    needed = set(requested)
    for package in requested:
        if any(candidate.torch_version for candidate in candidates.get(package, ())):
            needed.add("torch")
        if package != "torch" and any(
            package in fact.packages and "torch" in fact.packages for fact in store.couplings
        ):
            needed.add("torch")
        if allow_source_build:
            for fact in store.source_builds_for(package):
                if any(
                    _is_package_requirement(requirement, "torch")
                    for requirement in fact.requirements
                ):
                    needed.add("torch")
    return tuple(sorted(needed))


def _chosen(assignment: Mapping[str, Any], package: str) -> PackageCandidate:
    return cast(PackageCandidate, assignment[package])


def _parsed_requirement(value: str) -> Requirement | None:
    try:
        return Requirement(value)
    except InvalidRequirement:
        return None


def _is_package_requirement(value: str, package: str) -> bool:
    requirement = _parsed_requirement(value)
    return requirement is not None and canonicalize_name(requirement.name) == package


def _toolkit_matches(profile: MachineProfile, specifier: str) -> bool:
    if profile.toolkit is None:
        return False
    try:
        return Version(profile.toolkit.version) in SpecifierSet(specifier)
    except InvalidVersion:
        return False


def _source_environment_accepts(
    assignment: Mapping[str, Any], *, package: str, profile: MachineProfile
) -> bool:
    candidate = _chosen(assignment, package)
    if not candidate.source_build:
        return True
    for raw in candidate.source_requirements:
        requirement = raw.strip()
        lowered = requirement.lower()
        if lowered in {"linux", "windows", "darwin", "macos"}:
            expected = "darwin" if lowered == "macos" else lowered
            if profile.os != expected:
                return False
            continue
        toolkit = re.fullmatch(r"(?:cuda\s+toolkit|nvcc)\s*(.*)", lowered)
        if toolkit:
            specifier = toolkit.group(1).strip()
            if not _toolkit_matches(profile, specifier or ">=0"):
                return False
    return True


def _accelerator_accepts(
    assignment: Mapping[str, Any], *, package: str, profile: MachineProfile
) -> bool:
    explicit_cpu = any(issue.code == "explicit-cpu-target" for issue in profile.issues)
    candidate = _chosen(assignment, package)
    return not explicit_cpu or (candidate.cuda_line is None and candidate.cuda_exact is None)


def _source_torch_accepts(assignment: Mapping[str, Any], *, package: str) -> bool:
    candidate = _chosen(assignment, package)
    if not candidate.source_build:
        return True
    torch = _chosen(assignment, "torch")
    for raw in candidate.source_requirements:
        requirement = _parsed_requirement(raw)
        if requirement is None or canonicalize_name(requirement.name) != "torch":
            continue
        if Version(torch.version) not in requirement.specifier:
            return False
    return True


def _pin_accepts(assignment: Mapping[str, Any], *, package: str, requirement: Requirement) -> bool:
    return _requirement_accepts(_chosen(assignment, package), requirement)


def _requirement_accepts(candidate: PackageCandidate, requirement: Requirement) -> bool:
    exact = _exact_pin(requirement)
    if exact is not None:
        if _public_version(candidate.version) != Version(exact):
            return False
        requested_cuda = _local_cuda_pin(requirement)
        if requested_cuda is None:
            return True
        candidate_cuda = candidate.cuda_exact or candidate.cuda_line
        if candidate_cuda is None:
            return False
        return _version_tuple(candidate_cuda)[:2] == _version_tuple(requested_cuda)[:2]
    return Version(candidate.version) in requirement.specifier


def _python_accepts(
    assignment: Mapping[str, Any], *, package: str, profile: MachineProfile
) -> bool:
    candidate = _chosen(assignment, package)
    return _python_matches(
        candidate.python_tags,
        candidate.abi_tags,
        profile.python_version,
        profile.platform.python_abi_tag,
    )


def _platform_accepts(
    assignment: Mapping[str, Any], *, package: str, profile: MachineProfile
) -> bool:
    candidate = _chosen(assignment, package)
    if candidate.cuda_line is not None or candidate.cuda_exact is not None:
        if profile.os is None or not profile.os.lower().startswith("linux"):
            return False
        if _normal_arch(profile.architecture) != "x86_64":
            return False
    return _platform_matches(candidate.platforms, profile)


def _driver_accepts(
    assignment: Mapping[str, Any],
    *,
    package: str,
    profile: MachineProfile,
    store: MatrixStore,
) -> bool:
    return _driver_supports(_chosen(assignment, package), profile, store)


def _architecture_accepts(
    assignment: Mapping[str, Any],
    *,
    package: str,
    profile: MachineProfile,
    store: MatrixStore,
) -> bool:
    return _architecture_supports(_chosen(assignment, package), profile, store)


def _not_broken_accepts(
    assignment: Mapping[str, Any],
    *,
    package: str,
    profile: MachineProfile,
    store: MatrixStore,
) -> bool:
    return not store.known_broken_for(
        _candidate_mapping(_chosen(assignment, package), profile=profile)
    )


def _torch_version_accepts(assignment: Mapping[str, Any], *, package: str) -> bool:
    candidate = _chosen(assignment, package)
    torch = _chosen(assignment, "torch")
    return candidate.torch_version is None or _torch_release_matches(
        candidate.torch_version, torch.version
    )


def _cuda_line_accepts(assignment: Mapping[str, Any], *, package: str) -> bool:
    candidate = _chosen(assignment, package)
    torch = _chosen(assignment, "torch")
    return (
        candidate.cuda_line is None
        or torch.cuda_line is None
        or cuda_lines_compatible(candidate.cuda_line, torch.cuda_line)
    )


def _cxx11abi_accepts(assignment: Mapping[str, Any], *, package: str) -> bool:
    candidate = _chosen(assignment, package)
    torch = _chosen(assignment, "torch")
    return (
        candidate.cxx11abi is None or torch.cxx11abi is None or candidate.cxx11abi is torch.cxx11abi
    )


def _not_broken_pair_accepts(
    assignment: Mapping[str, Any],
    *,
    package: str,
    profile: MachineProfile,
    store: MatrixStore,
) -> bool:
    return not store.known_broken_for(
        _candidate_mapping(
            _chosen(assignment, package),
            _chosen(assignment, "torch"),
            profile,
        )
    )


def build_csp(
    requirements: Sequence[Requirement],
    profile: MachineProfile,
    store: MatrixStore,
    *,
    allow_source_build: bool = False,
) -> tuple[CSP | None, tuple[str, ...], dict[str, tuple[PackageCandidate, ...]]]:
    all_candidates = _base_candidates(store)
    by_requirement: dict[str, Requirement] = {
        str(canonicalize_name(item.name)): item for item in requirements
    }
    requested = _requested_names(requirements)
    needed = _needed_packages(
        requested,
        all_candidates,
        store,
        allow_source_build=allow_source_build,
    )
    domains: dict[str, tuple[PackageCandidate, ...]] = {}
    for package in needed:
        candidates = all_candidates.get(package, ())
        requirement = by_requirement.get(package, Requirement(package))
        if allow_source_build:
            candidates = _merge_candidates(
                (*candidates, *_source_candidates(package, requirement, store, candidates))
            )
        domains[package] = tuple(
            candidate for candidate in candidates if _has_compatibility_axes(candidate)
        )
    missing = tuple(
        sorted(
            {
                *(package for package, values in domains.items() if not values),
                *(
                    package
                    for package, requirement in by_requirement.items()
                    if domains.get(package)
                    and not any(
                        _requirement_accepts(candidate, requirement)
                        for candidate in domains[package]
                    )
                ),
            }
        )
    )
    if missing:
        return None, missing, domains

    evidence_domains = {
        package: tuple(
            candidate
            for candidate in candidates
            if package not in by_requirement
            or _requirement_accepts(candidate, by_requirement[package])
        )
        for package, candidates in domains.items()
    }
    constraints: list[Constraint] = []
    for package, requirement in by_requirement.items():
        constraints.append(
            Constraint(
                key=f"user-pin:{package}",
                variables=(package,),
                predicate=partial(
                    _pin_accepts,
                    package=package,
                    requirement=requirement,
                ),
                summary=f"you requested {requirement}",
                kind="user-pin",
            )
        )

    for package in needed:
        candidate_sources = tuple(
            dict.fromkeys(
                source for candidate in evidence_domains[package] for source in candidate.sources
            )
        )
        constraints.extend(
            (
                Constraint(
                    key=f"python:{package}",
                    variables=(package,),
                    predicate=partial(_python_accepts, package=package, profile=profile),
                    summary=f"{package} must publish a wheel for Python {profile.python_version or 'unknown'}",
                    sources=candidate_sources,
                    kind="python",
                ),
                Constraint(
                    key=f"accelerator:{package}",
                    variables=(package,),
                    predicate=partial(
                        _accelerator_accepts,
                        package=package,
                        profile=profile,
                    ),
                    summary=f"{package}'s CUDA build cannot target an explicit CPU-only machine",
                    kind="accelerator",
                ),
                Constraint(
                    key=f"platform:{package}",
                    variables=(package,),
                    predicate=partial(_platform_accepts, package=package, profile=profile),
                    summary=f"{package} must publish a wheel for this OS, architecture, and glibc",
                    sources=candidate_sources,
                    kind="platform",
                ),
                Constraint(
                    key=f"source-environment:{package}",
                    variables=(package,),
                    predicate=partial(
                        _source_environment_accepts,
                        package=package,
                        profile=profile,
                    ),
                    summary=(
                        f"{package}'s source build requires its documented operating system "
                        "and CUDA toolkit"
                    ),
                    sources=tuple(fact.source for fact in store.source_builds_for(package)),
                    kind="source-environment",
                ),
                Constraint(
                    key=f"driver:{package}",
                    variables=(package,),
                    predicate=partial(
                        _driver_accepts,
                        package=package,
                        profile=profile,
                        store=store,
                    ),
                    summary=f"the NVIDIA driver must support {package}'s CUDA runtime",
                    sources=tuple(fact.source for fact in store.constraints),
                    kind="driver",
                ),
                Constraint(
                    key=f"architecture:{package}",
                    variables=(package,),
                    predicate=partial(
                        _architecture_accepts,
                        package=package,
                        profile=profile,
                        store=store,
                    ),
                    summary=f"{package}'s CUDA build must support every detected GPU architecture",
                    sources=tuple(fact.source for fact in store.architectures),
                    kind="architecture",
                ),
                Constraint(
                    key=f"known-broken:{package}",
                    variables=(package,),
                    predicate=partial(
                        _not_broken_accepts,
                        package=package,
                        profile=profile,
                        store=store,
                    ),
                    summary=f"{package} must not match a recorded broken combination",
                    sources=tuple(fact.source for fact in store.known_broken),
                    kind="known-broken",
                ),
            )
        )

    if "torch" in domains:
        for package in needed:
            if package == "torch":
                continue
            variables = (package, "torch")
            constraints.extend(
                (
                    Constraint(
                        key=f"torch-version:{package}",
                        variables=variables,
                        predicate=partial(_torch_version_accepts, package=package),
                        summary=f"{package}'s native wheel must match torch's major/minor release",
                        sources=tuple(
                            dict.fromkeys(
                                source
                                for candidate in evidence_domains[package]
                                for source in candidate.sources
                            )
                        ),
                        kind="torch-version",
                    ),
                    Constraint(
                        key=f"source-torch:{package}",
                        variables=variables,
                        predicate=partial(_source_torch_accepts, package=package),
                        summary=f"{package}'s source build requires a supported torch version",
                        sources=tuple(fact.source for fact in store.source_builds_for(package)),
                        kind="source-torch",
                    ),
                    Constraint(
                        key=f"cuda-line:{package}",
                        variables=variables,
                        predicate=partial(_cuda_line_accepts, package=package),
                        summary=f"{package} and torch must use compatible CUDA lines",
                        sources=tuple(
                            dict.fromkeys(
                                source
                                for name in variables
                                for candidate in evidence_domains[name]
                                for source in candidate.sources
                            )
                        ),
                        kind="cuda-line",
                    ),
                    Constraint(
                        key=f"cxx11abi:{package}",
                        variables=variables,
                        predicate=partial(_cxx11abi_accepts, package=package),
                        summary=f"{package} and torch must use the same C++11 ABI",
                        sources=tuple(
                            dict.fromkeys(
                                source
                                for name in variables
                                for candidate in evidence_domains[name]
                                for source in candidate.sources
                            )
                        ),
                        kind="cxx11abi",
                    ),
                    Constraint(
                        key=f"known-broken-pair:{package}",
                        variables=variables,
                        predicate=partial(
                            _not_broken_pair_accepts,
                            package=package,
                            profile=profile,
                            store=store,
                        ),
                        summary=f"{package} and torch must not match a recorded broken edge",
                        sources=tuple(fact.source for fact in store.known_broken),
                        kind="known-broken",
                    ),
                )
            )

    for left_index, left in enumerate(needed):
        for right in needed[left_index + 1 :]:
            related = tuple(
                fact for fact in store.couplings if {left, right}.issubset(fact.packages)
            )
            if not related:
                continue

            def coupling_accepts(
                assignment: Mapping[str, PackageCandidate],
                *,
                left: str = left,
                right: str = right,
                related: tuple[Any, ...] = related,
            ) -> bool:
                left_version = Version(assignment[left].version)
                right_version = Version(assignment[right].version)
                for fact in related:
                    if fact.kind == "exact-version-lockstep" and left_version == right_version:
                        return True
                    versions = fact.version_map
                    if (
                        fact.kind == "compatible-release-set"
                        and left in versions
                        and right in versions
                        and left_version == Version(versions[left])
                        and right_version == Version(versions[right])
                    ):
                        return True
                return False

            constraints.append(
                Constraint(
                    key=f"coupling:{left}:{right}",
                    variables=(left, right),
                    predicate=coupling_accepts,
                    summary=f"{left} and {right} must use an upstream-published compatibility tuple",
                    sources=tuple(fact.source for fact in related),
                    kind="coupling",
                )
            )
    return CSP(domains=domains, constraints=tuple(constraints)), (), domains


def _score(
    assignment: Mapping[str, PackageCandidate],
    preference: str,
    profile: MachineProfile,
    store: MatrixStore,
) -> tuple[Any, ...]:
    ordered = tuple(assignment[name] for name in sorted(assignment))
    tiers = tuple(candidate.tier for candidate in ordered)
    versions = tuple(candidate.parsed_version for candidate in ordered)
    source_builds = sum(candidate.source_build for candidate in ordered)
    stable = sum(not version.is_prerelease and not version.is_devrelease for version in versions)
    installed = {package.normalized_name: package for package in profile.installed.packages}

    def matches_installed(candidate: PackageCandidate) -> bool:
        package = installed.get(canonicalize_name(candidate.package))
        if package is None or _public_version(package.version) != _public_version(
            candidate.version
        ):
            return False
        actual_cuda = package.cuda_line
        actual_abi = package.cxx11_abi
        if candidate.package == "torch" and profile.torch is not None:
            actual_cuda = profile.torch.cuda_version or actual_cuda
            actual_abi = profile.torch.cxx11_abi
        if (
            candidate.cuda_line
            and actual_cuda
            and not cuda_lines_compatible(candidate.cuda_line, actual_cuda)
        ):
            return False
        if (
            candidate.cxx11abi is not None
            and actual_abi is not None
            and candidate.cxx11abi is not actual_abi
        ):
            return False
        if (
            candidate.torch_version
            and package.torch_version
            and not _torch_release_matches(candidate.torch_version, package.torch_version)
        ):
            return False
        return not (
            package.source_build is not None and package.source_build is not candidate.source_build
        )

    unchanged = sum(matches_installed(candidate) for candidate in ordered)
    all_tiers = (*tiers, *_plan_constraint_tiers(assignment, profile, store))
    common = (min(all_tiers, default=0), sum(all_tiers), -source_builds, versions)
    if preference == "verified":
        return common
    if preference == "newest":
        return (versions, *common)
    if preference == "stable":
        return (stable, *common)
    if preference == "minimal-change":
        return (unchanged, *common)
    raise UserInputError(f"unknown preference: {preference}")


def _source_environment(
    candidate: PackageCandidate, profile: MachineProfile
) -> tuple[tuple[str, str], ...]:
    if not candidate.source_build:
        return ()
    result: list[tuple[str, str]] = []
    if profile.toolkit is not None and profile.toolkit.path:
        cuda_home = _cuda_home_from_toolkit_path(profile.toolkit.path)
        if cuda_home is not None:
            result.append(("CUDA_HOME", cuda_home))
    # MachineProfile intentionally does not conflate GPU VRAM with host RAM.
    # When a per-job requirement is known, one compiler job is the only safe
    # deterministic default without probing mutable host resources.
    max_jobs = "1" if candidate.ram_gb_per_job is not None else "4"
    result.append(("MAX_JOBS", max_jobs))
    if profile.compute_capabilities:
        architectures = ";".join(
            f"{arch[3:-1]}.{arch[-1]}" if arch.startswith("sm_") else arch
            for arch in profile.compute_capabilities
        )
        result.append(("TORCH_CUDA_ARCH_LIST", architectures))
    return tuple(result)


def _cuda_home_from_toolkit_path(value: str) -> str | None:
    """Turn a toolkit root or nvcc executable path into CUDA_HOME."""

    candidate = value.strip()
    local_path = Path(candidate)
    if local_path.is_file():
        candidate = str(local_path.resolve())
    windows_path = bool(re.match(r"^[A-Za-z]:[\\/]", candidate)) or "\\" in candidate
    path = PureWindowsPath(candidate) if windows_path else PurePosixPath(candidate)
    if not path.is_absolute():
        return None
    if path.name.casefold() in {"nvcc", "nvcc.exe"}:
        path = path.parent.parent if path.parent.name.casefold() == "bin" else path.parent
    return str(path)


def _python_build_requirements(candidate: PackageCandidate) -> tuple[str, ...]:
    result: list[str] = []
    excluded = {"cuda", "cuda-toolkit", "linux", "nvcc", "torch"}
    for raw in candidate.source_requirements:
        try:
            requirement = Requirement(raw)
        except InvalidRequirement:
            continue
        if canonicalize_name(requirement.name) in excluded:
            continue
        result.append(str(requirement))
    return tuple(dict.fromkeys(result))


def _cuda_fact_applies(fact_runtime: str, candidate_runtime: str) -> bool:
    fact_parts = _version_tuple(fact_runtime)
    candidate_parts = _version_tuple(candidate_runtime)
    if not fact_parts or not candidate_parts or fact_parts[0] != candidate_parts[0]:
        return False
    if fact_runtime.endswith(".x") or len(fact_parts) == 1:
        return True
    return candidate_parts[: len(fact_parts)] == fact_parts


def _plan_constraint_tiers(
    assignment: Mapping[str, PackageCandidate],
    profile: MachineProfile,
    store: MatrixStore,
) -> tuple[int, ...]:
    """Return evidence tiers for matrix facts that constrain the selected plan."""

    tiers: set[int] = set()
    selected_cuda = tuple(
        cuda
        for candidate in assignment.values()
        if (cuda := candidate.cuda_exact or candidate.cuda_line) is not None
    )
    if profile.driver_version:
        for driver_fact in store.constraints:
            if driver_fact.compatibility == "minor-compatible" and any(
                _cuda_fact_applies(driver_fact.cuda_runtime, cuda) for cuda in selected_cuda
            ):
                tiers.add(int(driver_fact.tier))
    if profile.compute_capabilities and selected_cuda:
        for architecture_fact in store.architectures:
            if architecture_fact.arch in profile.compute_capabilities:
                tiers.add(int(architecture_fact.tier))
    for coupling_fact in store.couplings:
        selected = tuple(package for package in coupling_fact.packages if package in assignment)
        if len(selected) < 2:
            continue
        if coupling_fact.kind == "exact-version-lockstep":
            releases = {_public_version(assignment[package].version) for package in selected}
            if len(releases) == 1:
                tiers.add(int(coupling_fact.tier))
        elif all(
            package in coupling_fact.version_map
            and _public_version(assignment[package].version)
            == _public_version(coupling_fact.version_map[package])
            for package in selected
        ):
            tiers.add(int(coupling_fact.tier))
    return tuple(sorted(tiers))


def _make_plan(
    requested: Sequence[str],
    assignment: Mapping[str, PackageCandidate],
    profile: MachineProfile,
    store: MatrixStore,
    preference: str,
) -> InstallPlan:
    warnings: list[str] = []
    steps: list[InstallStep] = []
    constraint_tiers = _plan_constraint_tiers(assignment, profile, store)
    if 0 in constraint_tiers or any(candidate.tier == 0 for candidate in assignment.values()):
        warnings.append(
            "selected versions are metadata-backed; use --execute to install and verify them on this machine"
        )
    if profile.gpus and not profile.compute_capabilities:
        warnings.append(
            "GPU compute capability is unknown; architecture compatibility remains unverified"
        )
    torch_candidate = assignment.get("torch")
    for package in sorted(assignment):
        candidate = assignment[package]
        inherited_torch_index = (
            package in {"torchvision", "torchaudio"}
            and torch_candidate is not None
            and any(
                fact.kind == "compatible-release-set"
                and package in fact.packages
                and "torch" in fact.packages
                for fact in store.couplings
            )
        )
        needs_torch = (
            package != "torch"
            and "torch" in assignment
            and (
                candidate.torch_version is not None
                or any(
                    _is_package_requirement(requirement, "torch")
                    for requirement in candidate.source_requirements
                )
                or any(
                    package in fact.packages and "torch" in fact.packages
                    for fact in store.couplings
                )
            )
        )
        flags = candidate.source_flags
        if candidate.source_build and "--no-build-isolation" not in flags:
            flags = (*flags, "--no-build-isolation")
        if candidate.source_build:
            source_guidance = [
                f"roughly {candidate.estimate_minutes} minutes"
                if candidate.estimate_minutes
                else "duration depends on CPU, RAM, and toolkit"
            ]
            if candidate.ram_gb_per_job is not None:
                source_guidance.append(
                    f"~{candidate.ram_gb_per_job:g} GiB RAM per compiler job; MAX_JOBS=1"
                )
            warnings.append(
                f"{package} has no matching wheel and will build from source "
                f"({'; '.join(source_guidance)})"
            )
        if (
            package != "torch"
            and candidate.cxx11abi is not None
            and torch_candidate is not None
            and torch_candidate.cxx11abi is None
        ):
            warnings.append(
                f"torch's C++11 ABI is not established by the available upstream facts; the selected {package} asset assumes cxx11abi {str(candidate.cxx11abi).upper()}"
            )
        if (
            package in {"flash-attn", "vllm", "xformers", "bitsandbytes", "flashinfer-python"}
            and profile.compute_capabilities
            and not candidate.archs
            and not candidate.source_build
        ):
            warnings.append(
                f"{package}'s wheel filename does not establish GPU kernel coverage for {'/'.join(profile.compute_capabilities)}"
            )
        if (
            package in {"vllm", "xformers", "bitsandbytes", "flashinfer-python"}
            and candidate.cuda_line is None
            and candidate.torch_version is None
        ):
            warnings.append(
                f"the recorded {package} artifact has no encoded CUDA/torch coupling; those axes remain unknown"
            )
        inherited_index_url = candidate.index_url
        inherited_cuda_line = candidate.cuda_line
        if inherited_torch_index:
            assert torch_candidate is not None
            inherited_index_url = torch_candidate.index_url
            inherited_cuda_line = torch_candidate.cuda_line
        steps.append(
            InstallStep(
                package=package,
                version=candidate.version,
                artifact_url=candidate.artifact_url,
                artifact_sha256=candidate.artifact_sha256,
                index_url=inherited_index_url,
                dependencies=("torch",) if needs_torch else (),
                build_requirements=_python_build_requirements(candidate),
                environment=_source_environment(candidate, profile),
                flags=flags,
                source_build=candidate.source_build,
                build_estimate=(
                    f"~{candidate.estimate_minutes} min" if candidate.estimate_minutes else None
                ),
                ram_gb_per_job=candidate.ram_gb_per_job,
                tier=candidate.tier,
                provenance=candidate.citations,
                cuda_line=inherited_cuda_line,
                torch_version=candidate.torch_version,
                cxx11_abi=candidate.cxx11abi,
                python_tag=(candidate.python_tags[0] if len(candidate.python_tags) == 1 else None),
                platform_tag=(candidate.platforms[0] if len(candidate.platforms) == 1 else None),
            )
        )
    if profile.max_cuda_runtime:
        for candidate in assignment.values():
            cuda = candidate.cuda_exact or candidate.cuda_line
            if not cuda:
                continue
            chosen = _version_tuple(cuda)
            advertised = _version_tuple(profile.max_cuda_runtime)
            if (
                chosen
                and advertised
                and chosen[0] == advertised[0]
                and len(chosen) > 1
                and len(advertised) > 1
                and chosen[:2] > advertised[:2]
            ):
                warnings.append(
                    f"CUDA {cuda} relies on NVIDIA minor-version compatibility with this driver; PTX or newer-feature code may still require a newer driver"
                )
                break
    target = {
        key: value
        for key, value in {
            "gpu": profile.gpu_name,
            "gpu_count": profile.gpu_count,
            "compute_capability": profile.compute_capability,
            "compute_capabilities": profile.compute_capabilities,
            "driver_version": profile.driver_version,
            "python_version": profile.python_version,
            "platform": profile.os,
            "architecture": profile.architecture,
            "glibc": profile.platform.glibc_version,
            "cxx11abi": profile.cxx11_abi,
            "toolkit_version": profile.cuda_toolkit_version,
            "toolkit_path": profile.toolkit.path if profile.toolkit is not None else None,
            "cuda_runtime": next(
                (
                    candidate.cuda_exact
                    for candidate in assignment.values()
                    if candidate.package == "torch" and candidate.cuda_exact
                ),
                None,
            ),
        }.items()
        if value is not None
    }
    return InstallPlan(
        requested=tuple(requested),
        steps=tuple(steps),
        matrix_version=store.matrix_version,
        matrix_digest=store.digest,
        target=target,
        preference=preference,
        constraint_tiers=constraint_tiers,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _suggestions(
    requirements: Sequence[Requirement],
    domains: Mapping[str, tuple[PackageCandidate, ...]],
    profile: MachineProfile,
    store: MatrixStore,
    allow_source_build: bool,
) -> tuple[str, ...]:
    suggestions: list[str] = []

    def satisfiable(candidate_profile: MachineProfile, *, source_build: bool) -> bool:
        candidate_csp, missing, _ = build_csp(
            requirements,
            candidate_profile,
            store,
            allow_source_build=source_build,
        )
        return not missing and candidate_csp is not None and solve_csp(candidate_csp).satisfiable

    python_versions: set[str] = set()
    for candidates in domains.values():
        for candidate in candidates:
            for tag in candidate.python_tags:
                if re.fullmatch(r"\d+\.\d+", tag):
                    python_versions.add(tag)
                else:
                    match = re.fullmatch(r"cp(\d)(\d{1,2})", tag)
                    if match:
                        python_versions.add(f"{match.group(1)}.{match.group(2)}")
    if profile.python_version and python_versions:
        current = _version_tuple(profile.python_version)[:2]
        alternatives = sorted(
            (item for item in python_versions if _version_tuple(item) != current),
            key=Version,
            reverse=True,
        )
        for alternative in alternatives:
            candidate_profile = profile_from_target(f"python={alternative}", base=profile)
            if satisfiable(candidate_profile, source_build=allow_source_build):
                suggestions.append(f"Use Python {alternative} (a complete solution exists)")
                break
    if (
        not allow_source_build
        and any(store.source_builds_for(canonicalize_name(item.name)) for item in requirements)
        and satisfiable(profile, source_build=True)
    ):
        suggestions.append(
            "Retry with --allow-source-build (the plan will show time and RAM guidance)"
        )
    if allow_source_build and profile.toolkit is None:
        toolkit_versions: set[str] = set()
        needs_toolkit = False
        for item in requirements:
            for fact in store.source_builds_for(canonicalize_name(item.name)):
                for requirement in fact.requirements:
                    if re.fullmatch(
                        r"(?:cuda\s+toolkit|nvcc)(?:\s*>=\s*0)?", requirement.strip().lower()
                    ):
                        needs_toolkit = True
                    match = re.fullmatch(
                        r"(?:cuda\s+toolkit|nvcc)\s*(?:>=|==|~=|>)?\s*(\d+(?:\.\d+){1,2})",
                        requirement.strip().lower(),
                    )
                    if match:
                        needs_toolkit = True
                        toolkit_versions.add(match.group(1))
        if needs_toolkit and not toolkit_versions:
            for candidate in domains.get("torch", ()):
                candidate_cuda = candidate.cuda_exact or candidate.cuda_line
                if candidate_cuda is not None:
                    toolkit_versions.add(candidate_cuda)
        for version in sorted(toolkit_versions, key=Version):
            candidate_profile = profile_from_target(f"nvcc={version}", base=profile)
            if satisfiable(candidate_profile, source_build=True):
                suggestions.append(
                    f"Install CUDA toolkit {version} or include nvcc={version} in --target"
                )
                break
    driver_floors = []
    platform = "windows" if profile.platform.is_wsl else "linux"
    for candidates in domains.values():
        for candidate in candidates:
            cuda = candidate.cuda_exact or candidate.cuda_line
            if cuda:
                floor = store.driver_minimum(cuda, platform)
                if floor:
                    driver_floors.append(floor)
    if profile.driver_version and driver_floors:
        newer = sorted(
            {
                floor
                for floor in driver_floors
                if _version_tuple(floor) > _version_tuple(profile.driver_version)
            },
            key=_version_tuple,
        )
        for floor in newer:
            target_floor = floor if "." in floor else f"{floor}.0"
            candidate_profile = profile_from_target(f"driver={target_floor}", base=profile)
            if satisfiable(candidate_profile, source_build=allow_source_build):
                suggestions.append(f"Update the NVIDIA driver to at least {target_floor}")
                break
    return tuple(suggestions[:3])


def resolve(
    specs: Sequence[str],
    profile: MachineProfile,
    store: MatrixStore,
    *,
    preference: str = "verified",
    allow_source_build: bool = False,
) -> ResolutionOutcome:
    if isinstance(specs, (str, bytes)):
        raise UserInputError("specs must be a sequence of requirement strings")
    requirements = parse_requirements(specs)
    csp, missing, domains = build_csp(
        requirements,
        profile,
        store,
        allow_source_build=allow_source_build,
    )
    if csp is None:
        by_requirement = {
            canonicalize_name(requirement.name): requirement for requirement in requirements
        }
        coverage_gaps = tuple(
            CoverageGap(
                package=package,
                requested=str(by_requirement.get(canonicalize_name(package), Requirement(package))),
                modeled_versions=tuple(
                    sorted(
                        {candidate.version for candidate in domains.get(package, ())},
                        key=Version,
                    )
                ),
                sources=tuple(
                    dict.fromkeys(
                        source
                        for candidate in domains.get(package, ())
                        for source in candidate.sources
                    )
                ),
            )
            for package in missing
        )
        return ResolutionOutcome(
            failure=ResolutionFailure(
                requested=tuple(specs),
                missing_packages=missing,
                coverage_gaps=coverage_gaps,
                suggestions=_suggestions(requirements, domains, profile, store, allow_source_build),
            )
        )
    result = solve_csp(
        csp,
        scorer=lambda assignment: _score(assignment, preference, profile, store),
    )
    if not result.satisfiable:
        return ResolutionOutcome(
            failure=ResolutionFailure(
                requested=tuple(specs),
                core=minimal_unsatisfiable_subset(csp),
                suggestions=_suggestions(requirements, domains, profile, store, allow_source_build),
                explored_nodes=result.explored_nodes,
            )
        )
    assignment = cast(
        dict[str, PackageCandidate],
        {name: value for name, value in result.assignment.items()},
    )
    return ResolutionOutcome(plan=_make_plan(specs, assignment, profile, store, preference))
