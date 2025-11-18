"""Inspect installed distributions without importing any of them.

In particular, torch is never imported.  Its CUDA version is recovered from
``torch/version.py``, its C++ ABI from bundled CMake/build configuration, and
compiled architectures from static build text or binary string markers.
"""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Callable, Iterable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

from .model import (
    DetectionIssue,
    InstalledEnvironment,
    InstalledPackage,
    TorchBuild,
    normalise_compute_capability,
    optional_text,
)

DistributionProvider = Callable[[], Iterable[metadata.Distribution]]


@dataclass(frozen=True, slots=True)
class InstalledProbeResult:
    environment: InstalledEnvironment
    issues: tuple[DetectionIssue, ...] = ()


def canonicalize_package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _cuda_from_digits(digits: str) -> str:
    if len(digits) <= 2:
        return str(int(digits))
    if len(digits) == 3:
        return f"{int(digits[:2])}.{int(digits[2:])}"
    return f"{int(digits[:2])}.{int(digits[2:])}"


def parse_build_markers(version: str) -> tuple[str | None, str | None, bool | None]:
    """Extract CUDA, torch, and C++ ABI markers from native wheel versions."""

    cuda_match = re.search(
        r"(?:^|[+._-])cu(?:da)?(?P<cuda>\d{2,4})(?=$|[+._-]|torch)",
        version,
        re.IGNORECASE,
    )
    torch_match = re.search(r"torch(?P<torch>\d+(?:\.\d+)*)", version, re.IGNORECASE)
    abi_match = re.search(r"cxx11abi(?P<abi>true|false|0|1)", version, re.IGNORECASE)
    cuda = _cuda_from_digits(cuda_match.group("cuda")) if cuda_match else None
    torch_version = torch_match.group("torch") if torch_match else None
    abi: bool | None = None
    if abi_match:
        abi = abi_match.group("abi").lower() in {"true", "1"}
    return cuda, torch_version, abi


def _distribution_name(distribution: metadata.Distribution) -> str | None:
    try:
        value = distribution.metadata["Name"]
    except (AttributeError, KeyError, TypeError):
        value = None
    return optional_text(value)


def _distribution_version(distribution: metadata.Distribution) -> str | None:
    try:
        return optional_text(distribution.version)
    except (AttributeError, metadata.PackageNotFoundError):
        return None


def _read_distribution_text(
    distribution: metadata.Distribution,
    filename: str,
) -> str | None:
    try:
        return distribution.read_text(filename)
    except (AttributeError, OSError, UnicodeError):
        return None


def _wheel_tags(distribution: metadata.Distribution) -> tuple[str, ...]:
    wheel = _read_distribution_text(distribution, "WHEEL")
    if not wheel:
        return ()
    tags = []
    for line in wheel.splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip().lower() == "tag" and value.strip():
            tags.append(value.strip())
    return tuple(sorted(set(tags)))


def _source_build(distribution: metadata.Distribution) -> bool | None:
    direct_url = _read_distribution_text(distribution, "direct_url.json")
    if not direct_url:
        return None
    try:
        payload = json.loads(direct_url)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, Mapping):
        return None
    if "dir_info" in payload or "vcs_info" in payload:
        return True
    url = str(payload.get("url", "")).lower()
    if url.endswith(".whl"):
        return False
    if any(extension in url for extension in (".tar.gz", ".tar.bz2", ".zip")):
        return True
    return None


def inspect_distribution(distribution: metadata.Distribution) -> InstalledPackage | None:
    """Convert one ``importlib.metadata`` distribution to a stable record."""

    name = _distribution_name(distribution)
    version = _distribution_version(distribution)
    if name is None or version is None:
        return None
    try:
        location = str(Path(str(distribution.locate_file(""))).resolve())
    except (AttributeError, OSError, TypeError):
        location = None
    cuda_version, torch_version, cxx11_abi = parse_build_markers(version)
    return InstalledPackage(
        name=name,
        version=version,
        location=location,
        cuda_version=cuda_version,
        torch_version=torch_version,
        cxx11_abi=cxx11_abi,
        wheel_tags=_wheel_tags(distribution),
        source_build=_source_build(distribution),
    )


def _torch_root(distribution: metadata.Distribution) -> Path | None:
    try:
        root = Path(str(distribution.locate_file("torch")))
    except (AttributeError, OSError, TypeError):
        return None
    return root if root.exists() and root.is_dir() else None


def _literal_assignments(path: Path) -> dict[str, object]:
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError, UnicodeError):
        return {}
    values: dict[str, object] = {}
    wanted = {"__version__", "cuda", "hip", "xpu", "debug", "git_version"}
    for statement in tree.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        value_node = statement.value
        if value_node is None:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id in wanted:
                with suppress(ValueError, TypeError):
                    values[target.id] = ast.literal_eval(value_node)
    return values


_ABI_RE = re.compile(rb"(?:_GLIBCXX_USE_CXX11_ABI|GLIBCXX_USE_CXX11_ABI)\s*=?\s*([01])")
_ARCH_RE = re.compile(rb"(?:sm|compute)_([0-9]{2,3})(?:[a-z])?")


