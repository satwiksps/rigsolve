"""Stable plain-text reports; colour is intentionally a presentation detail."""

from __future__ import annotations

from rigsolve.detect import MachineProfile
from rigsolve.verify.smoke import SmokeResult


def format_profile(profile: MachineProfile) -> str:
    if profile.gpus:
        gpu_parts = [
            ", ".join(gpu.name or f"GPU {gpu.index}" for gpu in profile.gpus),
            f"count {profile.gpu_count}",
        ]
        if profile.compute_capabilities:
            gpu_parts.append("/".join(profile.compute_capabilities))
    else:
        gpu_parts = ["No NVIDIA GPU detected"]
    if profile.driver_version:
        gpu_parts.append(f"driver {profile.driver_version}")
    if profile.max_cuda_runtime:
        gpu_parts.append(f"driver supports CUDA <= {profile.max_cuda_runtime}")

    platform_parts = [
        item
        for item in (
            profile.os,
            profile.architecture,
            f"glibc {profile.platform.glibc_version}" if profile.platform.glibc_version else None,
            f"Python {profile.python_version}" if profile.python_version else None,
            profile.platform.python_abi_tag,
        )
        if item
    ]
    if profile.platform.is_wsl:
        platform_parts.append("WSL")
    if profile.platform.is_container:
        platform_parts.append(profile.platform.container_runtime or "container")

    if profile.torch:
        torch = f"torch {profile.torch.version}"
        if profile.torch.cuda_version:
            torch += f" | CUDA {profile.torch.cuda_version}"
        if profile.torch.cxx11_abi is not None:
            torch += f" | cxx11abi {str(profile.torch.cxx11_abi).upper()}"
    else:
        torch = "torch: not installed (or static build metadata unavailable)"

    lines = [" | ".join(gpu_parts), " | ".join(platform_parts), torch]
    if profile.toolkit:
        lines.append(f"nvcc toolkit: {profile.toolkit.version}")
    for issue in profile.issues:
        lines.append(f"! {issue.component}: {issue.message}")
    return "\n".join(lines) + "\n"


def format_smoke_results(results: tuple[SmokeResult, ...]) -> str:
    if not results:
        return "No supported installed packages were found to verify.\n"
    lines = []
    for result in results:
        if result.ok:
            tier = result.tier
            if tier is None:
                lines.append(f"[ok] {result.package} {result.version or ''} | unclassified")
                continue
            lines.append(
                f"[ok] {result.package} {result.version or ''} | tier {int(tier)} ({tier.label})"
            )
        else:
            lines.append(f"[FAIL] {result.package} | {result.error or 'probe failed'}")
    return "\n".join(lines) + "\n"
