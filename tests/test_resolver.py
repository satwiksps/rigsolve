from __future__ import annotations

from dataclasses import replace

import pytest

from rigsolve.detect import (
    CudaToolkit,
    InstalledEnvironment,
    InstalledPackage,
    TorchBuild,
    profile_from_target,
)
from rigsolve.errors import UserInputError
from rigsolve.matrix import MatrixStore, load_bundled
from rigsolve.solve.explain import explain_failure
from rigsolve.solve.resolver import (
    _platform_matches,
    _python_matches,
    parse_requirements,
    resolve,
)

MATRIX = r"""
[meta]
schema_version = 1
matrix_version = "test-1"
generated = "2026-08-15"

[[torch_build]]
version = "2.6.0"
cuda_line = "12.4"
cuda_exact = "12.4.1"
index_url = "https://download.example.test/cu124"
cxx11abi = false
pythons = ["3.12", "3.13"]
platforms = ["linux_x86_64"]
tier = 0
[torch_build.source]
kind = "build-script"
repo = "example/torch"
tag = "v2.6.0"
harvested = "2026-08-15"

[[wheel]]
package = "flash-attn"
version = "2.8.3"
cuda_line = "12"
torch = "2.6"
cxx11abi = false
python = "cp312"
abi = "cp312"
platform = "linux_x86_64"
url = "https://example.test/flash_attn-2.8.3-cp312-cp312-linux_x86_64.whl"
tier = 0
[wheel.source]
kind = "gh-release"
repo = "example/flash"
tag = "v2.8.3"
harvested = "2026-08-15"

[[source_build]]
package = "flash-attn"
version_spec = ">=2.8"
requirements = ["nvcc", "torch", "packaging", "ninja"]
flags = ["--no-build-isolation"]
estimate_minutes = 25
ram_gb_per_job = 2.0
tier = 0
[source_build.source]
kind = "build-docs"
url = "https://example.test/build"
harvested = "2026-08-15"
"""


def store() -> MatrixStore:
    return MatrixStore.from_toml(MATRIX)


def test_resolve_adds_torch_and_uses_direct_extension_wheel() -> None:
    profile = profile_from_target("RTX 4090,driver=560.35,python=3.12,linux")
    outcome = resolve(("flash-attn==2.8.3",), profile, store())
    assert outcome.satisfiable
    assert outcome.plan is not None
    assert [step.package for step in outcome.plan.ordered_steps()] == ["torch", "flash-attn"]
    extension = next(step for step in outcome.plan.steps if step.package == "flash-attn")
    assert extension.artifact_url and extension.artifact_url.endswith(".whl")
    assert outcome.plan.weakest_tier == 0


def test_unknown_gpu_architecture_is_reported_as_unverified() -> None:
    profile = profile_from_target("madeup,driver=580.65,python=3.12,linux")
    outcome = resolve(("torch",), profile, load_bundled())

    assert outcome.plan is not None
    assert any("GPU compute capability is unknown" in warning for warning in outcome.plan.warnings)


def test_bundled_matrix_resolves_supported_pure_python_package() -> None:
    profile = profile_from_target("cpu,python=3.12,linux")
    outcome = resolve(("transformers",), profile, load_bundled())

    assert outcome.failure is None
    assert outcome.plan is not None
    assert [(step.package, step.version) for step in outcome.plan.steps] == [
        ("transformers", "5.15.0")
    ]
    step = outcome.plan.steps[0]
    assert step.artifact_url is not None
    assert step.artifact_url.startswith("https://files.pythonhosted.org/")
    assert step.python_tag == "py3"
    assert step.platform_tag == "any"


def test_resolve_rejects_a_scalar_requirement_string() -> None:
    profile = profile_from_target("python=3.12,linux")
    with pytest.raises(UserInputError, match="sequence of requirement strings"):
        resolve("torch", profile, load_bundled())  # type: ignore[arg-type]


def test_unsat_explanation_calls_missing_python_wheel_a_conflict() -> None:
    profile = profile_from_target("RTX 4090,driver=560.35,python=3.13,linux")
    outcome = resolve(("flash-attn==2.8.3",), profile, store())
    assert not outcome.satisfiable
    assert outcome.failure is not None
    text = explain_failure(outcome.failure, profile)
    assert "No solution." in text
    assert "Python 3.13" in text
    assert "must publish a wheel for Python" in text
    assert "Use Python 3.12" in text


