"""NVIDIA GPU discovery through ``nvidia-smi`` only.

This module intentionally has no dependency on NVML Python bindings.  The CLI
tool is present with every normal NVIDIA driver installation and continues to
work when a Python CUDA environment is partially broken.
"""

from __future__ import annotations

import csv
import re
import subprocess
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from ._command import CommandRunner, run_command
from .model import DetectionIssue, GPUDevice, ProfileValidationError, optional_text

FULL_QUERY_FIELDS = (
    "index",
    "name",
    "uuid",
    "compute_cap",
    "memory.total",
    "driver_version",
)
LEGACY_QUERY_FIELDS = ("index", "name", "uuid", "memory.total", "driver_version")


@dataclass(frozen=True, slots=True)
class GPUProbeResult:
    devices: tuple[GPUDevice, ...] = ()
    driver_version: str | None = None
    nvidia_smi_available: bool = False
    issues: tuple[DetectionIssue, ...] = ()


# This is a fallback for older drivers that do not expose compute_cap in their
# query interface.  Keep patterns specific and order them newest-first.
_NAME_TO_SM: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern, re.IGNORECASE), sm)
    for pattern, sm in (
        (r"\b(?:B200|GB200|B100)\b", "sm_100"),
        (r"\b(?:RTX\s*5090|RTX\s*5080|RTX\s*5070(?:\s*Ti)?|RTX\s*5060(?:\s*Ti)?)\b", "sm_120"),
        (r"\b(?:H100|H200|GH200)\b", "sm_90"),
        (
            r"\b(?:RTX\s*4090|RTX\s*4080|RTX\s*4070(?:\s*Ti)?|RTX\s*4060(?:\s*Ti)?|L4|L40S?)\b",
            "sm_89",
        ),
        (r"\b(?:A100|A30)\b", "sm_80"),
        (
            r"\b(?:RTX\s*3090(?:\s*Ti)?|RTX\s*3080(?:\s*Ti)?|RTX\s*3070(?:\s*Ti)?|RTX\s*3060(?:\s*Ti)?|A10G?|A40)\b",
            "sm_86",
        ),
        (r"\b(?:RTX\s*3050|A2)\b", "sm_86"),
        (r"\bT4\b|RTX\s*20\d\d|GTX\s*16\d\d", "sm_75"),
        (r"\bV100\b|TITAN\s+V", "sm_70"),
        (r"\bP100\b", "sm_60"),
        (r"\b(?:P4|P40)\b|GTX\s*10\d\d|TITAN\s+X[Pp]", "sm_61"),
        (r"\bM60\b|\bM40\b|GTX\s*9\d\d", "sm_52"),
        (r"\bK80\b", "sm_37"),
    )
)


def compute_capability_from_name(name: str | None) -> str | None:
    """Return a conservative compute-capability fallback for a known GPU name."""

    if not name:
        return None
    for pattern, sm in _NAME_TO_SM:
        if pattern.search(name):
            return sm
    return None


def _canonical_field(field: str) -> str:
    cleaned = field.strip().lower()
    cleaned = re.sub(r"\s*\[[^]]+\]\s*$", "", cleaned)
    cleaned = cleaned.replace(" ", "_").replace("-", "_")
    aliases = {
        "gpu_name": "name",
        "compute_capability": "compute_cap",
        "compute_capability_(major,_minor)": "compute_cap",
        "memory_total": "memory.total",
        "memory.total_mib": "memory.total",
        "memory.total_[mib]": "memory.total",
        "driver": "driver_version",
    }
    return aliases.get(cleaned, cleaned)


def _memory_mib(value: object) -> int | None:
    text = optional_text(value)
    if text is None:
        return None
    match = re.search(r"\d+(?:\.\d+)?", text.replace(",", ""))
    if match is None:
        return None
    return round(float(match.group(0)))


def parse_nvidia_smi_csv(
    output: str,
    fields: Sequence[str] | None = None,
) -> tuple[GPUDevice, ...]:
    """Parse a no-header query result or a recorded CSV with a header.

    ``nvidia-smi`` uses standard CSV quoting, which matters for a few OEM GPU
    names.  Missing/unsupported cells remain unknown instead of rejecting the
    whole device.
    """

    rows = [row for row in csv.reader(output.splitlines(), skipinitialspace=True) if row]
    if not rows:
        return ()
    if any("no devices were found" in cell.lower() for row in rows for cell in row):
        return ()

    inferred_fields: tuple[str, ...]
    first = tuple(_canonical_field(value) for value in rows[0])
    known_headers = set(FULL_QUERY_FIELDS) | {"memory.total"}
    header_present = "name" in first and bool(set(first) & known_headers)
    if fields is None:
        if not header_present:
            raise ValueError("fields are required for headerless nvidia-smi CSV")
        inferred_fields = first
        rows = rows[1:]
    else:
        inferred_fields = tuple(_canonical_field(value) for value in fields)
        if header_present:
            inferred_fields = first
            rows = rows[1:]

    devices: list[GPUDevice] = []
    for ordinal, row in enumerate(rows):
        if not any(cell.strip() for cell in row):
            continue
        values = {
            field: row[index].strip() if index < len(row) else ""
            for index, field in enumerate(inferred_fields)
        }
        try:
            index_text = optional_text(values.get("index"))
            index = ordinal if index_text is None else int(index_text)
        except ValueError:
            index = ordinal
        name = optional_text(values.get("name"))
        compute_cap = optional_text(values.get("compute_cap"))
        if compute_cap is None:
            compute_cap = compute_capability_from_name(name)
        try:
            device = GPUDevice(
                index=index,
                name=name,
                uuid=optional_text(values.get("uuid")),
                compute_capability=compute_cap,
                memory_total_mib=_memory_mib(values.get("memory.total")),
            )
        except ProfileValidationError:
            # A future driver may emit a compute capability representation that
            # is unknown to us.  Preserve every other device fact.
            device = GPUDevice(
                index=index,
                name=name,
                uuid=optional_text(values.get("uuid")),
                compute_capability=compute_capability_from_name(name),
                memory_total_mib=_memory_mib(values.get("memory.total")),
            )
        devices.append(device)
    return tuple(sorted(devices, key=lambda device: device.index))


