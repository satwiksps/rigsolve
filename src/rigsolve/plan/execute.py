"""Explicit, shell-free execution of a reviewed install plan."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable

from rigsolve.plan.install import InstallPlan, InstallStep

Runner = Callable[..., subprocess.CompletedProcess[str]]


def step_argv(step: InstallStep) -> list[str]:
    command = [sys.executable, "-m", "pip", "install"]
    if step.index_url:
        command.extend(("--index-url", step.index_url))
    command.extend(step.flags)
    command.append(step.requirement)
    return command


def execute_plan(
    plan: InstallPlan,
    *,
    runner: Runner = subprocess.run,
    on_step: Callable[[InstallStep], None] | None = None,
) -> None:
    """Execute a plan only after the caller handled explicit user consent."""

    for step in plan.ordered_steps():
        if on_step:
            on_step(step)
        environment = os.environ.copy()
        environment.update(dict(step.environment))
        if step.build_requirements:
            runner(
                [sys.executable, "-m", "pip", "install", *step.build_requirements],
                env=environment,
                check=True,
                text=True,
            )
        runner(step_argv(step), env=environment, check=True, text=True)