def test_source_build_is_explicit_and_carries_guidance() -> None:
    profile = profile_from_target(
        "RTX 4090,driver=560.35,nvcc=12.4,cuda_home=/opt/cuda-12.4,python=3.13,linux"
    )
    outcome = resolve(
        ("flash-attn==2.8.3",),
        profile,
        store(),
        allow_source_build=True,
    )
    assert outcome.satisfiable
    assert outcome.plan is not None
    extension = next(step for step in outcome.plan.steps if step.package == "flash-attn")
    assert extension.source_build
    assert extension.build_estimate == "~25 min"
    assert extension.ram_gb_per_job == 2.0
    assert ("CUDA_HOME", "/opt/cuda-12.4") in extension.environment
    assert ("MAX_JOBS", "1") in extension.environment
    assert "--no-build-isolation" in extension.flags
    assert extension.build_requirements == ("packaging", "ninja")
    assert [step.package for step in outcome.plan.ordered_steps()] == ["torch", "flash-attn"]


def test_source_build_derives_cuda_home_from_detected_nvcc_path() -> None:
    profile = profile_from_target("RTX 4090,driver=560.35,nvcc=12.4,python=3.13,linux")
    profile = replace(
        profile,
        toolkit=CudaToolkit("12.4", path="/usr/local/cuda/bin/nvcc"),
    )
    outcome = resolve(
        ("flash-attn==2.8.3",),
        profile,
        store(),
        allow_source_build=True,
    )

    assert outcome.plan is not None
    extension = next(step for step in outcome.plan.steps if step.package == "flash-attn")
    assert ("CUDA_HOME", "/usr/local/cuda") in extension.environment


def test_source_build_requires_toolkit_and_documented_platform() -> None:
    without_toolkit = profile_from_target("RTX 4090,driver=560.35,python=3.13,linux")
    outcome = resolve(
        ("flash-attn==2.8.3",),
        without_toolkit,
        store(),
        allow_source_build=True,
    )
    assert not outcome.satisfiable
    assert outcome.failure is not None
    assert any("CUDA toolkit" in suggestion for suggestion in outcome.failure.suggestions)

    windows = profile_from_target("RTX 4090,driver=560.35,nvcc=12.4,python=3.13,windows")
    assert not resolve(
        ("flash-attn==2.8.3",),
        windows,
        store(),
        allow_source_build=True,
    ).satisfiable


def test_suggestions_are_counterfactual_solutions() -> None:
    profile = profile_from_target("RTX 4090,driver=560.35,python=3.13,linux")
    outcome = resolve(
        ("flash-attn==2.8.3",),
        profile,
        store(),
        allow_source_build=True,
    )
    assert outcome.failure is not None
    assert "Use Python 3.12 (a complete solution exists)" in outcome.failure.suggestions
    assert not any("Python 3.15" in item for item in outcome.failure.suggestions)
    assert any("CUDA toolkit" in item for item in outcome.failure.suggestions)

    impossible = resolve(("torch==99",), profile, store())
    assert impossible.failure is not None
    assert impossible.failure.suggestions == ()


def test_wheel_tag_matching_handles_abi3_and_platform_any() -> None:
    profile = profile_from_target("python=3.12,linux,arch=x86_64")
    assert _python_matches(("cp38",), ("abi3",), "3.12")
    assert not _python_matches(("cp38",), ("cp38",), "3.12")
    assert _python_matches(("py39",), ("none",), "3.12")
    assert not _python_matches(("py39",), ("none",), "3.8")
    assert _platform_matches(("any",), profile)


def test_official_torch_abi_selects_matching_flash_asset() -> None:
    profile = profile_from_target("RTX 4090,driver=580.65,python=3.12,linux")
    outcome = resolve(
        ("flash-attn==2.8.3", "torch==2.8.0"),
        profile,
        load_bundled(),
    )
    assert outcome.plan is not None
    flash = next(step for step in outcome.plan.steps if step.package == "flash-attn")
    assert flash.artifact_url is not None
    assert "cxx11abiTRUE" in flash.artifact_url
    assert not any("ABI is not established" in warning for warning in outcome.plan.warnings)


def test_local_cuda_pin_maps_to_public_torch_build() -> None:
    profile = profile_from_target("RTX 4090,driver=580.65,python=3.12,linux")
    outcome = resolve(("torch==2.9.0+cu126",), profile, load_bundled())

    assert outcome.plan is not None
    assert outcome.plan.steps[0].version == "2.9.0"
    assert outcome.plan.steps[0].index_url is not None
    assert outcome.plan.steps[0].index_url.endswith("/cu126")


@pytest.mark.parametrize("requirement", ["torch[opt]", "torch; python_version < '3'"])
def test_solver_rejects_semantics_it_cannot_preserve(requirement: str) -> None:
    with pytest.raises(UserInputError):
        parse_requirements((requirement,))


