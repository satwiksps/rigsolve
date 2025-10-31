from __future__ import annotations

from pathlib import Path
from typing import Any

import rigsolve.detect.platform as platform_module
from rigsolve.detect._command import CommandResult
from rigsolve.detect.platform import (
    derive_manylinux_tag,
    detect_container_runtime,
    detect_wsl,
    normalize_architecture,
    normalize_os,
    parse_glibc_version,
    python_abi_tag,
)

FIXTURES = Path(__file__).parent / "fixtures" / "detect"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_wsl_detection_uses_proc_and_environment() -> None:
    assert detect_wsl(fixture("proc_version_wsl2.txt"), environ={}) is True
    assert detect_wsl(fixture("proc_version_linux.txt"), environ={}) is False
    assert detect_wsl(None, environ={"WSL_DISTRO_NAME": "Ubuntu"}) is True


def test_container_runtime_detection_covers_common_cgroups() -> None:
    assert detect_container_runtime(fixture("cgroup_docker_v2.txt"), environ={}) == "docker"
    assert detect_container_runtime(fixture("cgroup_kubernetes.txt"), environ={}) == "kubernetes"
    assert detect_container_runtime(None, containerenv_exists=True, environ={}) == "podman"
    assert detect_container_runtime(None, environ={"container": "lxc"}) == "lxc"
    assert detect_container_runtime(None, environ={}) is None


def test_glibc_and_manylinux_derivation() -> None:
    assert parse_glibc_version(fixture("ldd_ubuntu_2_35.txt")) == "2.35"
    assert parse_glibc_version("glibc 2.17") == "2.17"
    assert derive_manylinux_tag("2.35", "AMD64") == "manylinux_2_35_x86_64"
    assert derive_manylinux_tag(None, "x86_64") is None


def test_platform_normalization_and_python_abi() -> None:
    assert normalize_os("Windows-11") == "windows"
    assert normalize_os("Darwin") == "macos"
    assert normalize_architecture("AMD64") == "x86_64"
    assert normalize_architecture("arm64") == "aarch64"
    assert python_abi_tag("cpython", 3, 12) == "cp312"
    assert python_abi_tag("pypy", 3, 10) == "pp310"


def test_full_linux_platform_probe_from_recorded_proc_data(monkeypatch: Any) -> None:
    monkeypatch.setattr(platform_module.std_platform, "system", lambda: "Linux")
    monkeypatch.setattr(platform_module.std_platform, "release", lambda: "5.15.153-WSL2")
    monkeypatch.setattr(platform_module.std_platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(platform_module.std_platform, "python_implementation", lambda: "CPython")
    monkeypatch.setattr(platform_module.os, "confstr", lambda name: "glibc 2.35", raising=False)

    def forbidden_runner(args: object, timeout: float) -> CommandResult:
        raise AssertionError("ldd fallback should not run when confstr succeeds")

    result = platform_module.detect_platform(
        runner=forbidden_runner,  # type: ignore[arg-type]
        proc_version=fixture("proc_version_wsl2.txt"),
        cgroup=fixture("cgroup_docker_v2.txt"),
        environ={},
        dockerenv_exists=False,
        containerenv_exists=False,
    )

    assert result.platform.os == "linux"
    assert result.platform.architecture == "x86_64"
    assert result.platform.glibc_version == "2.35"
    assert result.platform.manylinux_tag == "manylinux_2_35_x86_64"
    assert result.platform.is_wsl is True
    assert result.platform.is_container is True
    assert result.platform.container_runtime == "docker"
    assert result.platform.python_abi_tag.startswith("cp")
    assert result.issues == ()


def test_glibc_probe_falls_back_to_ldd(monkeypatch: Any) -> None:
    monkeypatch.setattr(platform_module.os, "confstr", lambda name: None, raising=False)
    monkeypatch.setattr(platform_module.std_platform, "libc_ver", lambda: ("", ""))

    def runner(args: object, timeout: float) -> CommandResult:
        command = tuple(str(value) for value in args)  # type: ignore[arg-type]
        return CommandResult(command, 0, stdout=fixture("ldd_ubuntu_2_35.txt"))

    version, issue = platform_module._glibc_version(runner=runner, timeout=1)

    assert version == "2.35"
    assert issue is None
