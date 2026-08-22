from __future__ import annotations

import pytest

from rigsolve.plan import InstallPlan, InstallStep


def test_install_plan_rejects_dependency_cycle() -> None:
    plan = InstallPlan(
        requested=("package-a",),
        steps=(
            InstallStep("package-a", "1", dependencies=("package-b",)),
            InstallStep("package-b", "1", dependencies=("package-a",)),
        ),
        matrix_version="test",
        matrix_digest="a" * 64,
    )

    with pytest.raises(ValueError, match="install dependency cycle: package-a, package-b"):
        plan.ordered_steps()


@pytest.mark.parametrize("field", ["artifact_url", "index_url"])
def test_install_step_rejects_non_https_package_urls(field: str) -> None:
    with pytest.raises(ValueError, match="URL must be absolute HTTPS"):
        InstallStep("demo", "1", **{field: "http://packages.example.test/simple"})


def test_install_step_rejects_wheel_url_for_source_build() -> None:
    with pytest.raises(ValueError, match="source-build step cannot also name a wheel URL"):
        InstallStep(
            "demo",
            "1",
            artifact_url="https://packages.example.test/demo.whl",
            source_build=True,
        )
