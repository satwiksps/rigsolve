"""High-level machine profile collection."""

from __future__ import annotations

from ._command import CommandRunner, run_command
from .driver import max_cuda_runtime_for_driver
from .gpu import detect_gpus
from .installed import DistributionProvider, detect_installed
from .model import DriverInfo, InstalledEnvironment, MachineProfile
from .platform import detect_platform
from .target import TargetSpec, profile_from_target
from .toolkit import detect_nvcc


def detect_machine_profile(
    *,
    target: str | TargetSpec | None = None,
    runner: CommandRunner = run_command,
    distributions: DistributionProvider | None = None,
    include_installed: bool = True,
    torch_binary_scan_limit: int = 256 * 1024 * 1024,
    nvcc_executable: str | None = None,
) -> MachineProfile:
    """Collect a local profile or construct a fully hypothetical target profile.

    Passing ``target`` deliberately skips local probes.  This prevents details
    from the caller's workstation leaking into a Docker/CI target.
    """

    if target is not None:
        return profile_from_target(target)

    platform_probe = detect_platform(runner=runner)
    gpu_probe = detect_gpus(runner=runner)
    toolkit_probe = detect_nvcc(runner=runner, executable=nvcc_executable)
    if include_installed:
        if distributions is None:
            installed_probe = detect_installed(torch_binary_scan_limit=torch_binary_scan_limit)
        else:
            installed_probe = detect_installed(
                distributions=distributions,
                torch_binary_scan_limit=torch_binary_scan_limit,
            )
        installed = installed_probe.environment
        installed_issues = installed_probe.issues
    else:
        installed = InstalledEnvironment()
        installed_issues = ()

    # WSL receives a Windows display driver via the host, despite reporting a
    # Linux userspace.  The minimum-version table must use Windows thresholds.
    driver_os = "windows" if platform_probe.platform.is_wsl else platform_probe.platform.os
    driver = DriverInfo(
        version=gpu_probe.driver_version,
        max_cuda_runtime=max_cuda_runtime_for_driver(
            gpu_probe.driver_version,
            os_name=driver_os,
        ),
    )
    issues = platform_probe.issues + gpu_probe.issues + toolkit_probe.issues + installed_issues
    return MachineProfile(
        gpus=gpu_probe.devices,
        driver=driver,
        toolkit=toolkit_probe.toolkit,
        platform=platform_probe.platform,
        installed=installed,
        issues=issues,
        source="local",
    )


detect_profile = detect_machine_profile
collect_machine_profile = detect_machine_profile
