"""Output-format registry."""

from __future__ import annotations

from collections.abc import Callable

from rigsolve.errors import UserInputError
from rigsolve.plan.emit.colab import emit_colab
from rigsolve.plan.emit.dockerfile import emit_dockerfile
from rigsolve.plan.emit.json import emit_json
from rigsolve.plan.emit.pip import emit_pip
from rigsolve.plan.emit.toml import emit_toml
from rigsolve.plan.emit.uv import emit_uv
from rigsolve.plan.install import InstallPlan

Emitter = Callable[[InstallPlan], str]

EMITTERS: dict[str, Emitter] = {
    "colab": emit_colab,
    "docker": emit_dockerfile,
    "json": emit_json,
    "pip": emit_pip,
    "toml": emit_toml,
    "uv": emit_uv,
}


def render_plan(plan: InstallPlan, output: str) -> str:
    try:
        emitter = EMITTERS[output]
    except KeyError as error:
        choices = ", ".join(sorted(EMITTERS))
        raise UserInputError(
            f"unknown output format {output!r}; choose one of: {choices}"
        ) from error
    return emitter(plan)
