"""Small subprocess boundary used by detection probes and their tests."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str = ""
    stderr: str = ""


class CommandRunner(Protocol):
    def __call__(self, args: Sequence[str], timeout: float) -> CommandResult: ...


def run_command(args: Sequence[str], timeout: float = 5.0) -> CommandResult:
    """Run a probe command without a shell and capture decoded output."""

    completed = subprocess.run(
        list(args),
        check=False,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=timeout,
    )
    return CommandResult(
        args=tuple(str(value) for value in args),
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )
