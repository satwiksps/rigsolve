from __future__ import annotations

import sys

from rigsolve.plan.execute import execute_plan
from rigsolve.plan.install import InstallPlan, InstallStep


def test_execute_uses_argv_and_orders_dependencies() -> None:
    calls = []

    def runner(argv, **kwargs):
        calls.append((argv, kwargs))

    plan = InstallPlan(
        requested=("extension",),
        steps=(
            InstallStep(
                "extension",
                "1",
                dependencies=("torch",),
                build_requirements=("ninja",),
                flags=("--no-deps",),
            ),
            InstallStep("torch", "2", index_url="https://example.test/simple"),
        ),
        matrix_version="1",
        matrix_digest="a" * 64,
    )
    execute_plan(plan, runner=runner)
    assert [argv for argv, _ in calls] == [
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--index-url",
            "https://example.test/simple",
            "torch==2",
        ],
        [sys.executable, "-m", "pip", "install", "ninja"],
        [sys.executable, "-m", "pip", "install", "--no-deps", "extension==1"],
    ]
    assert all(kwargs["check"] is True for _, kwargs in calls)
    assert all(kwargs["text"] is True for _, kwargs in calls)
    assert all("shell" not in kwargs for _, kwargs in calls)
