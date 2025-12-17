from __future__ import annotations

import json

import pytest

from rigsolve.errors import UserInputError
from rigsolve.plan import InstallPlan, InstallStep, render_plan


def sample_plan() -> InstallPlan:
    return InstallPlan(
        requested=("flash-attn",),
        steps=(
            InstallStep(
                package="flash-attn",
                version="2.8.3",
                artifact_url="https://example.test/flash.whl",
                artifact_sha256="b" * 64,
                dependencies=("torch",),
                tier=0,
                cuda_line="12.4",
                torch_version="2.6",
                cxx11_abi=True,
            ),
            InstallStep(
                package="torch",
                version="2.6.0+cu124",
                index_url="https://download.pytorch.org/whl/cu124",
                tier=2,
                cuda_line="12.4",
            ),
        ),
        matrix_version="2026.08.15",
        matrix_digest="a" * 64,
        target={
            "python_version": "3.12",
            "platform": "linux_x86_64",
            "cuda_runtime": "12.4.1",
        },
    )


def source_plan() -> InstallPlan:
    return InstallPlan(
        requested=("flash-attn",),
        steps=(
            InstallStep(
                package="flash-attn",
                version="2.8.3",
                build_requirements=("packaging", "ninja"),
                environment=(("CUDA_HOME", "/opt/cuda"), ("MAX_JOBS", "1")),
                flags=("--no-build-isolation",),
                source_build=True,
                build_estimate="~25 min",
                ram_gb_per_job=2.0,
            ),
        ),
        matrix_version="2026.08.15",
        matrix_digest="a" * 64,
        target={
            "python_version": "3.12",
            "platform": "linux",
            "cuda_runtime": "12.4.1",
        },
    )


def test_pip_is_dependency_ordered_and_warns_about_evidence() -> None:
    output = render_plan(sample_plan(), "pip")
    assert output.index("torch==") < output.index("flash.whl")
    assert "weakest evidence: tier 0" in output
    assert "--index-url https://download.pytorch.org/whl/cu124" in output
    assert "#sha256=" + "b" * 64 in output


def test_json_is_valid_and_ordered() -> None:
    payload = json.loads(render_plan(sample_plan(), "json"))
    assert [step["package"] for step in payload["steps"]] == ["torch", "flash-attn"]
    assert payload["weakest_tier"] == 0


def test_toml_roundtrip(tmp_path) -> None:
    from rigsolve.plan.lockfile import load_lockfile

    path = tmp_path / "rigsolve.toml"
    text = render_plan(sample_plan(), "toml")
    path.write_text(text, encoding="utf-8")
    loaded = load_lockfile(path)
    assert render_plan(loaded, "toml") == text


@pytest.mark.parametrize(
    ("field", "message"),
    (
        ('source-build = "false"', "source-build must be a boolean"),
        ('cxx11abi = "false"', "cxx11abi must be a boolean"),
        ('sha25 = "' + "a" * 64 + '"', "sha25"),
    ),
)
def test_lockfile_rejects_malformed_package_fields(tmp_path, field, message) -> None:
    from rigsolve.plan.lockfile import load_lockfile

    path = tmp_path / "invalid.toml"
    path.write_text(
        "\n".join(
            (
                "lock-version = 1",
                'matrix-version = "test"',
                f'matrix-digest = "{"a" * 64}"',
                "[[package]]",
                'name = "torch"',
                'version = "2.9.0"',
                field,
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(UserInputError, match=message):
        load_lockfile(path)


def test_lockfile_rejects_unknown_target_fields(tmp_path) -> None:
    from rigsolve.plan.lockfile import load_lockfile

    path = tmp_path / "invalid-target.toml"
    path.write_text(
        "\n".join(
            (
                "lock-version = 1",
                'matrix-version = "test"',
                f'matrix-digest = "{"a" * 64}"',
                "[target]",
                'mystery = "value"',
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(UserInputError, match="unknown target field"):
        load_lockfile(path)


def test_source_build_guidance_roundtrips_and_renders(tmp_path) -> None:
    from rigsolve.plan.lockfile import load_lockfile

    path = tmp_path / "rigsolve-source.toml"
    toml = render_plan(source_plan(), "toml")
    path.write_text(toml, encoding="utf-8")
    loaded = load_lockfile(path)

    assert loaded.steps[0].ram_gb_per_job == 2.0
    assert "ram-gb-per-job = 2.0" in toml
    assert render_plan(loaded, "toml") == toml

    payload = json.loads(render_plan(source_plan(), "json"))
    assert payload["steps"][0]["ram_gb_per_job"] == 2.0

    pip = render_plan(source_plan(), "pip")
    assert "~2 GiB RAM per compiler job" in pip
    assert "export CUDA_HOME=/opt/cuda" in pip
    assert "export MAX_JOBS=1" in pip

    docker = render_plan(source_plan(), "docker")
    assert "~2 GiB RAM per compiler job" in docker
    assert 'ENV CUDA_HOME="/opt/cuda"' in docker
    assert 'ENV MAX_JOBS="1"' in docker

    colab = render_plan(source_plan(), "colab")
    assert "~2 GiB RAM per compiler job" in colab


def test_uv_uses_explicit_index_and_direct_wheel() -> None:
    output = render_plan(sample_plan(), "uv")
    assert "[[tool.uv.index]]" in output
    assert "explicit = true" in output
    assert "#sha256=" + "b" * 64 in output
    assert 'requires-python = "==3.12.*"' in output


def test_docker_and_colab_outputs_are_complete() -> None:
    docker = render_plan(sample_plan(), "docker")
    assert docker.startswith("# syntax=docker/dockerfile:1")
    assert "FROM ghcr.io/astral-sh/uv:0.12.5@sha256:" in docker
    assert "FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04" in docker
    assert "uv python install 3.12" in docker
    assert "uv pip install --system --python /usr/local/bin/python" in docker
    assert "python -m pip" not in docker
    assert 'CMD ["python"]' in docker

    colab = render_plan(sample_plan(), "colab")
    assert colab.startswith("%%bash\n# Colab bootstrap generated by rigsolve")
