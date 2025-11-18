from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

import rigsolve.detect.profile as profile_module
from rigsolve.detect import (
    CudaToolkit,
    DetectionIssue,
    DriverInfo,
    GPUDevice,
    MachineProfile,
    PlatformInfo,
    TargetParseError,
    apply_target,
    detect_machine_profile,
    parse_target,
    profile_from_target,
)
from rigsolve.detect._command import CommandResult
from rigsolve.detect.gpu import GPUProbeResult
from rigsolve.detect.installed import InstalledProbeResult
from rigsolve.detect.model import InstalledEnvironment
from rigsolve.detect.platform import PlatformProbeResult
from rigsolve.detect.toolkit import ToolkitProbeResult


def test_parse_documented_target_string() -> None:
    target = parse_target("A100,driver=550.54,python=3.11,linux")

    assert target.gpu_name == "A100"
    assert target.driver_version == "550.54"
    assert target.python_version == "3.11"
    assert target.os == "linux"

    profile = target.to_profile()
    assert profile.source == "target"
    assert profile.gpu_name == "A100"
    assert profile.compute_capability == "sm_80"
    assert profile.driver_version == "550.54"
    assert profile.max_cuda_runtime == "12.4"
    assert profile.platform.python_abi_tag == "cp311"
    assert profile.architecture == "x86_64"


def test_target_supports_explicit_axes_and_flags() -> None:
    profile = profile_from_target(
        "gpu=Custom Accelerator,sm=9.0,count=2,vram=80GB,driver=560.35.03,"
        "cuda=12.6,nvcc=12.4,cuda_home=/opt/cuda-12.4,python=3.12.2,"
        "arch=arm64,glibc=2.35,abi=true,wsl"
    )

    assert profile.gpu_count == 2
    assert profile.compute_capabilities == ("sm_90",)
    assert profile.gpus[0].memory_total_mib == 81920
    assert profile.toolkit is not None and profile.toolkit.version == "12.4"
    assert profile.toolkit.path == "/opt/cuda-12.4"
    assert profile.max_cuda_runtime == "12.6"
    assert profile.platform.is_wsl is True
    assert profile.platform.manylinux_tag == "manylinux_2_35_aarch64"
    assert profile.cxx11_abi is True


def test_cpu_target_and_quoted_gpu_name() -> None:
    cpu = profile_from_target("cpu,python=3.12")
    assert cpu.gpus == ()
    assert any(issue.code == "explicit-cpu-target" for issue in cpu.issues)
    quoted = parse_target('"NVIDIA Prototype, Engineering Sample",linux')
    assert quoted.gpu_name == "NVIDIA Prototype, Engineering Sample"


def test_wsl_driver_uses_windows_host_compatibility_mapping() -> None:
    profile = profile_from_target("A100,driver=560.70,wsl")

    assert profile.max_cuda_runtime == "12.5"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "A100,driver=banana",
        "A100,python=312",
        "A100,driver=550,driver=560",
        "A100,mystery=yes",
        "A100,,linux",
    ],
)
def test_invalid_targets_are_actionable(value: str) -> None:
    with pytest.raises(TargetParseError):
        parse_target(value)


def test_target_overlay_changes_only_explicit_fields() -> None:
    base = MachineProfile(
        gpus=(GPUDevice(0, "NVIDIA T4", "sm_75", 15360),),
        driver=DriverInfo("470.239", "11.4"),
        platform=PlatformInfo(
            os="linux",
            architecture="x86_64",
            python_version="3.10.14",
            python_abi_tag="cp310",
        ),
    )

    target = apply_target(base, "python=3.12")

    assert target.gpus == base.gpus
    assert target.driver == base.driver
    assert target.python_version == "3.12"
    assert target.platform.python_abi_tag == "cp312"


