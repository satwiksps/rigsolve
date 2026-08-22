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
    nvidia_smi = shutil.which("nvidia-smi")
    nvcc = shutil.which("nvcc")
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
            nvidia_smi is not None,
            "available" if nvidia_smi else "not found; GPU fields remain unconstrained",
        ),
        DoctorCheck(
            "nvcc",
            nvcc is not None,
            "available" if nvcc else "not found; binary wheels are unaffected",
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
