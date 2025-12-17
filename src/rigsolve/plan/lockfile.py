"""Read and write deterministic rigsolve TOML lockfiles."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

try:
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib

from rigsolve.errors import UserInputError
from rigsolve.plan.emit.toml import emit_toml
from rigsolve.plan.install import InstallPlan, InstallStep

_PACKAGE_FIELDS = frozenset(
    {
        "name",
        "version",
        "url",
        "sha256",
        "index-url",
        "dependencies",
        "build-requirements",
        "environment",
        "flags",
        "source-build",
        "build-estimate",
        "ram-gb-per-job",
        "tier",
        "provenance",
        "cuda-line",
        "torch",
        "cxx11abi",
        "python",
        "platform",
    }
)
_TARGET_STRING_FIELDS = frozenset(
    {
        "gpu",
        "compute-capability",
        "driver-version",
        "python-version",
        "platform",
        "architecture",
        "glibc",
        "toolkit-version",
        "toolkit-path",
        "cuda-runtime",
    }
)
_TARGET_FIELDS = _TARGET_STRING_FIELDS | {
    "gpu-count",
    "compute-capabilities",
    "cxx11abi",
}


def _string_array(value: Any, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be an array of strings")
    return tuple(value)


def _optional_string(item: Mapping[str, Any], field: str, *, context: str) -> str | None:
    value = item.get(field)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{context}.{field} must be a string")
    return value


def write_lockfile(plan: InstallPlan, path: Path) -> None:
    path.write_text(emit_toml(plan), encoding="utf-8", newline="\n")


def load_lockfile(path: Path) -> InstallPlan:
    try:
        with path.open("rb") as stream:
            raw: Any = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise UserInputError(f"cannot read lockfile {path}: {error}") from error
    try:
        if not isinstance(raw, Mapping):
            raise ValueError("root must be a TOML table")
        allowed = {
            "lock-version",
            "matrix-version",
            "matrix-digest",
            "preference",
            "weakest-tier",
            "constraint-tiers",
            "requested",
            "warnings",
            "target",
            "package",
        }
        unknown = set(raw).difference(allowed)
        if unknown:
            raise ValueError("unknown top-level field(s): " + ", ".join(sorted(unknown)))
        lock_version = raw.get("lock-version")
        if isinstance(lock_version, bool) or lock_version != 1:
            raise ValueError("lock-version must be 1")
        matrix_version = raw.get("matrix-version")
        matrix_digest = raw.get("matrix-digest")
        if not isinstance(matrix_version, str) or not matrix_version:
            raise ValueError("matrix-version must be a non-empty string")
        if not isinstance(matrix_digest, str) or not re.fullmatch(
            r"[0-9a-fA-F]{64}", matrix_digest
        ):
            raise ValueError("matrix-digest must contain 64 hex characters")
        target = raw.get("target", {})
        packages = raw.get("package", [])
        if not isinstance(target, Mapping):
            raise ValueError("target must be a TOML table")
        if not isinstance(packages, list):
            raise ValueError("package must be an array of TOML tables")
        unknown_target = set(target).difference(_TARGET_FIELDS)
        if unknown_target:
            raise ValueError("unknown target field(s): " + ", ".join(sorted(unknown_target)))
        for field in _TARGET_STRING_FIELDS:
            if field in target and not isinstance(target[field], str):
                raise ValueError(f"target.{field} must be a string")
        if "gpu-count" in target and (
            not isinstance(target["gpu-count"], int)
            or isinstance(target["gpu-count"], bool)
            or target["gpu-count"] < 0
        ):
            raise ValueError("target.gpu-count must be a non-negative integer")
        if "compute-capabilities" in target:
            _string_array(target["compute-capabilities"], field="target.compute-capabilities")
        if "cxx11abi" in target and not isinstance(target["cxx11abi"], bool):
            raise ValueError("target.cxx11abi must be a boolean")

        steps = []
        for index, item in enumerate(packages):
            if not isinstance(item, Mapping):
                raise ValueError(f"package[{index}] must be a TOML table")
            context = f"package[{index}]"
            unknown_package = set(item).difference(_PACKAGE_FIELDS)
            if unknown_package:
                raise ValueError(
                    f"{context} has unknown field(s): " + ", ".join(sorted(unknown_package))
                )
            for required in ("name", "version"):
                if not isinstance(item.get(required), str) or not item[required]:
                    raise ValueError(f"{context}.{required} must be a non-empty string")
            for field in (
                "url",
                "sha256",
                "index-url",
                "build-estimate",
                "cuda-line",
                "torch",
                "python",
                "platform",
            ):
                _optional_string(item, field, context=context)
            arrays = {
                field: _string_array(item.get(field, []), field=f"{context}.{field}")
                for field in (
                    "dependencies",
                    "build-requirements",
                    "flags",
                    "provenance",
                )
            }
            environment = item.get("environment", {})
            if not isinstance(environment, Mapping):
                raise ValueError(f"{context}.environment must be a TOML table")
            if not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in environment.items()
            ):
                raise ValueError(f"{context}.environment values must be strings")
            source_build = item.get("source-build", False)
            if not isinstance(source_build, bool):
                raise ValueError(f"{context}.source-build must be a boolean")
            cxx11abi = item.get("cxx11abi")
            if cxx11abi is not None and not isinstance(cxx11abi, bool):
                raise ValueError(f"{context}.cxx11abi must be a boolean")
            tier = item.get("tier", 0)
            if not isinstance(tier, int) or isinstance(tier, bool):
                raise ValueError(f"{context}.tier must be an integer")
            ram_gb_per_job = item.get("ram-gb-per-job")
            if ram_gb_per_job is not None and (
                isinstance(ram_gb_per_job, bool) or not isinstance(ram_gb_per_job, (int, float))
            ):
                raise ValueError(f"{context}.ram-gb-per-job must be a number")
            steps.append(
                InstallStep(
                    package=item["name"],
                    version=item["version"],
                    artifact_url=item.get("url"),
                    artifact_sha256=item.get("sha256"),
                    index_url=item.get("index-url"),
                    dependencies=arrays["dependencies"],
                    build_requirements=arrays["build-requirements"],
                    environment=tuple(sorted(environment.items())),
                    flags=arrays["flags"],
                    source_build=source_build,
                    build_estimate=item.get("build-estimate"),
                    ram_gb_per_job=ram_gb_per_job,
                    tier=tier,
                    provenance=arrays["provenance"],
                    cuda_line=item.get("cuda-line"),
                    torch_version=item.get("torch"),
                    cxx11_abi=cxx11abi,
                    python_tag=item.get("python"),
                    platform_tag=item.get("platform"),
                )
            )
        requested = raw.get("requested", ())
        warnings = raw.get("warnings", [])
        constraint_tiers = raw.get("constraint-tiers", [])
        if not isinstance(requested, list) or not all(isinstance(item, str) for item in requested):
            raise ValueError("requested must be an array of strings")
        if not isinstance(warnings, list) or not all(isinstance(item, str) for item in warnings):
            raise ValueError("warnings must be an array of strings")
        if not isinstance(constraint_tiers, list):
            raise ValueError("constraint-tiers must be an array of integers")
        if not all(
            isinstance(item, int) and not isinstance(item, bool) for item in constraint_tiers
        ):
            raise ValueError("constraint-tiers must be an array of integers")
        preference = raw.get("preference", "verified")
        if not isinstance(preference, str) or not preference:
            raise ValueError("preference must be a non-empty string")
        weakest_tier = raw.get("weakest-tier")
        if weakest_tier is not None and (
            not isinstance(weakest_tier, int) or isinstance(weakest_tier, bool)
        ):
            raise ValueError("weakest-tier must be an integer")
        plan = InstallPlan(
            requested=tuple(requested),
            steps=tuple(steps),
            matrix_version=matrix_version,
            matrix_digest=matrix_digest.lower(),
            target={str(key).replace("-", "_"): value for key, value in target.items()},
            preference=preference,
            constraint_tiers=tuple(constraint_tiers),
            warnings=tuple(warnings),
        )
        if weakest_tier is not None and weakest_tier != plan.weakest_tier:
            raise ValueError(
                f"weakest-tier must match the plan's computed tier {plan.weakest_tier}"
            )
        return plan
    except (KeyError, TypeError, ValueError) as error:
        raise UserInputError(f"invalid lockfile {path}: {error}") from error
