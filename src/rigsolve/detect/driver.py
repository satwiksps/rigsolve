"""NVIDIA display-driver to maximum CUDA runtime mapping."""

from __future__ import annotations

import re
from collections.abc import Iterable

# Minimum driver versions published in CUDA toolkit release notes.  Ordering is
# newest-first because a driver can support every older runtime line as well.
_LINUX_MINIMUMS: tuple[tuple[str, str], ...] = (
    ("13.0", "580.65.06"),
    ("12.9", "575.51.03"),
    ("12.8", "570.26"),
    ("12.7", "565.57.01"),
    ("12.6", "560.28.03"),
    ("12.5", "555.42.02"),
    ("12.4", "550.54.14"),
    ("12.3", "545.23.06"),
    ("12.2", "535.54.03"),
    ("12.1", "530.30.02"),
    ("12.0", "525.60.13"),
    ("11.8", "520.61.05"),
    ("11.7", "515.43.04"),
    ("11.6", "510.39.01"),
    ("11.5", "495.29.05"),
    ("11.4", "470.42.01"),
    ("11.3", "465.19.01"),
    ("11.2", "460.27.04"),
    ("11.1", "455.23"),
    ("11.0", "450.36.06"),
    ("10.2", "440.33"),
    ("10.1", "418.39"),
    ("10.0", "410.48"),
)

_WINDOWS_MINIMUMS: tuple[tuple[str, str], ...] = (
    ("13.0", "580.88"),
    ("12.9", "576.02"),
    ("12.8", "570.65"),
    ("12.7", "566.03"),
    ("12.6", "560.76"),
    ("12.5", "555.85"),
    ("12.4", "551.61"),
    ("12.3", "546.01"),
    ("12.2", "536.25"),
    ("12.1", "531.14"),
    ("12.0", "527.41"),
    ("11.8", "522.06"),
    ("11.7", "516.01"),
    ("11.6", "511.23"),
    ("11.5", "496.04"),
    ("11.4", "471.41"),
    ("11.3", "465.89"),
    ("11.2", "461.09"),
    ("11.1", "456.38"),
    ("11.0", "451.22"),
    ("10.2", "441.22"),
    ("10.1", "418.96"),
    ("10.0", "411.31"),
)

_MINOR_COMPATIBILITY_FLOORS = {
    "linux": {13: "580.65.06", 12: "525.60.13", 11: "450.80.02"},
    "windows": {13: "580.88", 12: "527.41", 11: "452.39"},
}


def parse_version_tuple(value: str | None) -> tuple[int, ...] | None:
    """Parse a dotted NVIDIA version while tolerating distro suffixes."""

    if value is None:
        return None
    match = re.search(r"\d+(?:\.\d+)+", value.strip())
    if match is None:
        return None
    return tuple(int(part) for part in match.group(0).split("."))


def _padded(value: tuple[int, ...], length: int = 4) -> tuple[int, ...]:
    return (value + (0,) * length)[:length]


def _minimums(os_name: str | None) -> Iterable[tuple[str, str]]:
    normalized = (os_name or "linux").strip().lower()
    return _WINDOWS_MINIMUMS if normalized.startswith("win") else _LINUX_MINIMUMS


def _at_least(current: tuple[int, ...], minimum: tuple[int, ...]) -> bool:
    # A user-supplied branch such as ``550.54`` conventionally means the
    # 550.54 release family; accept it when the published threshold is
    # 550.54.14.  Full versions still receive exact numeric comparison.
    if len(current) < len(minimum) and current == minimum[: len(current)]:
        return True
    return _padded(current) >= _padded(minimum)


def max_cuda_runtime_for_driver(
    driver_version: str | None,
    *,
    os_name: str | None = "linux",
) -> str | None:
    """Return the newest CUDA runtime supported by a display driver.

    Unknown or very old driver versions return ``None``.  That value is an
    unconstrained solver input, not a claim that CUDA is unsupported.
    """

    parsed = parse_version_tuple(driver_version)
    if parsed is None:
        return None
    for cuda_runtime, minimum_driver in _minimums(os_name):
        minimum = parse_version_tuple(minimum_driver)
        if minimum is not None and _at_least(parsed, minimum):
            return cuda_runtime
    return None


def driver_supports_runtime(
    driver_version: str | None,
    cuda_runtime: str | None,
    *,
    os_name: str | None = "linux",
    minor_compatibility: bool = True,
) -> bool | None:
    """Return support status, or ``None`` when either side is unknown.

    By default this applies NVIDIA's within-major minor-version compatibility
    floors (with the documented reduced feature set).  Set
    ``minor_compatibility=False`` when a build requires the runtime's
    corresponding toolkit driver, for example because it contains PTX that
    must be JIT-compiled by a newer driver.
    """

    driver = parse_version_tuple(driver_version)
    requested = parse_version_tuple(cuda_runtime)
    if requested is None or driver is None:
        return None
    if minor_compatibility:
        family = "windows" if (os_name or "").lower().startswith("win") else "linux"
        minimum_value = _MINOR_COMPATIBILITY_FLOORS[family].get(requested[0])
        if minimum_value is None:
            return None
        minimum = parse_version_tuple(minimum_value)
        return None if minimum is None else _at_least(driver, minimum)
    maximum = parse_version_tuple(max_cuda_runtime_for_driver(driver_version, os_name=os_name))
    if maximum is None:
        return None
    return _padded(requested, 2) <= _padded(maximum, 2)


# Natural aliases used by callers and older fixture code.
driver_to_max_cuda = max_cuda_runtime_for_driver
max_cuda_for_driver = max_cuda_runtime_for_driver
