"""Independent compatibility checks for an already-installed environment."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from rigsolve.detect import InstalledPackage, MachineProfile
from rigsolve.matrix import MatrixStore, cuda_lines_compatible
from rigsolve.plan.install import InstallPlan
from rigsolve.plan.lockfile import load_lockfile
from rigsolve.solve.resolver import _platform_matches, resolve


@dataclass(frozen=True, slots=True)
class Violation:
    code: str
    packages: tuple[str, ...]
    summary: str
    detail: str = ""
    fix: str | None = None
    citations: tuple[str, ...] = ()
    severity: str = "error"


@dataclass(frozen=True, slots=True)
class CheckReport:
    violations: tuple[Violation, ...]
    repair_plan: InstallPlan | None = None

    @property
    def healthy(self) -> bool:
        return not any(item.severity == "error" for item in self.violations)


def _version(value: str | None) -> Version | None:
    if value is None:
        return None
    try:
        return Version(value)
    except InvalidVersion:
        return None


def _public_version(value: str | None) -> Version | None:
    parsed = _version(value)
    return None if parsed is None else Version(parsed.public)


def _citation(facts: tuple[Any, ...] | list[Any]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(fact.source.citation() for fact in facts))


def _torch_versions_compatible(left: str, right: str) -> bool:
    left_version = _public_version(left)
    right_version = _public_version(right)
    if left_version is None or right_version is None:
        return False
    return left_version.release[:2] == right_version.release[:2]


def _applicable_wheel_citations(
    package: InstalledPackage,
    store: MatrixStore,
    *,
    axis: str,
) -> tuple[str, ...]:
    """Cite only wheel facts that describe the observed installed build.

    A package name alone is not enough evidence for a native-build mismatch:
    release pages commonly contain wheels for several package, CUDA, torch,
    and ABI combinations.  Missing metadata is tolerated for dimensions other
    than the mismatch being explained, but contradictory metadata is not.
    """

    matching: list[Any] = []
    for fact in store.wheels_for(package.normalized_name):
        if _public_version(fact.version) != _public_version(package.version):
            continue
        if (
            package.cuda_line is not None
            and fact.cuda_line is not None
            and not cuda_lines_compatible(package.cuda_line, fact.cuda_line)
        ):
            continue
        if (
            package.torch_version is not None
            and fact.torch is not None
            and not _torch_versions_compatible(package.torch_version, fact.torch)
        ):
            continue
        if (
            package.cxx11_abi is not None
            and fact.cxx11abi is not None
            and package.cxx11_abi is not fact.cxx11abi
        ):
            continue

        axis_matches = {
            "cuda": (
                package.cuda_line is not None
                and fact.cuda_line is not None
                and cuda_lines_compatible(package.cuda_line, fact.cuda_line)
            ),
            "torch": (
                package.torch_version is not None
                and fact.torch is not None
                and _torch_versions_compatible(package.torch_version, fact.torch)
            ),
            "cxx11abi": (
                package.cxx11_abi is not None
                and fact.cxx11abi is not None
                and package.cxx11_abi is fact.cxx11abi
            ),
        }
        if axis_matches[axis]:
            matching.append(fact)
    return _citation(matching)


def _package_assignment(
    package: InstalledPackage,
    torch_version: str | None,
    profile: MachineProfile,
) -> dict[str, Any]:
    python_tags: list[str] = []
    platform_tags: list[str] = []
    for wheel_tag in package.wheel_tags:
        parts = wheel_tag.split("-", 2)
        if len(parts) == 3:
            python_tags.extend(parts[0].split("."))
            platform_tags.extend(parts[2].split("."))
    if profile.platform.python_abi_tag:
        python_tags.append(profile.platform.python_abi_tag)
    if profile.platform.manylinux_tag:
        platform_tags.append(profile.platform.manylinux_tag)
    if profile.os and profile.architecture:
        platform_tags.append(
            f"{profile.os.lower()}_{_normalise_architecture(profile.architecture)}"
        )
    return {
        key: value
        for key, value in {
            "package": package.normalized_name,
            "version": package.version,
            "cuda_line": package.cuda_line,
            "torch": package.torch_version or torch_version,
            "cxx11abi": package.cxx11_abi,
            "python": tuple(dict.fromkeys(python_tags)) or None,
            "platform": tuple(dict.fromkeys(platform_tags)) or None,
            "source_build": package.source_build,
        }.items()
        if value is not None
    }


def _normalise_architecture(value: str) -> str:
    aliases = {"amd64": "x86_64", "x64": "x86_64", "arm64": "aarch64"}
    return aliases.get(value.lower(), value.lower())


def _target_lockfile_violations(profile: MachineProfile, plan: InstallPlan) -> list[Violation]:
    result: list[Violation] = []
    target = plan.target
    unknown: list[str] = []

    expected_python = target.get("python_version")
    if expected_python:
        actual_python = _version(profile.python_version)
        expected_python_version = _version(str(expected_python))
        if actual_python is None:
            unknown.append("Python version")
        elif (
            expected_python_version is not None
            and actual_python.release[:2] != expected_python_version.release[:2]
        ):
            result.append(
                Violation(
                    code="lock-target-python",
                    packages=(),
                    summary=(
                        f"Python {profile.python_version} does not match the lockfile target "
                        f"{expected_python}"
                    ),
                    fix=f"use Python {expected_python} or regenerate the lockfile",
                )
            )

    expected_platform = target.get("platform")
    if expected_platform:
        actual_platform = (profile.os or "").lower()
        expected_platform_name = str(expected_platform).lower()
        if not actual_platform:
            unknown.append("operating system")
        elif actual_platform != expected_platform_name and not expected_platform_name.startswith(
            f"{actual_platform}_"
        ):
            result.append(
                Violation(
                    code="lock-target-platform",
                    packages=(),
                    summary=f"platform {profile.os} does not match the lockfile target {expected_platform}",
                    fix="regenerate the lockfile for this operating system",
                )
            )

    expected_architecture = target.get("architecture")
    if expected_architecture:
        if not profile.architecture:
            unknown.append("CPU architecture")
        elif _normalise_architecture(profile.architecture) != _normalise_architecture(
            str(expected_architecture)
        ):
            result.append(
                Violation(
                    code="lock-target-architecture",
                    packages=(),
                    summary=(
                        f"architecture {profile.architecture} does not match the lockfile target "
                        f"{expected_architecture}"
                    ),
                    fix="regenerate the lockfile for this architecture",
                )
            )

    expected_compute = target.get("compute_capability")
    if expected_compute:
        if not profile.compute_capabilities:
            unknown.append("GPU compute capability")
        elif str(expected_compute) not in profile.compute_capabilities:
            result.append(
                Violation(
                    code="lock-target-gpu-architecture",
                    packages=(),
                    summary=(
                        f"GPU architecture {'/'.join(profile.compute_capabilities)} does not match "
                        f"the lockfile target {expected_compute}"
                    ),
                    fix="re-solve for this GPU architecture",
                )
            )

    expected_computes = target.get("compute_capabilities")
    if isinstance(expected_computes, (list, tuple)):
        expected_set = {str(value) for value in expected_computes}
        actual_set = set(profile.compute_capabilities)
        if not actual_set and expected_set:
            unknown.append("GPU compute capabilities")
        elif actual_set != expected_set:
            result.append(
                Violation(
                    code="lock-target-gpu-architectures",
                    packages=(),
                    summary=(
                        f"GPU architectures {sorted(actual_set)} do not match the lockfile "
                        f"target {sorted(expected_set)}"
                    ),
                    fix="re-solve for the complete set of GPU architectures",
                )
            )

    expected_gpu_count = target.get("gpu_count")
    if isinstance(expected_gpu_count, int) and profile.gpu_count != expected_gpu_count:
        result.append(
            Violation(
                code="lock-target-gpu-count",
                packages=(),
                summary=(
                    f"GPU count {profile.gpu_count} does not match the lockfile target "
                    f"{expected_gpu_count}"
                ),
                fix="re-solve for the current GPU inventory",
            )
        )

    expected_glibc = target.get("glibc")
    if expected_glibc:
        actual_glibc = _version(profile.platform.glibc_version)
        expected_glibc_version = _version(str(expected_glibc))
        if actual_glibc is None:
            unknown.append("glibc version")
        elif expected_glibc_version is not None and actual_glibc < expected_glibc_version:
            result.append(
                Violation(
                    code="lock-target-glibc",
                    packages=(),
                    summary=(
                        f"glibc {profile.platform.glibc_version} is older than the lockfile target "
                        f"{expected_glibc}"
                    ),
                    fix="use a compatible container/host or regenerate the lockfile",
                )
            )

    for key, actual_value, label in (
        ("gpu", profile.gpu_name, "GPU model"),
        ("driver_version", profile.driver_version, "NVIDIA driver"),
    ):
        expected_value = target.get(key)
        if (
            expected_value
            and actual_value
            and str(expected_value).casefold() != str(actual_value).casefold()
        ):
            result.append(
                Violation(
                    code=f"lock-target-{key.replace('_', '-')}-drift",
                    packages=(),
                    summary=(
                        f"{label} is {actual_value}; the lockfile was resolved for {expected_value}"
                    ),
                    fix="run rigsolve check against the applicable matrix facts before installing",
                    severity="warning",
                )
            )

    if unknown:
        result.append(
            Violation(
                code="lock-target-unverified",
                packages=(),
                summary="could not verify lockfile target fields: " + ", ".join(unknown),
                detail="Unknown detection data is not treated as a confirmed match.",
                severity="warning",
            )
        )
    return result


def _lockfile_violations(
    profile: MachineProfile, plan: InstallPlan, store: MatrixStore
) -> list[Violation]:
    result: list[Violation] = []
    installed = {package.normalized_name: package for package in profile.installed.packages}
    for step in plan.steps:
        actual = installed.get(canonicalize_name(step.package))
        if actual is None:
            result.append(
                Violation(
                    code="lock-missing",
                    packages=(step.package,),
                    summary=f"{step.package} is required by the lockfile but is not installed",
                    fix=f"install {step.package}=={step.version}",
                )
            )
            continue
        elif _public_version(actual.version) != _public_version(step.version):
            result.append(
                Violation(
                    code="lock-version-drift",
                    packages=(step.package,),
                    summary=(
                        f"{step.package} is {actual.version}, but the lockfile requires {step.version}"
                    ),
                    fix=f"reinstall {step.package}=={step.version}",
                )
            )
            continue
        expected_cuda = step.cuda_line
        actual_cuda = actual.cuda_line
        if step.package == "torch" and profile.torch is not None:
            actual_cuda = profile.torch.cuda_version or actual_cuda
        if expected_cuda:
            if actual_cuda is None:
                result.append(
                    Violation(
                        code="lock-build-unverified",
                        packages=(step.package,),
                        summary=f"{step.package}'s CUDA build marker could not be verified",
                        severity="warning",
                    )
                )
            elif not cuda_lines_compatible(actual_cuda, expected_cuda):
                result.append(
                    Violation(
                        code="lock-cuda-drift",
                        packages=(step.package,),
                        summary=(
                            f"{step.package} targets CUDA {actual_cuda}, but the lockfile requires "
                            f"CUDA {expected_cuda}"
                        ),
                        fix=f"reinstall {step.package} from the locked artifact or index",
                    )
                )
        actual_abi = actual.cxx11_abi
        if step.package == "torch" and profile.torch is not None:
            actual_abi = profile.torch.cxx11_abi
        if step.cxx11_abi is not None:
            if actual_abi is None:
                result.append(
                    Violation(
                        code="lock-build-unverified",
                        packages=(step.package,),
                        summary=f"{step.package}'s C++11 ABI marker could not be verified",
                        severity="warning",
                    )
                )
            elif actual_abi is not step.cxx11_abi:
                result.append(
                    Violation(
                        code="lock-cxx11abi-drift",
                        packages=(step.package,),
                        summary=f"{step.package}'s C++11 ABI does not match the lockfile",
                        fix=f"reinstall {step.package} from the locked artifact or index",
                    )
                )
        if step.torch_version:
            if actual.torch_version is None:
                result.append(
                    Violation(
                        code="lock-build-unverified",
                        packages=(step.package,),
                        summary=f"{step.package}'s torch build marker could not be verified",
                        severity="warning",
                    )
                )
            elif not _torch_versions_compatible(actual.torch_version, step.torch_version):
                result.append(
                    Violation(
                        code="lock-torch-build-drift",
                        packages=(step.package,),
                        summary=(
                            f"{step.package} targets torch {actual.torch_version}, but the "
                            f"lockfile requires torch {step.torch_version}"
                        ),
                        fix=f"reinstall {step.package} from the locked artifact",
                    )
                )
    if plan.matrix_digest != store.digest:
        result.append(
            Violation(
                code="lock-matrix-drift",
                packages=(),
                summary=(
                    f"the lockfile used matrix {plan.matrix_version} ({plan.matrix_digest[:12]}), "
                    f"but the active matrix is {store.matrix_version} ({store.digest[:12]})"
                ),
                detail="Package and target checks still use the locked plan; regenerate to adopt new facts.",
                severity="warning",
            )
        )
    result.extend(_target_lockfile_violations(profile, plan))
    return result


def _coupling_violations(
    installed: Mapping[str, InstalledPackage], store: MatrixStore
) -> list[Violation]:
    result: list[Violation] = []
    package_sets = sorted({fact.packages for fact in store.couplings})
    for packages in package_sets:
        present = tuple(package for package in packages if package in installed)
        if len(present) < 2:
            continue
        relevant = tuple(fact for fact in store.couplings if fact.packages == packages)
        for left, right in combinations(present, 2):
            left_version = _public_version(installed[left].version)
            right_version = _public_version(installed[right].version)
            lockstep = tuple(fact for fact in relevant if fact.kind == "exact-version-lockstep")
            release_sets = tuple(fact for fact in relevant if fact.kind == "compatible-release-set")

            # Lockstep facts describe a general relationship, so they remain
            # applicable even when an installed release is not in the matrix.
            if lockstep:
                # Unparseable installed metadata is unknown evidence, not a
                # confirmed lockstep mismatch.
                applicable = left_version is not None and right_version is not None
                compatible = applicable and left_version == right_version
                citations = _citation(list(lockstep))
            else:
                compatible = any(
                    left_version == _public_version(fact.version_map[left])
                    and right_version == _public_version(fact.version_map[right])
                    for fact in release_sets
                    if left in fact.version_map and right in fact.version_map
                )
                # A compatible-release-set is positive evidence, not an
                # exhaustive catalogue.  It can establish a hard negative only
                # when both observed releases occur somewhere in the published
                # tuple family; one represented side says nothing about a new
                # release of the other package.
                left_represented = any(
                    left_version == _public_version(fact.version_map[left])
                    for fact in release_sets
                    if left in fact.version_map and right in fact.version_map
                )
                right_represented = any(
                    right_version == _public_version(fact.version_map[right])
                    for fact in release_sets
                    if left in fact.version_map and right in fact.version_map
                )
                applicable = left_represented and right_represented
                anchored_release_sets = tuple(
                    fact
                    for fact in release_sets
                    if left in fact.version_map
                    and right in fact.version_map
                    and (
                        left_version == _public_version(fact.version_map[left])
                        or right_version == _public_version(fact.version_map[right])
                    )
                )
                citations = _citation(list(anchored_release_sets))

            if applicable and not compatible:
                result.append(
                    Violation(
                        code="release-coupling",
                        packages=(left, right),
                        summary=(
                            f"{left} {installed[left].version} and {right} "
                            f"{installed[right].version} are not a published compatibility tuple"
                        ),
                        fix="resolve both packages together with rigsolve solve",
                        citations=citations,
                    )
                )
    return result


def check_environment(
    profile: MachineProfile,
    store: MatrixStore,
    *,
    lockfile: Path | None = None,
    build_repair_plan: bool = False,
) -> CheckReport:
    violations: list[Violation] = []
    installed = {package.normalized_name: package for package in profile.installed.packages}
    torch_meta = installed.get("torch")
    torch_build = profile.torch
    torch_version = (
        torch_build.version if torch_build else (torch_meta.version if torch_meta else None)
    )
    torch_cuda = (
        torch_build.cuda_version if torch_build else (torch_meta.cuda_line if torch_meta else None)
    )
    torch_abi = (
        torch_build.cxx11_abi if torch_build else (torch_meta.cxx11_abi if torch_meta else None)
    )

    for package in installed.values():
        broken = store.known_broken_for(_package_assignment(package, torch_version, profile))
        for fact in broken:
            violations.append(
                Violation(
                    code=f"known-broken:{fact.id}",
                    packages=(package.normalized_name,),
                    summary=fact.description.strip(),
                    fix=fact.workaround,
                    citations=(fact.source.citation(),),
                )
            )
        if package.normalized_name == "torch":
            continue
        if (
            package.cuda_line
            and torch_cuda
            and not cuda_lines_compatible(package.cuda_line, torch_cuda)
        ):
            violations.append(
                Violation(
                    code="cuda-line-mismatch",
                    packages=("torch", package.normalized_name),
                    summary=(
                        f"torch was built for CUDA {torch_cuda}, but {package.name} "
                        f"expects CUDA {package.cuda_line}"
                    ),
                    detail=f"This commonly surfaces as a missing libcudart.so.{package.cuda_line.split('.')[0]} error.",
                    fix="re-resolve torch and the extension on one CUDA line",
                    citations=_applicable_wheel_citations(package, store, axis="cuda"),
                )
            )
        if package.torch_version and torch_version:
            required = Version(package.torch_version).release
            actual = Version(torch_version).release
            if actual[: len(required)] != required:
                violations.append(
                    Violation(
                        code="torch-build-mismatch",
                        packages=("torch", package.normalized_name),
                        summary=(
                            f"{package.name} expects torch {package.torch_version}, "
                            f"but torch {torch_version} is installed"
                        ),
                        fix="install an extension wheel built for this torch major/minor",
                        citations=_applicable_wheel_citations(package, store, axis="torch"),
                    )
                )
        if (
            package.cxx11_abi is not None
            and torch_abi is not None
            and package.cxx11_abi is not torch_abi
        ):
            violations.append(
                Violation(
                    code="cxx11abi-mismatch",
                    packages=("torch", package.normalized_name),
                    summary=f"{package.name} and torch use different C++11 ABI modes",
                    detail="This mismatch usually presents as an undefined C++ symbol during import.",
                    fix="install the wheel whose cxx11abi flag matches torch",
                    citations=_applicable_wheel_citations(package, store, axis="cxx11abi"),
                )
            )
        if package.source_build:
            python_tag = profile.platform.python_abi_tag
            matching = store.wheels_for(
                package.normalized_name,
                version=package.version,
                cuda_line=torch_cuda,
                torch=torch_version,
                cxx11abi=torch_abi,
                python=python_tag,
            )
            matching = tuple(
                fact
                for fact in matching
                if fact.platform is not None and _platform_matches((fact.platform,), profile)
            )
            if matching:
                violations.append(
                    Violation(
                        code="avoidable-source-build",
                        packages=(package.normalized_name,),
                        summary=f"{package.name} is a source build, but a matching wheel exists",
                        fix=f"reinstall from {matching[0].url}",
                        citations=_citation(list(matching)),
                        severity="warning",
                    )
                )

    if torch_cuda and profile.driver_version:
        platform = (
            "windows"
            if profile.platform.is_wsl or (profile.os or "").lower().startswith("win")
            else "linux"
        )
        minimum = store.driver_minimum(torch_cuda, platform)
        if minimum and _version_tuple(profile.driver_version) < _version_tuple(minimum):
            driver_facts = tuple(
                fact
                for fact in store.constraints
                if cuda_lines_compatible(fact.cuda_runtime, torch_cuda)
                and fact.minimum_for(platform) == minimum
            )
            violations.append(
                Violation(
                    code="driver-too-old",
                    packages=("torch",),
                    summary=(
                        f"driver {profile.driver_version} is below the {minimum} floor for CUDA {torch_cuda}"
                    ),
                    fix=(
                        "update the Windows host driver (WSL uses the host driver)"
                        if profile.platform.is_wsl
                        else f"update the NVIDIA driver to at least {minimum}"
                    ),
                    citations=_citation(list(driver_facts)),
                )
            )

    if torch_build and torch_build.archs and profile.compute_capabilities:
        missing_archs = set(profile.compute_capabilities).difference(torch_build.archs)
        if missing_archs:
            violations.append(
                Violation(
                    code="missing-kernel-architecture",
                    packages=("torch",),
                    summary=(
                        "the installed torch build has no recorded kernels for "
                        + ", ".join(sorted(missing_archs))
                    ),
                    fix="install a build whose architecture list covers this GPU",
                )
            )

    violations.extend(_coupling_violations(installed, store))
    if lockfile is not None:
        violations.extend(_lockfile_violations(profile, load_lockfile(lockfile), store))

    repair: InstallPlan | None = None
    if build_repair_plan and violations:
        affected = sorted(
            {
                package
                for violation in violations
                for package in violation.packages
                if package in store.packages
            }
        )
        if affected:
            outcome = resolve(affected, profile, store, preference="minimal-change")
            repair = outcome.plan
    return CheckReport(violations=tuple(violations), repair_plan=repair)


def _version_tuple(value: str) -> tuple[int, ...]:
    import re

    return tuple(int(part) for part in re.findall(r"\d+", value))


def format_check_report(report: CheckReport) -> str:
    if not report.violations:
        return (
            "[ok] No known incompatibility found among applicable facts; "
            "unknown axes remain unverified.\n"
        )
    lines = []
    for violation in report.violations:
        symbol = "[FAIL]" if violation.severity == "error" else "[!]"
        lines.append(f"{symbol} {violation.summary}")
        if violation.detail:
            lines.append(f"  {violation.detail}")
        for citation in violation.citations:
            lines.append(f"  source: {citation}")
        if violation.fix:
            lines.append(f"  fix: {violation.fix}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
