from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from rigsolve.detect.model import (
    CudaToolkit,
    DetectionIssue,
    DriverInfo,
    GPUDevice,
    InstalledEnvironment,
    InstalledPackage,
    MachineProfile,
    PlatformInfo,
    ProfileValidationError,
    TorchBuild,
    normalise_compute_capability,
    optional_text,
)


def test_full_profile_round_trip_exercises_every_nested_model() -> None:
    torch = TorchBuild(
        version="2.6.0+cu124",
        cuda_version="12.4",
        cxx11_abi=True,
        archs=("8.9", "sm_80", "sm_89"),
        location="/venv/torch",
        evidence=("version.py", "version.py", "cmake"),
    )
    environment = InstalledEnvironment(
        packages=(
            InstalledPackage(
                name="flash_attn",
                version="2.8.3+cu12torch2.8cxx11abiFALSE",
                location="/venv",
                cuda_version="12.1",
                torch_version="2.8",
                cxx11_abi=False,
                wheel_tags=("cp312-cp312-linux_x86_64",),
                source_build=False,
            ),
            InstalledPackage(name="torch", version="2.6.0+cu124"),
        ),
        torch=torch,
    )
    profile = MachineProfile(
        gpus=(
            GPUDevice.from_dict(
                {
                    "index": "1",
                    "name": "NVIDIA L4",
                    "sm": "8.9",
                    "vram_mib": "23034",
                    "uuid": "GPU-two",
                }
            ),
            GPUDevice(0, "NVIDIA L4", "sm_89", 23034, "GPU-one"),
        ),
        driver=DriverInfo("560.35.03", "12.6"),
        toolkit=CudaToolkit("12.4", "12.4.131", "/usr/local/cuda/bin/nvcc"),
        platform=PlatformInfo(
            os="linux",
            kernel="6.8.0",
            architecture="x86_64",
            glibc_version="2.35",
            manylinux_tag="manylinux_2_35_x86_64",
            python_version="3.12.4",
            python_implementation="cpython",
            python_abi_tag="cp312",
            python_soabi="cpython-312-x86_64-linux-gnu",
            is_container=True,
            container_runtime="docker",
        ),
        installed=environment,
        issues=(DetectionIssue("gpu", "fixture-note", "recorded fixture", "info"),),
        source="fixture",
    )

    restored = MachineProfile.from_json(profile.to_json(indent=None))

    assert restored == profile
    assert restored.has_gpu is True
    assert restored.gpu_count == 2
    assert restored.gpu_name == "NVIDIA L4"
    assert restored.compute_capability == "sm_89"
    assert restored.compute_capabilities == ("sm_89",)
    assert restored.driver_version == "560.35.03"
    assert restored.cuda_toolkit_version == "12.4"
    assert restored.python_version == "3.12.4"
    assert restored.os == "linux"
    assert restored.torch == torch
    assert restored.cxx11_abi is True
    assert restored.installed.get("FLASH.ATTN") is not None
    assert restored.installed.get("missing") is None
    assert restored.installed.packages[0].cuda_line == "12"
    assert restored.toolkit is not None
    assert restored.toolkit.to_dict()["compiler_build"] == "12.4.131"
    assert restored.issues[0].to_dict()["severity"] == "info"


def test_alias_heavy_dict_profile_parsing() -> None:
    profile = MachineProfile.from_dict(
        {
            "schema_version": 1,
            "source": "unknown",
            "gpus": [{"name": "T4", "memory_mib": 15360}],
            "driver": {"driver_version": "470.239", "cuda_runtime": "11.4"},
            "toolkit": {"version": "11.8", "build": "11.8.89"},
            "platform": {
                "system": "linux",
                "release": "6.1",
                "arch": "x86_64",
                "glibc": "2.31",
                "manylinux": "manylinux_2_31_x86_64",
                "python": "3.10.14",
                "implementation": "cpython",
                "python_abi": "cp310",
                "soabi": "cpython-310-x86_64-linux-gnu",
                "is_wsl": "false",
                "is_container": "true",
            },
            "installed": {
                "packages": [
                    {
                        "name": "demo_pkg",
                        "version": "1.0",
                        "cuda": "11.8",
                        "torch": "2.1",
                        "cxx11_abi": "yes",
                        "wheel_tags": ["py3-none-any"],
                        "source_build": 0,
                    }
                ],
                "torch": {
                    "version": "2.1.0",
                    "cuda": "11.8",
                    "cxx11_abi": 0,
                    "archs": ["75"],
                    "evidence": ["fixture"],
                },
            },
            "issues": [{"component": "fixture", "code": "note", "message": "hello"}],
        }
    )

    assert profile.compute_capability is None
    assert profile.installed.packages[0].normalized_name == "demo-pkg"
    assert profile.installed.packages[0].cuda_version == "11.8"
    assert profile.installed.packages[0].source_build is False
    assert profile.platform.is_container is True
    assert profile.torch is not None and profile.torch.archs == ("sm_75",)


@pytest.mark.parametrize("value", ["", "unknown", "N/A", None])
def test_common_unknown_sentinels(value: object) -> None:
    assert optional_text(value) is None


@pytest.mark.parametrize("value", ["sm_89", "compute_89", "8.9", "089"])
def test_compute_capability_normalization(value: str) -> None:
    assert normalise_compute_capability(value) == "sm_89"


@pytest.mark.parametrize(
    "factory",
    [
        lambda: GPUDevice(-1),
        lambda: GPUDevice(0, memory_total_mib=-1),
        lambda: DetectionIssue("", "code", "message"),
        lambda: DetectionIssue("gpu", "code", "message", "fatal"),
        lambda: CudaToolkit("unknown"),
        lambda: InstalledPackage("", "1"),
        lambda: TorchBuild(""),
        lambda: MachineProfile(source="remote"),
    ],
)
def test_model_validation_rejects_corrupt_values(factory: object) -> None:
    with pytest.raises(ProfileValidationError):
        factory()  # type: ignore[operator]


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        "[]",
        '{"schema_version": 99}',
        '{"gpus": {}}',
        '{"issues": {}}',
        '{"driver": []}',
    ],
)
def test_corrupt_profile_json_is_rejected(payload: str) -> None:
    with pytest.raises(ProfileValidationError):
        MachineProfile.from_json(payload)


def test_frozen_nested_models_cannot_be_mutated() -> None:
    driver = DriverInfo("560.35", "12.6")
    with pytest.raises(FrozenInstanceError):
        driver.version = "535"  # type: ignore[misc]
