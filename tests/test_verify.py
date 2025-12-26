from __future__ import annotations

import subprocess

from rigsolve.verify.smoke import PROBES, SmokeProbe, run_probe, verify_packages
from rigsolve.verify.tiers import VerificationTier


def test_import_probe_parses_sentinel_after_package_noise() -> None:
    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(
            args[0],
            0,
            stdout='package banner\nRIGSOLVE_RESULT={"details":{"gpu":null},"version":"1.2.3"}\n',
            stderr="",
        )

    result = run_probe(SmokeProbe("demo", "demo"), runner=runner)
    assert result.ok
    assert result.version == "1.2.3"
    assert result.tier is VerificationTier.IMPORTS


def test_native_crash_is_reported_without_raising() -> None:
    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], -1073741819, stdout="", stderr="native crash")

    result = run_probe(SmokeProbe("demo", "demo"), runner=runner)
    assert not result.ok
    assert result.tier is None
    assert result.returncode == -1073741819
    assert result.error == "native crash"


def test_explicit_empty_package_set_runs_no_probes() -> None:
    assert verify_packages(()) == ()


def test_flashinfer_distribution_uses_the_documented_import_name() -> None:
    assert PROBES["flashinfer-python"].module == "flashinfer"
