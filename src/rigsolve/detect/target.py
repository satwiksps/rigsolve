"""Parser for hypothetical machine targets used by solve and CI generation."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, replace
from typing import Any, cast

from rigsolve.errors import UserInputError

from .driver import max_cuda_runtime_for_driver, parse_version_tuple
from .gpu import compute_capability_from_name
from .model import (
    CudaToolkit,
    DetectionIssue,
    DriverInfo,
    GPUDevice,
    InstalledEnvironment,
    MachineProfile,
    PlatformInfo,
    ProfileValidationError,
    normalise_compute_capability,
    optional_text,
)
from .platform import derive_manylinux_tag, normalize_architecture, normalize_os


class TargetParseError(UserInputError, ValueError):
    """Raised when a ``--target`` expression is invalid or ambiguous."""


def _bool(value: str, *, field: str) -> bool:
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise TargetParseError(f"{field} must be true or false, got {value!r}")


def _memory(value: str) -> int:
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(mib|mb|gib|gb)?\s*", value, re.IGNORECASE)
    if match is None:
        raise TargetParseError(f"invalid VRAM value: {value!r}")
    amount = float(match.group(1))
    unit = (match.group(2) or "mib").lower()
    if unit in {"gib", "gb"}:
        amount *= 1024
    return round(amount)


def _python_version(value: str) -> str:
    match = re.fullmatch(r"(?:python)?\s*(\d+)\.(\d+)(?:\.(\d+))?", value, re.IGNORECASE)
    if match is None:
        raise TargetParseError(f"invalid Python version: {value!r}")
    return ".".join(part for part in match.groups() if part is not None)


def _python_abi(version: str) -> str:
    major, minor, *_ = version.split(".")
    return f"cp{int(major)}{int(minor)}"


@dataclass(frozen=True, slots=True)
class TargetSpec:
    gpu_name: str | None = None
    gpu_count: int | None = None
    compute_capability: str | None = None
    memory_total_mib: int | None = None
    driver_version: str | None = None
    cuda_runtime: str | None = None
    toolkit_version: str | None = None
    toolkit_path: str | None = None
    os: str | None = None
    architecture: str | None = None
    glibc_version: str | None = None
    manylinux_tag: str | None = None
    python_version: str | None = None
    cxx11_abi: bool | None = None
    is_wsl: bool | None = None
    is_container: bool | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "gpu_name", optional_text(self.gpu_name))
        object.__setattr__(
            self,
            "compute_capability",
            normalise_compute_capability(self.compute_capability),
        )
        object.__setattr__(self, "driver_version", optional_text(self.driver_version))
        object.__setattr__(self, "cuda_runtime", optional_text(self.cuda_runtime))
        object.__setattr__(self, "toolkit_version", optional_text(self.toolkit_version))
        object.__setattr__(self, "toolkit_path", optional_text(self.toolkit_path))
        object.__setattr__(self, "os", normalize_os(self.os))
        object.__setattr__(self, "architecture", normalize_architecture(self.architecture))
        object.__setattr__(self, "glibc_version", optional_text(self.glibc_version))
        object.__setattr__(self, "manylinux_tag", optional_text(self.manylinux_tag))
        if self.python_version is not None:
            object.__setattr__(self, "python_version", _python_version(self.python_version))
        if self.gpu_count is not None and self.gpu_count < 0:
            raise TargetParseError("GPU count cannot be negative")
        if self.memory_total_mib is not None and self.memory_total_mib < 0:
            raise TargetParseError("VRAM cannot be negative")
        if self.driver_version is not None and parse_version_tuple(self.driver_version) is None:
            raise TargetParseError(f"invalid NVIDIA driver version: {self.driver_version!r}")
        for field_name in ("cuda_runtime", "toolkit_version", "glibc_version"):
            value = getattr(self, field_name)
            if value is not None and re.fullmatch(r"\d+(?:\.\d+){1,2}", value) is None:
                raise TargetParseError(f"invalid {field_name.replace('_', ' ')}: {value!r}")
        if self.toolkit_path is not None and any(
            character in self.toolkit_path for character in "\x00\r\n"
        ):
            raise TargetParseError("toolkit path contains a control character")

    def to_dict(self) -> dict[str, object]:
        return {
            "gpu_name": self.gpu_name,
            "gpu_count": self.gpu_count,
            "compute_capability": self.compute_capability,
            "memory_total_mib": self.memory_total_mib,
            "driver_version": self.driver_version,
            "cuda_runtime": self.cuda_runtime,
            "toolkit_version": self.toolkit_version,
            "toolkit_path": self.toolkit_path,
            "os": self.os,
            "architecture": self.architecture,
            "glibc_version": self.glibc_version,
            "manylinux_tag": self.manylinux_tag,
            "python_version": self.python_version,
            "cxx11_abi": self.cxx11_abi,
            "is_wsl": self.is_wsl,
            "is_container": self.is_container,
        }

    def to_profile(self, base: MachineProfile | None = None) -> MachineProfile:
        return profile_from_target(self, base=base)


_KEY_ALIASES = {
    "gpu": "gpu_name",
    "name": "gpu_name",
    "gpu_name": "gpu_name",
    "count": "gpu_count",
    "gpu_count": "gpu_count",
    "sm": "compute_capability",
    "cc": "compute_capability",
    "compute_cap": "compute_capability",
    "compute_capability": "compute_capability",
    "memory": "memory_total_mib",
    "vram": "memory_total_mib",
    "memory_mib": "memory_total_mib",
    "memory_total_mib": "memory_total_mib",
    "driver": "driver_version",
    "driver_version": "driver_version",
    "cuda": "cuda_runtime",
    "cuda_runtime": "cuda_runtime",
    "max_cuda": "cuda_runtime",
    "nvcc": "toolkit_version",
    "toolkit": "toolkit_version",
    "toolkit_version": "toolkit_version",
    "cuda_home": "toolkit_path",
    "cuda_path": "toolkit_path",
    "toolkit_path": "toolkit_path",
    "os": "os",
    "platform": "os",
    "arch": "architecture",
    "architecture": "architecture",
    "glibc": "glibc_version",
    "glibc_version": "glibc_version",
    "manylinux": "manylinux_tag",
    "manylinux_tag": "manylinux_tag",
    "python": "python_version",
    "py": "python_version",
    "python_version": "python_version",
    "abi": "cxx11_abi",
    "cxx11abi": "cxx11_abi",
    "cxx11_abi": "cxx11_abi",
    "wsl": "is_wsl",
    "container": "is_container",
}


def parse_target(value: str) -> TargetSpec:
    """Parse ``A100,driver=550.54,python=3.11,linux`` style targets."""

    if not value or not value.strip():
        raise TargetParseError("target cannot be empty")
    try:
        tokens = next(csv.reader([value], skipinitialspace=True))
    except csv.Error as exc:
        raise TargetParseError(f"invalid target quoting: {exc}") from exc
    parsed: dict[str, object] = {}
    for raw_token in tokens:
        token = raw_token.strip()
        if not token:
            raise TargetParseError("target contains an empty component")
        if "=" in token:
            raw_key, raw_value = token.split("=", 1)
            key = raw_key.strip().lower().replace("-", "_")
            field = _KEY_ALIASES.get(key)
            component = raw_value.strip()
            if field is None:
                supported = ", ".join(sorted(_KEY_ALIASES))
                raise TargetParseError(f"unknown target field {raw_key!r}; supported: {supported}")
            if not component:
                raise TargetParseError(f"target field {raw_key!r} cannot be empty")
            if field in parsed:
                raise TargetParseError(f"target field {raw_key!r} was specified more than once")
            if field in {"gpu_count"}:
                try:
                    parsed[field] = int(component)
                except ValueError as exc:
                    raise TargetParseError(f"GPU count must be an integer: {component!r}") from exc
            elif field == "memory_total_mib":
                parsed[field] = _memory(component)
            elif field in {"cxx11_abi", "is_wsl", "is_container"}:
                parsed[field] = _bool(component, field=raw_key)
            elif field == "compute_capability":
                try:
                    parsed[field] = normalise_compute_capability(component)
                except ProfileValidationError as exc:
                    raise TargetParseError(str(exc)) from exc
            elif field == "python_version":
                parsed[field] = _python_version(component)
            elif field == "os":
                parsed[field] = normalize_os(component)
            elif field == "architecture":
                parsed[field] = normalize_architecture(component)
            else:
                parsed[field] = component
            continue

        lowered = token.lower()
        normalized_os = normalize_os(token)
        if lowered in {"linux", "windows", "win", "darwin", "macos", "osx"}:
            if "os" in parsed:
                raise TargetParseError("target operating system was specified more than once")
            parsed["os"] = "windows" if lowered == "win" else normalized_os
        elif lowered == "wsl":
            if "is_wsl" in parsed:
                raise TargetParseError("WSL was specified more than once")
            parsed["is_wsl"] = True
            parsed.setdefault("os", "linux")
        elif lowered in {"container", "docker"}:
            if "is_container" in parsed:
                raise TargetParseError("container was specified more than once")
            parsed["is_container"] = True
        elif normalize_architecture(token) in {"x86_64", "aarch64", "ppc64le", "s390x", "x86"}:
            if "architecture" in parsed:
                raise TargetParseError("target architecture was specified more than once")
            parsed["architecture"] = normalize_architecture(token)
        elif re.fullmatch(r"(?:sm_|compute_)?\d{2,3}|\d{1,2}\.\d", lowered):
            if "compute_capability" in parsed:
                raise TargetParseError("compute capability was specified more than once")
            try:
                parsed["compute_capability"] = normalise_compute_capability(lowered)
            except ProfileValidationError as exc:
                raise TargetParseError(str(exc)) from exc
        elif lowered in {"cpu", "none", "no-gpu", "nogpu"}:
            if "gpu_name" in parsed or "gpu_count" in parsed:
                raise TargetParseError("GPU target was specified more than once")
            parsed["gpu_count"] = 0
        elif "gpu_name" not in parsed:
            parsed["gpu_name"] = token
        else:
            raise TargetParseError(
                f"unrecognized bare target component {token!r}; use key=value syntax"
            )
    try:
        return TargetSpec(**cast(Any, parsed))
    except (TypeError, ProfileValidationError) as exc:
        raise TargetParseError(str(exc)) from exc


def profile_from_target(
    target: str | TargetSpec,
    *,
    base: MachineProfile | None = None,
) -> MachineProfile:
    """Create a solver profile from a target, optionally overlaying local facts."""

    spec = parse_target(target) if isinstance(target, str) else target
    original = base or MachineProfile(
        platform=PlatformInfo(os="linux", architecture="x86_64"),
        installed=InstalledEnvironment(),
        source="unknown",
    )

    replaces_gpu = any(
        value is not None
        for value in (
            spec.gpu_name,
            spec.gpu_count,
            spec.compute_capability,
            spec.memory_total_mib,
        )
    )
    if replaces_gpu:
        count = spec.gpu_count
        if count is None:
            count = 1
        compute_capability = spec.compute_capability or compute_capability_from_name(spec.gpu_name)
        gpus = tuple(
            GPUDevice(
                index=index,
                name=spec.gpu_name,
                compute_capability=compute_capability,
                memory_total_mib=spec.memory_total_mib,
            )
            for index in range(count)
        )
    else:
        gpus = original.gpus

    os_name = spec.os or original.platform.os
    architecture = spec.architecture or original.platform.architecture
    if spec.glibc_version is not None:
        glibc_version = spec.glibc_version
    elif spec.os is not None and os_name != "linux":
        glibc_version = None
    else:
        glibc_version = original.platform.glibc_version
    manylinux = spec.manylinux_tag
    if os_name != "linux":
        manylinux = None
    elif manylinux is None:
        if spec.glibc_version is not None or spec.architecture is not None:
            manylinux = derive_manylinux_tag(glibc_version, architecture)
        else:
            manylinux = original.platform.manylinux_tag
    python_version = spec.python_version or original.platform.python_version
    python_abi = (
        _python_abi(spec.python_version)
        if spec.python_version is not None
        else original.platform.python_abi_tag
    )
    platform = replace(
        original.platform,
        os=os_name,
        architecture=architecture,
        glibc_version=glibc_version,
        manylinux_tag=manylinux,
        python_version=python_version,
        python_abi_tag=python_abi,
        is_wsl=spec.is_wsl if spec.is_wsl is not None else original.platform.is_wsl,
        is_container=(
            spec.is_container if spec.is_container is not None else original.platform.is_container
        ),
        container_runtime=(
            None
            if spec.is_container is False
            else (
                "target"
                if spec.is_container is True and original.platform.container_runtime is None
                else original.platform.container_runtime
            )
        ),
    )

    driver_version = spec.driver_version or original.driver.version
    max_runtime: str | None
    if spec.cuda_runtime is not None:
        max_runtime = spec.cuda_runtime
    elif spec.driver_version is not None:
        driver_os = "windows" if platform.is_wsl else os_name
        max_runtime = max_cuda_runtime_for_driver(driver_version, os_name=driver_os)
    else:
        max_runtime = original.driver.max_cuda_runtime
    driver = DriverInfo(version=driver_version, max_cuda_runtime=max_runtime)

    toolkit = original.toolkit
    if spec.toolkit_version is not None:
        toolkit = CudaToolkit(version=spec.toolkit_version, path=spec.toolkit_path)
    elif spec.toolkit_path is not None:
        if toolkit is None:
            raise TargetParseError("cuda_home requires an nvcc/toolkit version")
        toolkit = replace(toolkit, path=spec.toolkit_path)
    issues = tuple(issue for issue in original.issues if issue.code != "explicit-cpu-target")
    if spec.gpu_count == 0:
        issues = (
            *issues,
            DetectionIssue(
                component="gpu",
                code="explicit-cpu-target",
                message="the hypothetical target explicitly requests no GPU",
                severity="info",
            ),
        )
    elif not replaces_gpu:
        issues = original.issues
    return MachineProfile(
        gpus=gpus,
        driver=driver,
        toolkit=toolkit,
        platform=platform,
        installed=original.installed,
        cxx11_abi=(spec.cxx11_abi if spec.cxx11_abi is not None else original.cxx11_abi),
        issues=issues,
        source="target",
    )


def apply_target(profile: MachineProfile, target: str | TargetSpec) -> MachineProfile:
    return profile_from_target(target, base=profile)


parse_target_string = parse_target
