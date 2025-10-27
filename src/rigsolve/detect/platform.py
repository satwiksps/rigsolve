"""Operating-system, Python ABI, container, and WSL detection."""

from __future__ import annotations

import os
import platform as std_platform
import re
import subprocess
import sys
import sysconfig
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ._command import CommandRunner, run_command
from .model import DetectionIssue, PlatformInfo


@dataclass(frozen=True, slots=True)
class PlatformProbeResult:
    platform: PlatformInfo
    issues: tuple[DetectionIssue, ...] = ()


def normalize_os(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.strip().lower()
    if lowered.startswith("linux"):
        return "linux"
    if lowered == "win" or lowered.startswith(("windows", "mingw", "msys", "cygwin")):
        return "windows"
    if lowered in {"darwin", "mac", "macos", "osx"}:
        return "macos"
    return lowered


def normalize_architecture(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.strip().lower().replace("-", "_")
    aliases = {
        "amd64": "x86_64",
        "x64": "x86_64",
        "x86_64": "x86_64",
        "arm64": "aarch64",
        "aarch64": "aarch64",
        "i386": "x86",
        "i686": "x86",
        "x86": "x86",
    }
    return aliases.get(lowered, lowered)


def parse_glibc_version(output: str | None) -> str | None:
    """Extract a glibc version from confstr, libc_ver, or ``ldd`` output."""

    if not output:
        return None
    patterns = (
        r"(?:glibc|gnu\s+libc)\s*([0-9]+\.[0-9]+)",
        r"\bldd\b[^\n]*?([0-9]+\.[0-9]+)(?:[-.][0-9]+)?\s*$",
        r"\b([0-9]+\.[0-9]+)(?:[-.][0-9]+)?\s*$",
    )
    for line in output.splitlines():
        for pattern in patterns:
            match = re.search(pattern, line.strip(), re.IGNORECASE)
            if match:
                return match.group(1)
    return None


def derive_manylinux_tag(
    glibc_version: str | None,
    architecture: str | None,
) -> str | None:
    """Return the host's native PEP 600 compatibility tag."""

    if not glibc_version or not architecture:
        return None
    match = re.fullmatch(r"(\d+)\.(\d+)", glibc_version.strip())
    if match is None:
        return None
    arch = normalize_architecture(architecture)
    if arch not in {"x86_64", "aarch64", "ppc64le", "s390x", "x86"}:
        return None
    return f"manylinux_{int(match.group(1))}_{int(match.group(2))}_{arch}"


def detect_wsl(
    proc_version: str | None,
    *,
    kernel_release: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> bool:
    env = os.environ if environ is None else environ
    evidence = " ".join((proc_version or "", kernel_release or "")).lower()
    return (
        "microsoft" in evidence
        or "wsl" in evidence
        or bool(env.get("WSL_INTEROP"))
        or bool(env.get("WSL_DISTRO_NAME"))
    )


def detect_container_runtime(
    cgroup: str | None,
    *,
    dockerenv_exists: bool = False,
    containerenv_exists: bool = False,
    environ: Mapping[str, str] | None = None,
) -> str | None:
    env = os.environ if environ is None else environ
    explicit = env.get("container", "").strip().lower()
    if explicit:
        return explicit
    content = (cgroup or "").lower()
    if "kubepods" in content:
        return "kubernetes"
    if "libpod" in content or "podman" in content or containerenv_exists:
        return "podman"
    if "containerd" in content:
        return "containerd"
    if "docker" in content or dockerenv_exists:
        return "docker"
    if "lxc" in content:
        return "lxc"
    return None


def _read_text(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return None


def _glibc_version(
    *,
    runner: CommandRunner,
    timeout: float,
) -> tuple[str | None, DetectionIssue | None]:
    confstr = getattr(os, "confstr", None)
    try:
        confstr_value = confstr("CS_GNU_LIBC_VERSION") if callable(confstr) else None
    except (OSError, ValueError):
        confstr_value = None
    parsed = parse_glibc_version(confstr_value)
    if parsed:
        return parsed, None

    try:
        libc_name, libc_version = std_platform.libc_ver()
    except OSError:
        libc_name, libc_version = "", ""
    if libc_name.lower() == "glibc" and parse_glibc_version(libc_version):
        return parse_glibc_version(libc_version), None

    try:
        result = runner(("ldd", "--version"), timeout)
    except (OSError, subprocess.TimeoutExpired):
        result = None
    if result is not None:
        parsed = parse_glibc_version(f"{result.stdout}\n{result.stderr}")
        if parsed:
            return parsed, None
    return None, DetectionIssue(
        "platform", "glibc-unknown", "glibc version could not be determined", "info"
    )


def python_abi_tag(
    implementation: str,
    major: int,
    minor: int,
    *,
    abi_flags: str = "",
) -> str:
    normalized = implementation.strip().lower()
    prefix = {
        "cpython": "cp",
        "pypy": "pp",
        "graalpy": "gp",
    }.get(normalized, normalized[:2] or "py")
    flags = abi_flags if normalized == "cpython" else ""
    return f"{prefix}{major}{minor}{flags}"


def detect_platform(
    *,
    runner: CommandRunner = run_command,
    timeout: float = 3.0,
    proc_version: str | None = None,
    cgroup: str | None = None,
    environ: Mapping[str, str] | None = None,
    dockerenv_exists: bool | None = None,
    containerenv_exists: bool | None = None,
) -> PlatformProbeResult:
    """Collect platform facts with fixture injection points for proc/cgroup data."""

    env = os.environ if environ is None else environ
    os_name = normalize_os(std_platform.system())
    kernel = std_platform.release() or None
    architecture = normalize_architecture(std_platform.machine())
    issues: list[DetectionIssue] = []

    glibc_version: str | None = None
    if os_name == "linux":
        glibc_version, glibc_issue = _glibc_version(runner=runner, timeout=timeout)
        if glibc_issue is not None:
            issues.append(glibc_issue)

    if proc_version is None and os_name == "linux":
        proc_version = _read_text("/proc/version")
    if cgroup is None and os_name == "linux":
        cgroup = _read_text("/proc/1/cgroup")
    if dockerenv_exists is None:
        dockerenv_exists = Path("/.dockerenv").exists()
    if containerenv_exists is None:
        containerenv_exists = Path("/run/.containerenv").exists()
    is_wsl = detect_wsl(proc_version, kernel_release=kernel, environ=env)
    runtime = detect_container_runtime(
        cgroup,
        dockerenv_exists=dockerenv_exists,
        containerenv_exists=containerenv_exists,
        environ=env,
    )

    implementation = std_platform.python_implementation().lower()
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    abi = python_abi_tag(
        implementation,
        sys.version_info.major,
        sys.version_info.minor,
        abi_flags=getattr(sys, "abiflags", ""),
    )
    soabi_value = sysconfig.get_config_var("SOABI")
    soabi = str(soabi_value) if soabi_value else None
    info = PlatformInfo(
        os=os_name,
        kernel=kernel,
        architecture=architecture,
        glibc_version=glibc_version,
        manylinux_tag=(
            derive_manylinux_tag(glibc_version, architecture) if os_name == "linux" else None
        ),
        python_version=version,
        python_implementation=implementation,
        python_abi_tag=abi,
        python_soabi=soabi,
        is_wsl=is_wsl,
        is_container=runtime is not None,
        container_runtime=runtime,
    )
    return PlatformProbeResult(platform=info, issues=tuple(issues))


detect_platform_info = detect_platform
