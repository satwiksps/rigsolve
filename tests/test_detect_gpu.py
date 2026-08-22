from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from rigsolve.detect._command import CommandResult
from rigsolve.detect.gpu import (
    FULL_QUERY_FIELDS,
    LEGACY_QUERY_FIELDS,
    compute_capability_from_name,
    detect_gpus,
    parse_nvidia_smi_csv,
)

FIXTURES = Path(__file__).parent / "fixtures" / "detect"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_single_gpu_fixture() -> None:
    devices = parse_nvidia_smi_csv(fixture("nvidia_smi_rtx4090.csv"))

    assert len(devices) == 1
    assert devices[0].name == "NVIDIA GeForce RTX 4090"
    assert devices[0].compute_capability == "sm_89"
    assert devices[0].memory_total_mib == 24564
    assert devices[0].uuid == "GPU-8be5f6a1-f4f9-4ca2-8abc-1db5f49b0123"


def test_parse_multi_gpu_fixture_preserves_each_device() -> None:
    devices = parse_nvidia_smi_csv(fixture("nvidia_smi_multi_a100.csv"))

    assert [device.index for device in devices] == [0, 1]
    assert {device.compute_capability for device in devices} == {"sm_80"}
    assert [device.memory_total_mib for device in devices] == [81920, 81920]


def test_legacy_output_uses_conservative_name_lookup() -> None:
    devices = parse_nvidia_smi_csv(fixture("nvidia_smi_legacy.csv"))

    assert devices[0].compute_capability == "sm_75"
    assert compute_capability_from_name("an unknown accelerator") is None


def test_no_gpu_fixture_is_not_a_parse_failure() -> None:
    assert parse_nvidia_smi_csv(fixture("nvidia_smi_no_gpu.txt"), fields=FULL_QUERY_FIELDS) == ()


def test_probe_falls_back_when_compute_cap_query_is_unsupported() -> None:
    calls: list[tuple[str, ...]] = []

    def runner(args: object, timeout: float) -> CommandResult:
        command = tuple(str(value) for value in args)  # type: ignore[arg-type]
        calls.append(command)
        if len(calls) == 1:
            return CommandResult(command, 2, stderr="Field compute_cap is not a valid field")
        output = "0, Tesla T4, GPU-fixture, 15360, 470.239.06\n"
        return CommandResult(command, 0, stdout=output)

    result = detect_gpus(runner=runner)

    assert result.nvidia_smi_available is True
    assert result.devices[0].compute_capability == "sm_75"
    assert result.driver_version == "470.239.06"
    assert FULL_QUERY_FIELDS[3] in calls[0][1]
    assert LEGACY_QUERY_FIELDS[3] in calls[1][1]


def test_missing_nvidia_smi_degrades_to_unknown() -> None:
    def runner(args: object, timeout: float) -> CommandResult:
        raise FileNotFoundError("nvidia-smi")

    result = detect_gpus(runner=runner)

    assert result.devices == ()
    assert result.driver_version is None
    assert result.nvidia_smi_available is False
    assert result.issues[0].code == "nvidia-smi-not-found"


def test_failed_no_device_probe_is_informational() -> None:
    def runner(args: object, timeout: float) -> CommandResult:
        command = tuple(str(value) for value in args)  # type: ignore[arg-type]
        return CommandResult(command, 9, stderr="No devices were found")

    result = detect_gpus(runner=runner)

    assert result.devices == ()
    assert result.issues[0].code == "no-gpu"
    assert result.issues[0].severity == "info"


def test_successful_full_probe_and_multiple_driver_warning() -> None:
    output = (
        "0, NVIDIA A100-SXM4-80GB, GPU-one, 8.0, 81920, 535.104.05\n"
        "1, NVIDIA A100-SXM4-80GB, GPU-two, 8.0, 81920, 535.105.00\n"
    )

    def runner(args: object, timeout: float) -> CommandResult:
        command = tuple(str(value) for value in args)  # type: ignore[arg-type]
        return CommandResult(command, 0, stdout=output)

    result = detect_gpus(runner=runner)

    assert len(result.devices) == 2
    assert result.driver_version == "535.104.05"
    assert result.issues[0].code == "multiple-driver-versions"


@pytest.mark.parametrize(
    ("failure", "code", "available"),
    [
        (subprocess.TimeoutExpired("nvidia-smi", 1), "nvidia-smi-timeout", True),
        (OSError("permission denied"), "nvidia-smi-error", False),
    ],
)
def test_gpu_command_failures_degrade(failure: Exception, code: str, available: bool) -> None:
    def runner(args: object, timeout: float) -> CommandResult:
        raise failure

    result = detect_gpus(runner=runner)

    assert result.nvidia_smi_available is available
    assert result.issues[0].code == code


def test_generic_nonzero_gpu_exit_is_reported() -> None:
    def runner(args: object, timeout: float) -> CommandResult:
        command = tuple(str(value) for value in args)  # type: ignore[arg-type]
        return CommandResult(command, 13, stderr="driver communication failed")

    result = detect_gpus(runner=runner)

    assert result.devices == ()
    assert result.issues[0].code == "nvidia-smi-failed"


def test_headerless_parser_requires_fields() -> None:
    with pytest.raises(ValueError, match="fields are required"):
        parse_nvidia_smi_csv("0, NVIDIA T4, GPU-one, 7.5, 15360, 470.239")


def test_headerless_parser_rejects_scalar_fields() -> None:
    with pytest.raises(TypeError, match="sequence of field names"):
        parse_nvidia_smi_csv(
            "0, NVIDIA T4, GPU-one, 7.5, 15360, 470.239",
            fields="index,name,uuid,compute_cap,memory.total,driver_version",  # type: ignore[arg-type]
        )