def test_native_artifact_without_build_axes_is_missing_coverage() -> None:
    profile = profile_from_target("A100,driver=580.65,python=3.12,linux")
    outcome = resolve(("xformers",), profile, load_bundled())

    assert outcome.failure is not None
    assert outcome.failure.missing_packages == ("xformers",)


def test_explicit_cpu_target_rejects_cuda_only_torch_matrix() -> None:
    profile = profile_from_target("cpu,python=3.12,linux")
    outcome = resolve(("torch",), profile, load_bundled())

    assert not outcome.satisfiable
    assert outcome.failure is not None


def test_cuda_solve_rejects_platforms_outside_current_data_scope() -> None:
    profile = profile_from_target("A100,driver=580.65,python=3.12,macos")

    assert not resolve(("torch",), profile, load_bundled()).satisfiable


def test_minimal_change_prefers_installed_cuda_build_identity() -> None:
    base = profile_from_target("RTX 4090,driver=580.65,python=3.12,linux")
    installed = InstalledEnvironment(
        packages=(InstalledPackage("torch", "2.8.0+cu129", cuda_version="12.9"),),
        torch=TorchBuild("2.8.0+cu129", cuda_version="12.9", cxx11_abi=True),
    )
    profile = replace(base, installed=installed)

    outcome = resolve(("torch==2.8.0",), profile, load_bundled(), preference="minimal-change")

    assert outcome.plan is not None
    assert outcome.plan.steps[0].index_url is not None
    assert outcome.plan.steps[0].index_url.endswith("/cu129")


def test_coupled_pytorch_packages_share_selected_cuda_index() -> None:
    profile = profile_from_target("RTX 4090,driver=580.65,python=3.12,linux")
    outcome = resolve(("torchvision", "torchaudio"), profile, load_bundled())

    assert outcome.plan is not None
    indexes = {step.index_url for step in outcome.plan.steps}
    assert len(indexes) == 1
    assert None not in indexes


def test_platform_and_free_threaded_tags_are_not_conflated() -> None:
    windows = profile_from_target("python=3.13,windows,arch=amd64")
    assert _platform_matches(("win_amd64",), windows)
    assert not _python_matches(("3.13t",), (), "3.13", "cp313")
    assert _python_matches(("3.13t",), (), "3.13", "cp313t")


def test_driver_suggestion_accepts_branch_only_matrix_floor() -> None:
    profile = profile_from_target("RTX 4090,driver=500.0,python=3.12,linux")
    outcome = resolve(("flash-attn==2.8.3",), profile, load_bundled())

    assert outcome.failure is not None
    assert any(
        "driver" in suggestion.lower() and "580.0" in suggestion
        for suggestion in outcome.failure.suggestions
    )


def test_exact_pin_failure_sources_exclude_other_releases() -> None:
    profile = profile_from_target("A100,driver=500.0,python=3.12,linux")
    outcome = resolve(("flash-attn==2.8.3",), profile, load_bundled())

    assert outcome.failure is not None
    explanation = explain_failure(outcome.failure, profile)
    assert "v2.8.3" in explanation
    assert "v2.8.3.post1" not in explanation


def test_unmodeled_pin_is_reported_as_missing_coverage() -> None:
    profile = profile_from_target("RTX 4090,driver=580.65,python=3.12,linux")
    outcome = resolve(("torch==2.10",), profile, load_bundled())

    assert outcome.failure is not None
    text = explain_failure(outcome.failure, profile)
    assert "missing coverage" in text
    assert "modeled versions:" in text
    assert "2.9.0" in text
    assert "source:" in text


def test_plan_tier_includes_used_driver_constraints() -> None:
    verified_matrix = r"""
[meta]
schema_version = 1
matrix_version = "verified-test"
generated = "2026-08-15"

[[wheel]]
package = "bitsandbytes"
version = "1.0.0"
cuda_line = "12"
python = "cp312"
abi = "cp312"
platform = "linux_x86_64"
archs = ["sm_80"]
url = "https://example.test/bitsandbytes.whl"
sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
tier = 3
[wheel.source]
kind = "gpu-run"
url = "https://example.test/runs/1"
harvested = "2026-08-15"

[[constraint]]
kind = "driver-min"
cuda_runtime = "12.x"
min_driver = { linux = "525" }
tier = 0
[constraint.source]
kind = "official-docs"
url = "https://example.test/driver"
harvested = "2026-08-15"
"""
    profile = profile_from_target("A100,driver=580.65,python=3.12,linux")
    outcome = resolve(("bitsandbytes==1.0.0",), profile, MatrixStore.from_toml(verified_matrix))

    assert outcome.plan is not None
    assert outcome.plan.steps[0].tier == 3
    assert outcome.plan.weakest_tier == 0
    assert any("metadata-backed" in warning for warning in outcome.plan.warnings)