def test_cross_os_overlay_clears_linux_only_and_container_facts() -> None:
    base = MachineProfile(
        platform=PlatformInfo(
            os="linux",
            architecture="x86_64",
            glibc_version="2.35",
            manylinux_tag="manylinux_2_35_x86_64",
            is_container=True,
            container_runtime="docker",
        )
    )

    target = apply_target(base, "windows,container=false")

    assert target.platform.os == "windows"
    assert target.platform.glibc_version is None
    assert target.platform.manylinux_tag is None
    assert target.platform.is_container is False
    assert target.platform.container_runtime is None


def test_profile_json_round_trip_and_immutability() -> None:
    profile = profile_from_target("RTX 4090,driver=560.35.03,python=3.12,linux")
    restored = MachineProfile.from_json(profile.to_json())

    assert restored == profile
    with pytest.raises(FrozenInstanceError):
        profile.source = "local"  # type: ignore[misc]


def test_detect_target_does_not_touch_local_probes() -> None:
    def forbidden_runner(args: object, timeout: float) -> object:
        raise AssertionError("local command probe was called")

    profile = detect_machine_profile(
        target="A100,driver=550.54,python=3.11,linux",
        runner=forbidden_runner,  # type: ignore[arg-type]
        distributions=lambda: (_ for _ in ()).throw(AssertionError("metadata probe was called")),
    )

    assert profile.source == "target"
    assert profile.compute_capability == "sm_80"


def test_local_profile_orchestrates_probe_results(monkeypatch: object) -> None:
    platform_result = PlatformProbeResult(
        PlatformInfo(
            os="linux",
            architecture="x86_64",
            python_version="3.12.4",
            python_abi_tag="cp312",
            is_wsl=False,
        ),
        (DetectionIssue("platform", "fixture-platform", "fixture", "info"),),
    )
    gpu_result = GPUProbeResult(
        devices=(GPUDevice(0, "NVIDIA RTX 4090", "sm_89", 24564),),
        driver_version="560.35.03",
        nvidia_smi_available=True,
        issues=(DetectionIssue("gpu", "fixture-gpu", "fixture", "info"),),
    )
    toolkit_result = ToolkitProbeResult(toolkit=CudaToolkit("12.4"), nvcc_available=True)
    installed_result = InstalledProbeResult(environment=InstalledEnvironment())

    monkeypatch.setattr(profile_module, "detect_platform", lambda **kwargs: platform_result)  # type: ignore[attr-defined]
    monkeypatch.setattr(profile_module, "detect_gpus", lambda **kwargs: gpu_result)  # type: ignore[attr-defined]
    monkeypatch.setattr(profile_module, "detect_nvcc", lambda **kwargs: toolkit_result)  # type: ignore[attr-defined]
    monkeypatch.setattr(profile_module, "detect_installed", lambda **kwargs: installed_result)  # type: ignore[attr-defined]

    def runner(args: object, timeout: float) -> CommandResult:
        raise AssertionError("stubbed probes should own command execution")

    profile = detect_machine_profile(runner=runner, distributions=lambda: ())  # type: ignore[arg-type]

    assert profile.gpu_name == "NVIDIA RTX 4090"
    assert profile.max_cuda_runtime == "12.6"
    assert profile.cuda_toolkit_version == "12.4"
    assert [issue.code for issue in profile.issues] == ["fixture-platform", "fixture-gpu"]


def test_local_profile_can_skip_installed_enumeration(monkeypatch: object) -> None:
    monkeypatch.setattr(  # type: ignore[attr-defined]
        profile_module,
        "detect_platform",
        lambda **kwargs: PlatformProbeResult(PlatformInfo(os="windows")),
    )
    monkeypatch.setattr(profile_module, "detect_gpus", lambda **kwargs: GPUProbeResult())  # type: ignore[attr-defined]
    monkeypatch.setattr(  # type: ignore[attr-defined]
        profile_module,
        "detect_nvcc",
        lambda **kwargs: ToolkitProbeResult(),
    )

    profile = detect_machine_profile(include_installed=False)

    assert profile.installed == InstalledEnvironment()
