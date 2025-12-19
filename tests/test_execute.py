from __future__ import annotations

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
    assert calls[0][0][-1] == "torch==2"
    assert calls[1][0][-1] == "ninja"
    assert calls[2][0][-2:] == ["--no-deps", "extension==1"]
    assert all("shell" not in kwargs for _, kwargs in calls)
