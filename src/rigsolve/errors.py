"""Public exception hierarchy and stable process exit codes."""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    OK = 0
    UNSATISFIABLE = 1
    ENVIRONMENT_BROKEN = 2
    DETECTION_FAILED = 3
    MATRIX_STALE = 4
    USAGE = 64
    INTERNAL = 70


class RigsolveError(Exception):
    """Base class for expected, user-facing failures."""

    exit_code: ExitCode = ExitCode.INTERNAL


class MatrixError(RigsolveError):
    exit_code = ExitCode.UNSATISFIABLE


class MatrixValidationError(MatrixError, ValueError):
    """Raised when a matrix fact violates the schema or provenance rules."""


class DetectionError(RigsolveError):
    exit_code = ExitCode.DETECTION_FAILED


class UnsatisfiableError(RigsolveError):
    exit_code = ExitCode.UNSATISFIABLE


class BrokenEnvironmentError(RigsolveError):
    exit_code = ExitCode.ENVIRONMENT_BROKEN


class StaleMatrixError(RigsolveError):
    exit_code = ExitCode.MATRIX_STALE


class UserInputError(RigsolveError):
    exit_code = ExitCode.USAGE
