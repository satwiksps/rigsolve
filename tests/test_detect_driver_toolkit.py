from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

import rigsolve.detect.toolkit as toolkit_module
from rigsolve.detect._command import CommandResult
from rigsolve.detect.driver import (
    driver_supports_runtime,
    max_cuda_runtime_for_driver,
    parse_version_tuple,
)
from rigsolve.detect.toolkit import detect_nvcc, parse_nvcc_output

FIXTURES = Path(__file__).parent / "fixtures" / "detect"


@pytest.mark.parametrize(
    ("driver", "expected"),
    [
        ("580.65.06", "13.0"),
        ("575.51.03", "12.9"),
        ("560.35.03", "12.6"),
        ("550.54.14", "12.4"),
        ("535.104.05", "12.2"),
        ("520.61.05", "11.8"),
        ("450.80.02", "11.0"),
        ("not-a-version", None),
        (None, None),
    ],
)
def test_linux_driver_runtime_table(driver: str | None, expected: str | None) -> None:
    assert max_cuda_runtime_for_driver(driver) == expected


def test_truncated_driver_branch_is_treated_as_that_release_family() -> None:
    assert max_cuda_runtime_for_driver("550.54") == "12.4"
    assert max_cuda_runtime_for_driver("560.28") == "12.6"


def test_windows_driver_thresholds_are_distinct() -> None:
    assert max_cuda_runtime_for_driver("560.70", os_name="windows") == "12.5"
    assert max_cuda_runtime_for_driver("560.76", os_name="windows") == "12.6"


def test_driver_support_status_preserves_unknown() -> None:
    assert driver_supports_runtime("535.104", "12.2") is True
    assert driver_supports_runtime("535.104", "12.4") is True
    assert driver_supports_runtime("535.104", "12.4", minor_compatibility=False) is False
    assert driver_supports_runtime("520.61", "12.0") is False
    assert driver_supports_runtime(None, "12.4") is None
    assert parse_version_tuple("NVIDIA 560.35.03-1") == (560, 35, 3)


def test_parse_nvcc_fixture() -> None:
    payload = (FIXTURES / "nvcc_12_4.txt").read_text(encoding="utf-8")
    toolkit = parse_nvcc_output(payload, path="/usr/local/cuda/bin/nvcc")

    assert toolkit is not None
    assert toolkit.version == "12.4"
    assert toolkit.compiler_build == "12.4.131"
    assert toolkit.path == "/usr/local/cuda/bin/nvcc"


def test_nvcc_probe_is_optional_and_graceful() -> None:
    payload = (FIXTURES / "nvcc_12_4.txt").read_text(encoding="utf-8")

    def runner(args: object, timeout: float) -> CommandResult:
        command = tuple(str(value) for value in args)  # type: ignore[arg-type]
        return CommandResult(command, 0, stdout=payload)

    result = detect_nvcc(runner=runner, executable="nvcc-fixture")

    assert result.nvcc_available is True
    assert result.toolkit is not None
    assert result.toolkit.version == "12.4"


def test_unparseable_nvcc_is_an_issue_not_an_exception() -> None:
    def runner(args: object, timeout: float) -> CommandResult:
        command = tuple(str(value) for value in args)  # type: ignore[arg-type]
        return CommandResult(command, 0, stdout="unexpected vendor output")

    result = detect_nvcc(runner=runner, executable="nvcc-fixture")

    assert result.toolkit is None
    assert result.issues[0].code == "nvcc-parse-error"


def test_missing_nvcc_is_informational(monkeypatch: Any) -> None:
    monkeypatch.setattr(toolkit_module.shutil, "which", lambda name: None)

    result = detect_nvcc()

    assert result.nvcc_available is False
    assert result.issues[0].code == "nvcc-not-found"


@pytest.mark.parametrize(
    ("failure", "code", "available"),
    [
        (FileNotFoundError("gone"), "nvcc-not-found", False),
        (subprocess.TimeoutExpired("nvcc", 1), "nvcc-timeout", True),
        (OSError("denied"), "nvcc-error", False),
    ],
)
def test_nvcc_command_failures_degrade(failure: Exception, code: str, available: bool) -> None:
    def runner(args: object, timeout: float) -> CommandResult:
        raise failure

    result = detect_nvcc(runner=runner, executable="nvcc-fixture")

    assert result.nvcc_available is available
    assert result.issues[0].code == code


def test_nonzero_nvcc_exit_is_reported() -> None:
    def runner(args: object, timeout: float) -> CommandResult:
        command = tuple(str(value) for value in args)  # type: ignore[arg-type]
        return CommandResult(command, 2, stderr="compiler is broken")

    result = detect_nvcc(runner=runner, executable="nvcc-fixture")

    assert result.nvcc_available is True
    assert result.issues[0].code == "nvcc-failed"
