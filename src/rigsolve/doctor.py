from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import date

from rigsolve import __version__
from rigsolve.detect import MachineProfile
from rigsolve.matrix import MatrixStore

MAX_MATRIX_AGE_DAYS = 90


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    name: str
    ok: bool
    detail: str


def run_doctor(profile: MachineProfile, store: MatrixStore) -> tuple[DoctorCheck, ...]:
    age = (date.today() - store.metadata.generated_date).days
    return (
        DoctorCheck("rigsolve", True, f"version {__version__}"),
        DoctorCheck(
            "matrix",
            age <= MAX_MATRIX_AGE_DAYS,
            (
                f"{store.matrix_version}, {len(store.facts)} facts, generated "
                f"{store.metadata.generated} ({age} days ago)"
                + (
                    ""
                    if age <= MAX_MATRIX_AGE_DAYS
                    else f"; older than the {MAX_MATRIX_AGE_DAYS}-day safety window, run 'rigsolve matrix update'"
                )
            ),
        ),
        DoctorCheck(
            "nvidia-smi",
            shutil.which("nvidia-smi") is not None,
            "available"
            if shutil.which("nvidia-smi")
            else "not found; GPU fields remain unconstrained",
        ),
        DoctorCheck(
            "nvcc",
            shutil.which("nvcc") is not None,
            "available" if shutil.which("nvcc") else "not found; binary wheels are unaffected",
        ),
        DoctorCheck(
            "platform",
            bool(profile.os and profile.architecture and profile.python_version),
            f"{profile.os or '?'} {profile.architecture or '?'} | Python {profile.python_version or '?'}",
        ),
    )


def format_doctor(checks: tuple[DoctorCheck, ...]) -> str:
    return (
        "\n".join(
            f"{'[ok]' if check.ok else '[!]'} {check.name}: {check.detail}" for check in checks
        )
        + "\n"
    )
