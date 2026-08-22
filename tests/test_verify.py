from __future__ import annotations

import subprocess

import pytest

from rigsolve.errors import UserInputError
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


def test_malformed_sentinel_is_reported_without_raising() -> None:
    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(
            args[0],
            0,
            stdout="package banner\nRIGSOLVE_RESULT={not-json}\n",
            stderr="",
        )

    result = run_probe(SmokeProbe("demo", "demo"), runner=runner)
    assert not result.ok
    assert result.tier is None
    assert result.returncode == 0
    assert result.error == "probe exited without a structured result"


def test_native_crash_is_reported_without_raising() -> None:
    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], -1073741819, stdout="", stderr="native crash")

    result = run_probe(SmokeProbe("demo", "demo"), runner=runner)
    assert not result.ok
    assert result.tier is None
    assert result.returncode == -1073741819
    assert result.error == "native crash"


def test_python_traceback_is_reduced_to_its_final_exception() -> None:
    def runner(*args, **kwargs):
        stderr = (
            "Traceback (most recent call last):\n"
            '  File "<string>", line 1, in <module>\n'
            "ModuleNotFoundError: No module named 'missing_demo'\n"
        )
        return subprocess.CompletedProcess(args[0], 1, stdout="", stderr=stderr)

    result = run_probe(SmokeProbe("demo", "missing_demo"), runner=runner)
    assert not result.ok
    assert result.returncode == 1
    assert result.error == "ModuleNotFoundError: No module named 'missing_demo'"


def test_probe_spawn_failure_is_reported_without_raising() -> None:
    def runner(*args, **kwargs):
        raise FileNotFoundError("child interpreter missing")

    result = run_probe(SmokeProbe("demo", "demo"), runner=runner)
    assert not result.ok
    assert result.tier is None
    assert result.returncode == 126
    assert result.error == "could not start probe: child interpreter missing"


def test_unknown_package_is_reported_unsupported_without_guessing(monkeypatch) -> None:
    calls = []
    sentinel = object()

    def fake_probe(probe, **kwargs):
        calls.append(probe.distribution)
        return sentinel

    monkeypatch.setattr("rigsolve.verify.smoke.run_probe", fake_probe)
    with pytest.raises(UserInputError, match="unsupported verification package 'pillow'"):
        verify_packages(("pillow",), run_gpu=False)
    assert calls == []
    assert verify_packages(("torch",), run_gpu=False) == (sentinel,)
    assert calls == ["torch"]


def test_verify_rejects_invalid_timeout() -> None:
    for timeout in (0, -1, float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="timeout must be a finite positive number"):
            verify_packages((), timeout=timeout)


def test_verify_rejects_scalar_package_string() -> None:
    with pytest.raises(TypeError, match="packages must be a sequence of package names"):
        verify_packages("torch", run_gpu=False)


def test_explicit_empty_package_set_runs_no_probes() -> None:
    assert verify_packages(()) == ()


def test_flashinfer_distribution_uses_the_documented_import_name() -> None:
    assert PROBES["flashinfer-python"].module == "flashinfer"