def test_verified_preference_scores_the_effective_plan_tier_set() -> None:
    evidence_matrix = r"""
[meta]
schema_version = 1
matrix_version = "score-test"
generated = "2026-08-15"

[[wheel]]
package = "a"
version = "1"
python = "py3"
abi = "none"
platform = "any"
archs = ["sm_80"]
url = "https://example.test/a-1.whl"
sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
tier = 3
[wheel.source]
kind = "gpu-run"
url = "https://example.test/runs/a1"
harvested = "2026-08-15"

[[wheel]]
package = "b"
version = "1"
python = "py3"
abi = "none"
platform = "any"
url = "https://example.test/b-1.whl"
tier = 0
[wheel.source]
kind = "gh-release"
url = "https://example.test/releases/b1"
harvested = "2026-08-15"

[[wheel]]
package = "a"
version = "2"
python = "py3"
abi = "none"
platform = "any"
url = "https://example.test/a-2.whl"
sha256 = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
tier = 1
[wheel.source]
kind = "install-test"
url = "https://example.test/runs/a2"
harvested = "2026-08-15"

[[wheel]]
package = "b"
version = "2"
python = "py3"
abi = "none"
platform = "any"
url = "https://example.test/b-2.whl"
sha256 = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
tier = 1
[wheel.source]
kind = "install-test"
url = "https://example.test/runs/b2"
harvested = "2026-08-15"

[[couple]]
kind = "exact-version-lockstep"
packages = ["a", "b"]
tier = 0
[couple.source]
kind = "official-docs"
url = "https://example.test/compatibility"
harvested = "2026-08-15"
"""
    profile = profile_from_target("python=3.12,linux")
    outcome = resolve(("a", "b"), profile, MatrixStore.from_toml(evidence_matrix))

    assert outcome.plan is not None
    assert {step.version for step in outcome.plan.steps} == {"1"}
    assert outcome.plan.weakest_tier == 0


def test_known_broken_constraints_use_the_selected_target_axes() -> None:
    scoped_matrix = r"""
[meta]
schema_version = 1
matrix_version = "known-broken-target-test"
generated = "2026-08-15"

[[torch_build]]
version = "2.0.0"
cuda_line = "12.4"
index_url = "https://download.example.test/cu124"
pythons = ["3.11", "3.12"]
tier = 0
[torch_build.source]
kind = "build-script"
url = "https://example.test/build"
harvested = "2026-08-15"

[[known_broken]]
id = "python312-edge"
description = "This build is broken only on CPython 3.12."
match = { package = "torch", version = "2.0.0", python = "cp312", source_build = false }
workaround = "Use Python 3.11."
[known_broken.source]
kind = "issue"
url = "https://example.test/issues/12"
harvested = "2026-08-15"
"""
    matrix = MatrixStore.from_toml(scoped_matrix)
    broken_target = profile_from_target("A100,driver=580.65,python=3.12,linux")
    supported_target = profile_from_target("A100,driver=580.65,python=3.11,linux")

    assert not resolve(("torch==2.0.0",), broken_target, matrix).satisfiable
    assert resolve(("torch==2.0.0",), supported_target, matrix).satisfiable


def test_known_broken_platform_keeps_candidate_and_profile_tags() -> None:
    scoped_matrix = r"""
[meta]
schema_version = 1
matrix_version = "known-broken-platform-test"
generated = "2026-08-15"

[[torch_build]]
version = "2.0.0"
cuda_line = "12.4"
index_url = "https://download.example.test/cu124"
pythons = ["3.12"]
platforms = ["linux_x86_64"]
tier = 0
[torch_build.source]
kind = "build-script"
url = "https://example.test/build"
harvested = "2026-08-15"

[[known_broken]]
id = "linux-wheel-edge"
description = "This build is broken on the Linux x86_64 artifact."
match = { package = "torch", version = "2.0.0", platform = "linux_x86_64" }
workaround = "Use another release."
[known_broken.source]
kind = "issue"
url = "https://example.test/issues/linux"
harvested = "2026-08-15"
"""
    matrix = MatrixStore.from_toml(scoped_matrix)
    profile = profile_from_target("A100,driver=580.65,python=3.12,linux,glibc=2.28")

    assert profile.platform.manylinux_tag == "manylinux_2_28_x86_64"
    assert not resolve(("torch==2.0.0",), profile, matrix).satisfiable
