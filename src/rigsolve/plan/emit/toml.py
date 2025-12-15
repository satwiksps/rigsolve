from __future__ import annotations

from rigsolve.plan.emit._common import scalar, toml_string
from rigsolve.plan.install import InstallPlan


def emit_toml(plan: InstallPlan) -> str:
    lines = [
        "lock-version = 1",
        f"matrix-version = {toml_string(plan.matrix_version)}",
        f"matrix-digest = {toml_string(plan.matrix_digest)}",
        f"preference = {toml_string(plan.preference)}",
        f"weakest-tier = {plan.weakest_tier}",
        "constraint-tiers = [" + ", ".join(str(tier) for tier in plan.constraint_tiers) + "]",
        "requested = [" + ", ".join(toml_string(item) for item in plan.requested) + "]",
    ]
    if plan.warnings:
        lines.append("warnings = [" + ", ".join(toml_string(item) for item in plan.warnings) + "]")
    if plan.target:
        lines.extend(("", "[target]"))
        for key in sorted(plan.target):
            lines.append(f"{key.replace('_', '-')} = {scalar(plan.target[key])}")
    for step in plan.ordered_steps():
        lines.extend(
            (
                "",
                "[[package]]",
                f"name = {toml_string(step.package)}",
                f"version = {toml_string(step.version)}",
                f"tier = {step.tier}",
                f"source-build = {scalar(step.source_build)}",
            )
        )
        for key, value in (
            ("url", step.artifact_url),
            ("sha256", step.artifact_sha256),
            ("index-url", step.index_url),
            ("cuda-line", step.cuda_line),
            ("torch", step.torch_version),
            ("python", step.python_tag),
            ("platform", step.platform_tag),
            ("build-estimate", step.build_estimate),
        ):
            if value is not None:
                lines.append(f"{key} = {toml_string(value)}")
        if step.cxx11_abi is not None:
            lines.append(f"cxx11abi = {scalar(step.cxx11_abi)}")
        if step.ram_gb_per_job is not None:
            lines.append(f"ram-gb-per-job = {step.ram_gb_per_job!r}")
        if step.dependencies:
            lines.append(
                "dependencies = ["
                + ", ".join(toml_string(item) for item in step.dependencies)
                + "]"
            )
        if step.build_requirements:
            lines.append(
                "build-requirements = ["
                + ", ".join(toml_string(item) for item in step.build_requirements)
                + "]"
            )
        if step.flags:
            lines.append("flags = [" + ", ".join(toml_string(item) for item in step.flags) + "]")
        if step.provenance:
            lines.append(
                "provenance = [" + ", ".join(toml_string(item) for item in step.provenance) + "]"
            )
        if step.environment:
            lines.append("[package.environment]")
            lines.extend(f"{key} = {toml_string(value)}" for key, value in step.environment)
    return "\n".join(lines) + "\n"
