"""Optional CUDA toolkit discovery through ``nvcc``."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass

from ._command import CommandRunner, run_command
from .model import CudaToolkit, DetectionIssue


@dataclass(frozen=True, slots=True)
class ToolkitProbeResult:
    toolkit: CudaToolkit | None = None
    nvcc_available: bool = False
    issues: tuple[DetectionIssue, ...] = ()


_RELEASE_RE = re.compile(r"\brelease\s+(\d+\.\d+)(?:\s*,\s*V([^\s,]+))?", re.IGNORECASE)
_BUILD_RE = re.compile(r"\bV(\d+\.\d+(?:\.\d+)*)\b")


def parse_nvcc_output(output: str, *, path: str | None = None) -> CudaToolkit | None:
    """Parse the stable ``nvcc --version`` release line."""

    match = _RELEASE_RE.search(output)
    if match is None:
        return None
    compiler_build = match.group(2)
    if compiler_build is None:
        build_match = _BUILD_RE.search(output)
        compiler_build = build_match.group(1) if build_match else None
    return CudaToolkit(version=match.group(1), compiler_build=compiler_build, path=path)


def detect_nvcc(
    *,
    runner: CommandRunner = run_command,
    timeout: float = 5.0,
    executable: str | None = None,
) -> ToolkitProbeResult:
    """Detect an optional CUDA compiler without treating absence as an error."""

    path = executable or shutil.which("nvcc")
    if path is None:
        return ToolkitProbeResult(
            issues=(
                DetectionIssue(
                    "toolkit",
                    "nvcc-not-found",
                    "nvcc is not available; source builds may not be possible",
                    "info",
                ),
            )
        )
    try:
        result = runner((path, "--version"), timeout)
    except FileNotFoundError:
        return ToolkitProbeResult(
            issues=(
                DetectionIssue(
                    "toolkit",
                    "nvcc-not-found",
                    "nvcc disappeared while it was being probed",
                    "info",
                ),
            )
        )
    except subprocess.TimeoutExpired:
        return ToolkitProbeResult(
            nvcc_available=True,
            issues=(
                DetectionIssue("toolkit", "nvcc-timeout", "nvcc did not respond before timeout"),
            ),
        )
    except OSError as exc:
        return ToolkitProbeResult(
            issues=(DetectionIssue("toolkit", "nvcc-error", f"could not run nvcc: {exc}"),)
        )
    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        return ToolkitProbeResult(
            nvcc_available=True,
            issues=(
                DetectionIssue(
                    "toolkit",
                    "nvcc-failed",
                    f"nvcc exited with {result.returncode}: {details or 'no details'}",
                ),
            ),
        )
    toolkit = parse_nvcc_output(f"{result.stdout}\n{result.stderr}", path=path)
    if toolkit is None:
        return ToolkitProbeResult(
            nvcc_available=True,
            issues=(
                DetectionIssue(
                    "toolkit", "nvcc-parse-error", "nvcc output did not contain a CUDA release"
                ),
            ),
        )
    return ToolkitProbeResult(toolkit=toolkit, nvcc_available=True)


detect_toolkit = detect_nvcc
