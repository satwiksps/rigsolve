"""Crash-isolated package smoke tests.

Imports happen in child interpreters. A broken native extension can therefore
segfault without taking down the diagnostic process that needs to explain it.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from packaging.utils import canonicalize_name

from rigsolve.errors import UserInputError
from rigsolve.verify.tiers import VerificationTier

_SENTINEL = "RIGSOLVE_RESULT="


@dataclass(frozen=True, slots=True)
class SmokeProbe:
    distribution: str
    module: str
    config_code: str | None = None
    gpu_code: str | None = None


@dataclass(frozen=True, slots=True)
class SmokeResult:
    package: str
    ok: bool
    tier: VerificationTier | None
    version: str | None = None
    details: dict[str, Any] | None = None
    error: str | None = None
    returncode: int = 0


PROBES: dict[str, SmokeProbe] = {
    "torch": SmokeProbe(
        distribution="torch",
        module="torch",
        config_code="""
config = {
    "module_version": getattr(module, "__version__", None),
    "cuda": getattr(getattr(module, "version", None), "cuda", None),
    "cxx11abi": getattr(getattr(module, "_C", None), "_GLIBCXX_USE_CXX11_ABI", None),
    "archs": list(module.cuda.get_arch_list()) if hasattr(module, "cuda") else [],
}
""",
        gpu_code="""
if not module.cuda.is_available():
    raise RuntimeError("torch.cuda.is_available() is false")
x = module.tensor([1.0, 2.0], device="cuda")
y = (x * 2).sum()
module.cuda.synchronize()
gpu = {"device": module.cuda.get_device_name(0), "value": float(y.cpu())}
""",
    ),
    "torchvision": SmokeProbe("torchvision", "torchvision"),
    "torchaudio": SmokeProbe("torchaudio", "torchaudio"),
    "flash-attn": SmokeProbe(
        distribution="flash-attn",
        module="flash_attn",
        config_code="""
import torch
config = {
    "module_version": getattr(module, "__version__", None),
    "torch_version": getattr(torch, "__version__", None),
    "torch_cuda": getattr(getattr(torch, "version", None), "cuda", None),
}
""",
        gpu_code="""
import torch
from flash_attn import flash_attn_func
q = torch.randn(1, 8, 2, 16, device="cuda", dtype=torch.float16)
out = flash_attn_func(q, q, q)
torch.cuda.synchronize()
gpu = {"shape": list(out.shape), "device": torch.cuda.get_device_name(0)}
""",
    ),
    "xformers": SmokeProbe("xformers", "xformers"),
    "bitsandbytes": SmokeProbe("bitsandbytes", "bitsandbytes"),
    "triton": SmokeProbe("triton", "triton"),
    "vllm": SmokeProbe("vllm", "vllm"),
    "transformers": SmokeProbe("transformers", "transformers"),
    "flashinfer-python": SmokeProbe(
        "flashinfer-python",
        "flashinfer",
        config_code='config = {"module_version": getattr(module, "__version__", None)}',
    ),
}


def _script(probe: SmokeProbe, run_gpu: bool) -> str:
    gpu_code = probe.gpu_code if run_gpu and probe.gpu_code else "gpu = None"
    config_code = probe.config_code or "config = {}"
    return f"""
import importlib
import importlib.metadata
import json
module = importlib.import_module({probe.module!r})
version = importlib.metadata.version({probe.distribution!r})
details = {{"module": {probe.module!r}}}
config = {{}}
{config_code}
details["config"] = config
gpu = None
{gpu_code}
details["gpu"] = gpu
print({_SENTINEL!r} + json.dumps({{"version": version, "details": details}}, sort_keys=True))
"""


def _parse_result(stdout: str) -> dict[str, Any] | None:
    for line in reversed(stdout.splitlines()):
        if line.startswith(_SENTINEL):
            try:
                parsed = json.loads(line[len(_SENTINEL) :])
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, dict) else None
    return None


Run = Callable[..., subprocess.CompletedProcess[str]]


def run_probe(
    probe: SmokeProbe,
    *,
    run_gpu: bool = True,
    timeout: float = 60.0,
    runner: Run = subprocess.run,
) -> SmokeResult:
    try:
        process = runner(
            [sys.executable, "-c", _script(probe, run_gpu)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return SmokeResult(
            package=probe.distribution,
            ok=False,
            tier=None,
            error=f"probe exceeded {timeout:g}s timeout",
            returncode=124,
        )
    except OSError as exc:
        return SmokeResult(
            package=probe.distribution,
            ok=False,
            tier=None,
            error=f"could not start probe: {exc}",
            returncode=126,
        )
    payload = _parse_result(process.stdout)
    if process.returncode != 0 or payload is None:
        error = process.stderr.strip()
        if error.startswith("Traceback (most recent call last):"):
            error = error.splitlines()[-1].strip()
        error = error or "probe exited without a structured result"
        return SmokeResult(
            package=probe.distribution,
            ok=False,
            tier=None,
            error=error[-4000:],
            returncode=process.returncode,
        )
    gpu_ran = bool((payload.get("details") or {}).get("gpu"))
    tier = VerificationTier.RUNS if gpu_ran else VerificationTier.IMPORTS
    return SmokeResult(
        package=probe.distribution,
        ok=True,
        tier=tier,
        version=str(payload.get("version")),
        details=payload.get("details"),
        returncode=process.returncode,
    )


def verify_packages(
    packages: Sequence[str] | None = None,
    *,
    run_gpu: bool = True,
    timeout: float = 60.0,
) -> tuple[SmokeResult, ...]:
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be a finite positive number")
    if isinstance(packages, (str, bytes)):
        raise TypeError("packages must be a sequence of package names, not a string")
    names = tuple(PROBES) if packages is None else tuple(packages)
    results = []
    for name in names:
        normalized = canonicalize_name(name)
        probe = PROBES.get(normalized)
        if probe is None:
            raise UserInputError(
                f"unsupported verification package {normalized!r}; choose one of: "
                + ", ".join(sorted(PROBES))
            )
        results.append(run_probe(probe, run_gpu=run_gpu, timeout=timeout))
    return tuple(results)


def contribution_payload(
    results: Sequence[SmokeResult],
    machine_profile: dict[str, Any],
    matrix_version: str,
) -> str:
    """Create a local, inspectable payload. This function never transmits it."""

    payload = {
        "schema_version": 1,
        "matrix_version": matrix_version,
        "machine": machine_profile,
        "results": [
            {
                "package": result.package,
                "version": result.version,
                "ok": result.ok,
                "tier": None if result.tier is None else int(result.tier),
                "details": result.details,
                "error": result.error,
            }
            for result in results
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"
