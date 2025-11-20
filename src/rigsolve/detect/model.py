"""Immutable models shared by rigsolve's hardware and environment probes.

Detection is deliberately best effort.  Missing values are represented by
``None`` (or an empty tuple for collections) and recoverable failures are
recorded as :class:`DetectionIssue` instances on the machine profile.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from rigsolve.errors import DetectionError

_UNKNOWN_VALUES = {"", "n/a", "na", "none", "null", "unknown", "[not supported]"}


class ProfileValidationError(DetectionError, ValueError):
    """Raised when a serialized machine profile is structurally invalid."""


def optional_text(value: object) -> str | None:
    """Return a stripped string, treating common probe sentinels as unknown."""

    if value is None:
        return None
    text = str(value).strip()
    return None if text.lower() in _UNKNOWN_VALUES else text


def normalise_compute_capability(value: object) -> str | None:
    """Normalize compute capabilities such as ``8.9`` and ``89`` to ``sm_89``."""

    text = optional_text(value)
    if text is None:
        return None
    lowered = text.lower().replace("compute_", "").replace("sm_", "")
    match = re.fullmatch(r"(\d{1,2})\.(\d)", lowered)
    if match:
        return f"sm_{int(match.group(1))}{match.group(2)}"
    if re.fullmatch(r"\d{2,3}", lowered):
        return f"sm_{int(lowered)}"
    raise ProfileValidationError(f"invalid compute capability: {value!r}")


def _optional_bool(value: object) -> bool | None:
    if value is None or (isinstance(value, str) and value.strip().lower() in _UNKNOWN_VALUES):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    raise ProfileValidationError(f"invalid boolean: {value!r}")


def _mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ProfileValidationError(f"{field_name} must be an object")
    return value


@dataclass(frozen=True, slots=True)
class DetectionIssue:
    """A non-fatal problem encountered while collecting a profile."""

    component: str
    code: str
    message: str
    severity: str = "warning"

    def __post_init__(self) -> None:
        if not self.component.strip() or not self.code.strip() or not self.message.strip():
            raise ProfileValidationError("detection issue fields cannot be empty")
        if self.severity not in {"info", "warning", "error"}:
            raise ProfileValidationError(f"invalid issue severity: {self.severity!r}")

    def to_dict(self) -> dict[str, object]:
        return {
            "component": self.component,
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> DetectionIssue:
        try:
            return cls(
                component=str(data["component"]),
                code=str(data["code"]),
                message=str(data["message"]),
                severity=str(data.get("severity", "warning")),
            )
        except KeyError as exc:
            raise ProfileValidationError(f"missing issue field: {exc.args[0]}") from exc


@dataclass(frozen=True, slots=True)
class GPUDevice:
    """One physical NVIDIA GPU as reported by ``nvidia-smi``."""

    index: int
    name: str | None = None
    compute_capability: str | None = None
    memory_total_mib: int | None = None
    uuid: str | None = None

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ProfileValidationError("GPU index cannot be negative")
        object.__setattr__(self, "name", optional_text(self.name))
        object.__setattr__(
            self,
            "compute_capability",
            normalise_compute_capability(self.compute_capability),
        )
        object.__setattr__(self, "uuid", optional_text(self.uuid))
        if self.memory_total_mib is not None and self.memory_total_mib < 0:
            raise ProfileValidationError("GPU memory cannot be negative")

    @property
    def sm(self) -> str | None:
        return self.compute_capability

    @property
    def memory_mib(self) -> int | None:
        return self.memory_total_mib

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "name": self.name,
            "compute_capability": self.compute_capability,
            "memory_total_mib": self.memory_total_mib,
            "uuid": self.uuid,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> GPUDevice:
        memory = data.get("memory_total_mib", data.get("memory_mib", data.get("vram_mib")))
        try:
            parsed_memory = None if memory is None else int(str(memory))
            return cls(
                index=int(str(data.get("index", 0))),
                name=optional_text(data.get("name")),
                compute_capability=optional_text(data.get("compute_capability", data.get("sm"))),
                memory_total_mib=parsed_memory,
                uuid=optional_text(data.get("uuid")),
            )
        except (TypeError, ValueError) as exc:
            raise ProfileValidationError(f"invalid GPU entry: {data!r}") from exc


@dataclass(frozen=True, slots=True)
class DriverInfo:
    version: str | None = None
    max_cuda_runtime: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "version", optional_text(self.version))
        object.__setattr__(self, "max_cuda_runtime", optional_text(self.max_cuda_runtime))

    def to_dict(self) -> dict[str, object]:
        return {"version": self.version, "max_cuda_runtime": self.max_cuda_runtime}

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> DriverInfo:
        return cls(
            version=optional_text(data.get("version", data.get("driver_version"))),
            max_cuda_runtime=optional_text(data.get("max_cuda_runtime", data.get("cuda_runtime"))),
        )


@dataclass(frozen=True, slots=True)
class CudaToolkit:
    """An optional local CUDA compiler/toolkit installation."""

    version: str
    compiler_build: str | None = None
    path: str | None = None

    def __post_init__(self) -> None:
        version = optional_text(self.version)
        if version is None:
            raise ProfileValidationError("CUDA toolkit version cannot be empty")
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "compiler_build", optional_text(self.compiler_build))
        object.__setattr__(self, "path", optional_text(self.path))

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "compiler_build": self.compiler_build,
            "path": self.path,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> CudaToolkit:
        version = optional_text(data.get("version"))
        if version is None:
            raise ProfileValidationError("CUDA toolkit is missing version")
        return cls(
            version=version,
            compiler_build=optional_text(data.get("compiler_build", data.get("build"))),
            path=optional_text(data.get("path")),
        )


@dataclass(frozen=True, slots=True)
class PlatformInfo:
    os: str | None = None
    kernel: str | None = None
    architecture: str | None = None
    glibc_version: str | None = None
    manylinux_tag: str | None = None
    python_version: str | None = None
    python_implementation: str | None = None
    python_abi_tag: str | None = None
    python_soabi: str | None = None
    is_wsl: bool = False
    is_container: bool = False
    container_runtime: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "os",
            "kernel",
            "architecture",
            "glibc_version",
            "manylinux_tag",
            "python_version",
            "python_implementation",
            "python_abi_tag",
            "python_soabi",
            "container_runtime",
        ):
            object.__setattr__(self, name, optional_text(getattr(self, name)))

    def to_dict(self) -> dict[str, object]:
        return {
            "os": self.os,
            "kernel": self.kernel,
            "architecture": self.architecture,
            "glibc_version": self.glibc_version,
            "manylinux_tag": self.manylinux_tag,
            "python_version": self.python_version,
            "python_implementation": self.python_implementation,
            "python_abi_tag": self.python_abi_tag,
            "python_soabi": self.python_soabi,
            "is_wsl": self.is_wsl,
            "is_container": self.is_container,
            "container_runtime": self.container_runtime,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> PlatformInfo:
        return cls(
            os=optional_text(data.get("os", data.get("system"))),
            kernel=optional_text(data.get("kernel", data.get("release"))),
            architecture=optional_text(data.get("architecture", data.get("arch"))),
            glibc_version=optional_text(data.get("glibc_version", data.get("glibc"))),
            manylinux_tag=optional_text(data.get("manylinux_tag", data.get("manylinux"))),
            python_version=optional_text(data.get("python_version", data.get("python"))),
            python_implementation=optional_text(
                data.get("python_implementation", data.get("implementation"))
            ),
            python_abi_tag=optional_text(data.get("python_abi_tag", data.get("python_abi"))),
            python_soabi=optional_text(data.get("python_soabi", data.get("soabi"))),
            is_wsl=bool(_optional_bool(data.get("is_wsl", False))),
            is_container=bool(_optional_bool(data.get("is_container", False))),
            container_runtime=optional_text(data.get("container_runtime")),
        )


@dataclass(frozen=True, slots=True)
class InstalledPackage:
    """Distribution metadata collected without importing the package."""

    name: str
    version: str
    location: str | None = None
    cuda_version: str | None = None
    cuda_line: str | None = None
    torch_version: str | None = None
    cxx11_abi: bool | None = None
    wheel_tags: tuple[str, ...] = ()
    source_build: bool | None = None

    def __post_init__(self) -> None:
        name = optional_text(self.name)
        version = optional_text(self.version)
        if name is None or version is None:
            raise ProfileValidationError("installed package name and version are required")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "location", optional_text(self.location))
        cuda_version = optional_text(self.cuda_version)
        cuda_line = optional_text(self.cuda_line)
        if cuda_line is None and cuda_version is not None:
            cuda_line = cuda_version.split(".", 1)[0]
        object.__setattr__(self, "cuda_version", cuda_version)
        object.__setattr__(self, "cuda_line", cuda_line)
        object.__setattr__(self, "torch_version", optional_text(self.torch_version))
        object.__setattr__(self, "wheel_tags", tuple(sorted(set(self.wheel_tags))))

    @property
    def normalized_name(self) -> str:
        return re.sub(r"[-_.]+", "-", self.name).lower()

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "version": self.version,
            "location": self.location,
            "cuda_version": self.cuda_version,
            "cuda_line": self.cuda_line,
            "torch_version": self.torch_version,
            "cxx11_abi": self.cxx11_abi,
            "wheel_tags": list(self.wheel_tags),
            "source_build": self.source_build,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> InstalledPackage:
        tags = data.get("wheel_tags", ())
        if not isinstance(tags, (list, tuple)):
            raise ProfileValidationError("wheel_tags must be a list")
        try:
            return cls(
                name=str(data["name"]),
                version=str(data["version"]),
                location=optional_text(data.get("location")),
                cuda_version=optional_text(data.get("cuda_version", data.get("cuda"))),
                cuda_line=optional_text(data.get("cuda_line")),
                torch_version=optional_text(data.get("torch_version", data.get("torch"))),
                cxx11_abi=_optional_bool(data.get("cxx11_abi")),
                wheel_tags=tuple(str(tag) for tag in tags),
                source_build=_optional_bool(data.get("source_build")),
            )
        except KeyError as exc:
            raise ProfileValidationError(f"missing installed package field: {exc.args[0]}") from exc


@dataclass(frozen=True, slots=True)
class TorchBuild:
    """Static facts recovered from an installed torch distribution."""

    version: str
    cuda_version: str | None = None
    cxx11_abi: bool | None = None
    archs: tuple[str, ...] = ()
    location: str | None = None
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        version = optional_text(self.version)
        if version is None:
            raise ProfileValidationError("torch version cannot be empty")
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "cuda_version", optional_text(self.cuda_version))
        object.__setattr__(self, "location", optional_text(self.location))
        normalized_archs = {
            normalized
            for normalized in (normalise_compute_capability(arch) for arch in self.archs if arch)
            if normalized is not None
        }
        object.__setattr__(self, "archs", tuple(sorted(normalized_archs)))
        object.__setattr__(self, "evidence", tuple(dict.fromkeys(self.evidence)))

    @property
    def cuda_line(self) -> str | None:
        if self.cuda_version is None:
            return None
        return self.cuda_version.split(".", 1)[0]

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "cuda_version": self.cuda_version,
            "cuda_line": self.cuda_line,
            "cxx11_abi": self.cxx11_abi,
            "archs": list(self.archs),
            "location": self.location,
            "evidence": list(self.evidence),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> TorchBuild:
        archs = data.get("archs", ())
        evidence = data.get("evidence", ())
        if not isinstance(archs, (list, tuple)) or not isinstance(evidence, (list, tuple)):
            raise ProfileValidationError("torch archs and evidence must be lists")
        try:
            return cls(
                version=str(data["version"]),
                cuda_version=optional_text(data.get("cuda_version", data.get("cuda"))),
                cxx11_abi=_optional_bool(data.get("cxx11_abi")),
                archs=tuple(str(value) for value in archs),
                location=optional_text(data.get("location")),
                evidence=tuple(str(value) for value in evidence),
            )
        except KeyError as exc:
            raise ProfileValidationError("torch build is missing version") from exc


@dataclass(frozen=True, slots=True)
class InstalledEnvironment:
    packages: tuple[InstalledPackage, ...] = ()
    torch: TorchBuild | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "packages",
            tuple(
                sorted(
                    self.packages, key=lambda package: (package.normalized_name, package.version)
                )
            ),
        )

    def get(self, name: str) -> InstalledPackage | None:
        normalized = re.sub(r"[-_.]+", "-", name).lower()
        return next(
            (package for package in self.packages if package.normalized_name == normalized),
            None,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "packages": [package.to_dict() for package in self.packages],
            "torch": None if self.torch is None else self.torch.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> InstalledEnvironment:
        raw_packages = data.get("packages", ())
        if not isinstance(raw_packages, (list, tuple)):
            raise ProfileValidationError("installed packages must be a list")
        packages = tuple(
            InstalledPackage.from_dict(_mapping(item, "installed package")) for item in raw_packages
        )
        raw_torch = data.get("torch")
        torch_build = (
            None
            if raw_torch is None
            else TorchBuild.from_dict(_mapping(raw_torch, "installed torch"))
        )
        return cls(packages=packages, torch=torch_build)


@dataclass(frozen=True, slots=True)
class MachineProfile:
    """Complete, serializable input to the compatibility solver."""

    gpus: tuple[GPUDevice, ...] = ()
    driver: DriverInfo = field(default_factory=DriverInfo)
    toolkit: CudaToolkit | None = None
    platform: PlatformInfo = field(default_factory=PlatformInfo)
    installed: InstalledEnvironment = field(default_factory=InstalledEnvironment)
    cxx11_abi: bool | None = None
    issues: tuple[DetectionIssue, ...] = ()
    source: str = "local"

    def __post_init__(self) -> None:
        object.__setattr__(self, "gpus", tuple(sorted(self.gpus, key=lambda gpu: gpu.index)))
        object.__setattr__(self, "issues", tuple(self.issues))
        if self.source not in {"local", "target", "fixture", "unknown"}:
            raise ProfileValidationError(f"invalid profile source: {self.source!r}")
        if self.cxx11_abi is None and self.installed.torch is not None:
            object.__setattr__(self, "cxx11_abi", self.installed.torch.cxx11_abi)

    @property
    def has_gpu(self) -> bool:
        return bool(self.gpus)

    @property
    def gpu_count(self) -> int:
        return len(self.gpus)

    @property
    def gpu_name(self) -> str | None:
        return self.gpus[0].name if self.gpus else None

    @property
    def compute_capability(self) -> str | None:
        return self.gpus[0].compute_capability if self.gpus else None

    @property
    def compute_capabilities(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                gpu.compute_capability for gpu in self.gpus if gpu.compute_capability is not None
            )
        )

    @property
    def driver_version(self) -> str | None:
        return self.driver.version

    @property
    def max_cuda_runtime(self) -> str | None:
        return self.driver.max_cuda_runtime

    @property
    def cuda_toolkit_version(self) -> str | None:
        return self.toolkit.version if self.toolkit else None

    @property
    def python_version(self) -> str | None:
        return self.platform.python_version

    @property
    def architecture(self) -> str | None:
        return self.platform.architecture

    @property
    def os(self) -> str | None:
        return self.platform.os

    @property
    def torch(self) -> TorchBuild | None:
        return self.installed.torch

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "source": self.source,
            "gpus": [gpu.to_dict() for gpu in self.gpus],
            "driver": self.driver.to_dict(),
            "toolkit": None if self.toolkit is None else self.toolkit.to_dict(),
            "platform": self.platform.to_dict(),
            "installed": self.installed.to_dict(),
            "cxx11_abi": self.cxx11_abi,
            "issues": [issue.to_dict() for issue in self.issues],
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> MachineProfile:
        schema_version = data.get("schema_version", 1)
        if schema_version != 1:
            raise ProfileValidationError(
                f"unsupported machine profile schema version: {schema_version!r}"
            )
        raw_gpus = data.get("gpus", ())
        raw_issues = data.get("issues", ())
        if not isinstance(raw_gpus, (list, tuple)):
            raise ProfileValidationError("gpus must be a list")
        if not isinstance(raw_issues, (list, tuple)):
            raise ProfileValidationError("issues must be a list")
        raw_driver = data.get("driver", {})
        raw_platform = data.get("platform", {})
        raw_installed = data.get("installed", {})
        raw_toolkit = data.get("toolkit")
        return cls(
            gpus=tuple(GPUDevice.from_dict(_mapping(item, "GPU")) for item in raw_gpus),
            driver=DriverInfo.from_dict(_mapping(raw_driver, "driver")),
            toolkit=(
                None
                if raw_toolkit is None
                else CudaToolkit.from_dict(_mapping(raw_toolkit, "toolkit"))
            ),
            platform=PlatformInfo.from_dict(_mapping(raw_platform, "platform")),
            installed=InstalledEnvironment.from_dict(
                _mapping(raw_installed, "installed environment")
            ),
            cxx11_abi=_optional_bool(data.get("cxx11_abi")),
            issues=tuple(
                DetectionIssue.from_dict(_mapping(item, "detection issue")) for item in raw_issues
            ),
            source=str(data.get("source", "unknown")),
        )

    @classmethod
    def from_json(cls, payload: str) -> MachineProfile:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ProfileValidationError(f"invalid machine profile JSON: {exc}") from exc
        return cls.from_dict(_mapping(data, "machine profile"))


# A concise alias useful to API consumers.
GpuDevice = GPUDevice
