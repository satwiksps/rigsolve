from __future__ import annotations

import json
import shlex

from rigsolve.errors import UserInputError
from rigsolve.plan.install import InstallPlan, InstallStep


def _uv_pip_command(step: InstallStep) -> str:
    parts = ["uv", "pip", "install", "--system", "--python", "/usr/local/bin/python"]
    if step.index_url:
        parts.extend(("--index-url", step.index_url))
    parts.extend(step.flags)
    parts.append(step.requirement)
    return shlex.join(parts)


def emit_dockerfile(plan: InstallPlan) -> str:
    platform = str(plan.target.get("platform", "linux")).lower()
    if not platform.startswith("linux"):
        raise UserInputError("Docker output currently requires a Linux target")
    cuda_value = plan.target.get("cuda_runtime") or next(
        (step.cuda_line for step in plan.steps if step.cuda_line), None
    )
    cuda = str(cuda_value) if cuda_value is not None else None
    cuda_tag = None if cuda is None else (cuda if "." in cuda else f"{cuda}.0.0")
    python = str(plan.target.get("python_version", "3.12"))
    image_kind = "devel" if any(step.source_build for step in plan.steps) else "runtime"
    lines = [
        "# syntax=docker/dockerfile:1",
        f"# Generated from rigsolve matrix {plan.matrix_version}; weakest evidence tier {plan.weakest_tier}.",
        "FROM ghcr.io/astral-sh/uv:0.12.5@sha256:"
        "e85be844203885286c60ffad8a858d48afb6c5a5c237ca0e67f12e74b8f174b1 AS uv",
        (
            f"FROM nvidia/cuda:{cuda_tag}-{image_kind}-ubuntu22.04"
            if cuda_tag is not None
            else f"FROM python:{python}-slim"
        ),
        "COPY --from=uv /uv /uvx /bin/",
        "",
        "ENV DEBIAN_FRONTEND=noninteractive \\",
        "    PIP_DISABLE_PIP_VERSION_CHECK=1 \\",
        "    PYTHONDONTWRITEBYTECODE=1 \\",
        "    UV_PYTHON_INSTALL_DIR=/opt/uv/python \\",
        "    UV_PYTHON_PREFERENCE=only-managed",
        "RUN apt-get update \\",
        "    && apt-get install -y --no-install-recommends ca-certificates \\",
        "    && rm -rf /var/lib/apt/lists/*",
    ]
    if cuda_tag is not None:
        lines[-1] += " \\"
        lines.extend(
            (
                f"    && uv python install {python} \\",
                f'    && ln -sf "$(uv python find {python})" /usr/local/bin/python',
            )
        )
    for warning in plan.warnings:
        lines.append(f"# WARNING: {warning}")
    for step in plan.ordered_steps():
        for key, value in step.environment:
            lines.append(f"ENV {key}={json.dumps(value)}")
        if step.source_build:
            guidance = [step.build_estimate or "duration varies"]
            if step.ram_gb_per_job is not None:
                guidance.append(f"~{step.ram_gb_per_job:g} GiB RAM per compiler job")
            lines.append(f"# SOURCE BUILD ({'; '.join(guidance)})")
            if step.build_requirements:
                lines.append(
                    "RUN uv pip install --system --python /usr/local/bin/python "
                    + " ".join(shlex.quote(item) for item in step.build_requirements)
                )
        lines.append("RUN " + _uv_pip_command(step))
    lines.extend(("", 'CMD ["python"]'))
    return "\n".join(lines) + "\n"