def _scan_text_configs(torch_root: Path) -> tuple[bool | None, set[str], list[str]]:
    candidates = (
        torch_root / "share" / "cmake" / "Torch" / "TorchConfig.cmake",
        torch_root / "share" / "cmake" / "Caffe2" / "Caffe2Config.cmake",
        torch_root / "__config__.py",
    )
    abi: bool | None = None
    archs: set[str] = set()
    evidence: list[str] = []
    for path in candidates:
        try:
            if not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
                continue
            content = path.read_bytes()
        except OSError:
            continue
        abi_match = _ABI_RE.search(content)
        if abi_match is not None:
            abi = abi_match.group(1) == b"1"
            evidence.append(f"config:{path.name}:cxx11abi")
        discovered = {f"sm_{int(match.group(1))}" for match in _ARCH_RE.finditer(content)}
        if discovered:
            archs.update(discovered)
            evidence.append(f"config:{path.name}:archs")
    return abi, archs, evidence


def _cuda_library_candidates(torch_root: Path) -> tuple[Path, ...]:
    library_dir = torch_root / "lib"
    if not library_dir.is_dir():
        return ()
    patterns = ("libtorch_cuda.so*", "torch_cuda.dll", "libtorch_cuda.dylib")
    candidates: list[Path] = []
    for pattern in patterns:
        try:
            candidates.extend(path for path in library_dir.glob(pattern) if path.is_file())
        except OSError:
            continue
    return tuple(sorted(set(candidates), key=lambda path: str(path)))


def _scan_binary_archs(path: Path, max_bytes: int) -> set[str]:
    archs: set[str] = set()
    if max_bytes <= 0:
        return archs
    chunk_size = 4 * 1024 * 1024
    overlap = 32
    consumed = 0
    tail = b""
    try:
        with path.open("rb") as stream:
            while consumed < max_bytes:
                chunk = stream.read(min(chunk_size, max_bytes - consumed))
                if not chunk:
                    break
                consumed += len(chunk)
                content = tail + chunk
                archs.update(f"sm_{int(match.group(1))}" for match in _ARCH_RE.finditer(content))
                tail = content[-overlap:]
    except OSError:
        return set()
    return archs


def _cuda_from_local_version(version: str) -> str | None:
    match = re.search(r"(?:^|\+)cu(\d{2,4})(?:$|[.+-])", version, re.IGNORECASE)
    return _cuda_from_digits(match.group(1)) if match else None


def inspect_torch_distribution(
    distribution: metadata.Distribution,
    *,
    binary_scan_limit: int = 256 * 1024 * 1024,
) -> TorchBuild | None:
    """Recover torch build facts statically, even if its extension cannot load."""

    distribution_version = _distribution_version(distribution)
    if distribution_version is None:
        return None
    torch_root = _torch_root(distribution)
    if torch_root is None:
        return TorchBuild(version=distribution_version, evidence=("distribution-metadata",))

    assignments = _literal_assignments(torch_root / "version.py")
    version = optional_text(assignments.get("__version__")) or distribution_version
    cuda_version = optional_text(assignments.get("cuda")) or _cuda_from_local_version(version)
    evidence: list[str] = ["distribution-metadata"]
    if assignments:
        evidence.append("torch/version.py")

    abi, archs, config_evidence = _scan_text_configs(torch_root)
    evidence.extend(config_evidence)
    if not archs and binary_scan_limit > 0:
        remaining = binary_scan_limit
        for library in _cuda_library_candidates(torch_root):
            try:
                scan_size = min(remaining, library.stat().st_size)
            except OSError:
                continue
            discovered = _scan_binary_archs(library, scan_size)
            if discovered:
                archs.update(discovered)
                evidence.append(f"binary:{library.name}:archs")
            remaining -= scan_size
            if remaining <= 0:
                break
    normalized_archs = tuple(
        sorted(
            value
            for value in (normalise_compute_capability(arch) for arch in archs)
            if value is not None
        )
    )
    return TorchBuild(
        version=version,
        cuda_version=cuda_version,
        cxx11_abi=abi,
        archs=normalized_archs,
        location=str(torch_root),
        evidence=tuple(evidence),
    )


def detect_installed(
    *,
    distributions: DistributionProvider = metadata.distributions,
    torch_binary_scan_limit: int = 256 * 1024 * 1024,
) -> InstalledProbeResult:
    """Enumerate installed packages and statically inspect torch when present."""

    packages: list[InstalledPackage] = []
    torch_distribution: metadata.Distribution | None = None
    skipped = 0
    try:
        available = list(distributions())
    except Exception as exc:  # metadata backends can be third-party plug-ins
        return InstalledProbeResult(
            environment=InstalledEnvironment(),
            issues=(
                DetectionIssue(
                    "installed",
                    "metadata-enumeration-failed",
                    f"installed distributions could not be enumerated: {exc}",
                ),
            ),
        )

    for distribution in available:
        try:
            package = inspect_distribution(distribution)
        except Exception:  # malformed third-party metadata must not abort detection
            package = None
        if package is None:
            skipped += 1
            continue
        packages.append(package)
        if package.normalized_name == "torch" and torch_distribution is None:
            torch_distribution = distribution

    issues: list[DetectionIssue] = []
    if skipped:
        issues.append(
            DetectionIssue(
                "installed",
                "invalid-distribution-metadata",
                f"ignored {skipped} installed distribution(s) with unreadable metadata",
                "info",
            )
        )
    torch_build: TorchBuild | None = None
    if torch_distribution is not None:
        try:
            torch_build = inspect_torch_distribution(
                torch_distribution,
                binary_scan_limit=torch_binary_scan_limit,
            )
        except Exception as exc:  # static inspection is always best effort
            issues.append(
                DetectionIssue(
                    "installed",
                    "torch-static-inspection-failed",
                    f"installed torch metadata was found but build facts could not be read: {exc}",
                )
            )
    return InstalledProbeResult(
        environment=InstalledEnvironment(packages=tuple(packages), torch=torch_build),
        issues=tuple(issues),
    )


detect_installed_packages = detect_installed