def _driver_versions(output: str, fields: Sequence[str]) -> tuple[str, ...]:
    rows = [row for row in csv.reader(output.splitlines(), skipinitialspace=True) if row]
    try:
        position = tuple(fields).index("driver_version")
    except ValueError:
        return ()
    versions: list[str] = []
    for row in rows:
        if position < len(row):
            version = optional_text(row[position])
            if version is not None and version not in versions:
                versions.append(version)
    return tuple(versions)


def _query_args(fields: Iterable[str]) -> tuple[str, ...]:
    return (
        "nvidia-smi",
        f"--query-gpu={','.join(fields)}",
        "--format=csv,noheader,nounits",
    )


def detect_gpus(
    *,
    runner: CommandRunner = run_command,
    timeout: float = 5.0,
) -> GPUProbeResult:
    """Probe NVIDIA devices, falling back for older ``nvidia-smi`` versions."""

    issues: list[DetectionIssue] = []
    fields: Sequence[str] = FULL_QUERY_FIELDS
    try:
        result = runner(_query_args(fields), timeout)
    except FileNotFoundError:
        return GPUProbeResult(
            issues=(
                DetectionIssue(
                    "gpu",
                    "nvidia-smi-not-found",
                    "nvidia-smi is not available; GPU fields are unknown",
                    "info",
                ),
            )
        )
    except subprocess.TimeoutExpired:
        return GPUProbeResult(
            nvidia_smi_available=True,
            issues=(
                DetectionIssue(
                    "gpu", "nvidia-smi-timeout", "nvidia-smi did not respond before timeout"
                ),
            ),
        )
    except OSError as exc:
        return GPUProbeResult(
            issues=(DetectionIssue("gpu", "nvidia-smi-error", f"could not run nvidia-smi: {exc}"),)
        )

    if result.returncode != 0:
        combined = f"{result.stdout}\n{result.stderr}".lower()
        field_unsupported = any(
            marker in combined
            for marker in ("not a valid field", "unknown field", "invalid field", "compute_cap")
        )
        if field_unsupported:
            fields = LEGACY_QUERY_FIELDS
            try:
                result = runner(_query_args(fields), timeout)
            except (OSError, subprocess.TimeoutExpired) as exc:
                issues.append(
                    DetectionIssue(
                        "gpu", "nvidia-smi-fallback-error", f"legacy GPU query failed: {exc}"
                    )
                )
                return GPUProbeResult(nvidia_smi_available=True, issues=tuple(issues))

    if result.returncode != 0:
        combined = (result.stderr or result.stdout).strip()
        if "no devices were found" in combined.lower():
            issues.append(DetectionIssue("gpu", "no-gpu", "no NVIDIA GPU was reported", "info"))
        else:
            issues.append(
                DetectionIssue(
                    "gpu",
                    "nvidia-smi-failed",
                    f"nvidia-smi exited with {result.returncode}: {combined or 'no details'}",
                )
            )
        return GPUProbeResult(nvidia_smi_available=True, issues=tuple(issues))

    try:
        devices = parse_nvidia_smi_csv(result.stdout, fields)
    except (ValueError, csv.Error) as exc:
        return GPUProbeResult(
            nvidia_smi_available=True,
            issues=(
                DetectionIssue(
                    "gpu", "nvidia-smi-parse-error", f"invalid nvidia-smi output: {exc}"
                ),
            ),
        )
    versions = _driver_versions(result.stdout, fields)
    if len(versions) > 1:
        issues.append(
            DetectionIssue(
                "driver",
                "multiple-driver-versions",
                f"nvidia-smi reported multiple driver versions: {', '.join(versions)}",
            )
        )
    if not devices:
        issues.append(DetectionIssue("gpu", "no-gpu", "no NVIDIA GPU was reported", "info"))
    return GPUProbeResult(
        devices=devices,
        driver_version=versions[0] if versions else None,
        nvidia_smi_available=True,
        issues=tuple(issues),
    )


# Backwards-friendly singular spelling.
detect_gpu = detect_gpus
