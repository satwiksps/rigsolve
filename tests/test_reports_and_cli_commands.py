from __future__ import annotations

import json
from pathlib import Path

from tests.test_resolver import MATRIX

from rigsolve.cli import main
from rigsolve.detect import (
    DetectionIssue,
    DriverInfo,
    GPUDevice,
    InstalledEnvironment,
    InstalledPackage,
    MachineProfile,
    PlatformInfo,
    TorchBuild,
)
from rigsolve.diagnose import CheckReport, Violation
from rigsolve.matrix import dump_matrix, load_bundled
from rigsolve.report import format_profile, format_smoke_results
from rigsolve.verify.smoke import SmokeResult
from rigsolve.verify.tiers import VerificationTier


def matrix_path(tmp_path: Path) -> Path:
    path = tmp_path / "matrix.toml"
    path.write_text(MATRIX, encoding="utf-8")
    return path


def rich_profile() -> MachineProfile:
    return MachineProfile(
        gpus=(GPUDevice(0, "RTX 4090", "sm_89", 24564),),
        driver=DriverInfo("560.35", "12.6"),
        platform=PlatformInfo(
            os="linux",
            architecture="x86_64",
            glibc_version="2.35",
            python_version="3.12",
            python_abi_tag="cp312",
            is_container=True,
            container_runtime="docker",
        ),
        installed=InstalledEnvironment(
            packages=(InstalledPackage("torch", "2.6.0"),),
            torch=TorchBuild("2.6.0", "12.4.1", False, ("sm_89",)),
        ),
        issues=(DetectionIssue("toolkit", "missing", "nvcc not found", "info"),),
    )


def test_profile_and_smoke_reports_cover_success_failure_and_unknown() -> None:
    text = format_profile(rich_profile())
    assert "RTX 4090" in text
    assert "driver supports CUDA" in text
    assert "cxx11abi FALSE" in text
    assert "docker" in text
    assert "nvcc not found" in text

    results = (
        SmokeResult("torch", True, VerificationTier.RUNS, version="2.6.0"),
        SmokeResult(
            "flash-attn",
            False,
            VerificationTier.INSTALLS,
            error="undefined symbol",
        ),
    )
    output = format_smoke_results(results)
    assert "GPU-tested" in output
    assert "undefined symbol" in output
    assert "No supported" in format_smoke_results(())


def test_detect_cli_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr("rigsolve.cli.detect_machine_profile", rich_profile)
    assert main(("detect", "--json")) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["gpus"][0]["compute_capability"] == "sm_89"


def test_check_cli_prints_repair_status(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr("rigsolve.cli.detect_machine_profile", rich_profile)
    monkeypatch.setattr(
        "rigsolve.cli.check_environment",
        lambda *args, **kwargs: CheckReport(
            violations=(
                Violation(
                    "cuda-line-mismatch",
                    ("torch", "flash-attn"),
                    "CUDA lines disagree",
                    fix="resolve both",
                ),
            )
        ),
    )
    code = main(("--matrix", str(matrix_path(tmp_path)), "check", "--fix"))
    output = capsys.readouterr().out
    assert code == 2
    assert "CUDA lines disagree" in output
    assert "No automatic repair plan" in output


def test_verify_cli_writes_inspectable_contribution(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr("rigsolve.cli.detect_machine_profile", rich_profile)
    monkeypatch.setattr(
        "rigsolve.cli.verify_packages",
        lambda *args, **kwargs: (
            SmokeResult("torch", True, VerificationTier.IMPORTS, version="2.6.0"),
        ),
    )
    destination = tmp_path / "verification.json"
    code = main(
        (
            "--matrix",
            str(matrix_path(tmp_path)),
            "verify",
            "--package",
            "torch",
            "--no-gpu",
            "--contribute",
            "--contribution-file",
            str(destination),
        )
    )
    assert code == 0
    assert json.loads(destination.read_text(encoding="utf-8"))["results"][0]["tier"] == 2
    assert "nothing was uploaded" in capsys.readouterr().err


def test_verify_cli_with_no_supported_installed_packages_is_a_clean_noop(
    monkeypatch, tmp_path, capsys
) -> None:
    profile = MachineProfile(
        platform=PlatformInfo(os="linux", architecture="x86_64", python_version="3.12")
    )
    monkeypatch.setattr("rigsolve.cli.detect_machine_profile", lambda: profile)
    assert main(("--matrix", str(matrix_path(tmp_path)), "verify")) == 0
    assert "No supported installed packages" in capsys.readouterr().out


def test_matrix_show_add_and_doctor_commands(monkeypatch, tmp_path, capsys) -> None:
    source = matrix_path(tmp_path)
    assert main(("--matrix", str(source), "matrix", "show", "--package", "torch", "--json")) == 0
    assert "TorchBuildFact" in capsys.readouterr().out

    bundled = tmp_path / "bundled.toml"
    bundled.write_text(dump_matrix(load_bundled()), encoding="utf-8")
    assert (
        main(("--matrix", str(bundled), "matrix", "show", "--package", "flash_attn", "--json")) == 0
    )
    assert "KnownBrokenFact" in capsys.readouterr().out

    destination = tmp_path / "merged.toml"
    assert (
        main(
            (
                "--matrix",
                str(source),
                "matrix",
                "add",
                str(source),
                "--destination",
                str(destination),
            )
        )
        == 0
    )
    assert destination.exists()
    assert "Validated and wrote" in capsys.readouterr().out

    monkeypatch.setattr("rigsolve.cli.detect_machine_profile", rich_profile)
    assert main(("--matrix", str(source), "doctor")) == 0
    doctor = capsys.readouterr().out
    assert "matrix:" in doctor
    assert "platform:" in doctor
