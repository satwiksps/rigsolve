"""Offline/CI harvesters for rigsolve's compatibility matrix."""

from .cache import CachedHTTPClient, FetchResult, HarvestHTTPError
from .gh_release import (
    GitHubHarvestError,
    GitHubReleaseHarvest,
    GitHubReleaseHarvester,
    harvest_release,
    parse_release_payload,
)
from .normalise import (
    NormalizedWheel,
    WheelFilenameError,
    normalise_many,
    normalise_wheel_filename,
    normalize_wheel_filename,
    parse_wheel_asset,
    try_normalise_wheel_filename,
)
from .nvidia_tables import (
    NvidiaHarvestError,
    NvidiaTableHarvester,
    parse_driver_table,
)
from .pypi_index import (
    PyPIHarvest,
    PyPIHarvester,
    PyPIHarvestError,
    harvest_pypi,
    parse_pypi_payload,
)
from .pytorch_matrix import (
    ParsedBuildMatrix,
    PyTorchHarvest,
    PyTorchHarvestError,
    PyTorchMatrixHarvester,
    facts_from_build_script,
    harvest_pytorch_tag,
    parse_build_script,
)

__all__ = [
    "CachedHTTPClient",
    "FetchResult",
    "GitHubHarvestError",
    "GitHubReleaseHarvest",
    "GitHubReleaseHarvester",
    "HarvestHTTPError",
    "NormalizedWheel",
    "NvidiaHarvestError",
    "NvidiaTableHarvester",
    "ParsedBuildMatrix",
    "PyPIHarvest",
    "PyPIHarvestError",
    "PyPIHarvester",
    "PyTorchHarvest",
    "PyTorchHarvestError",
    "PyTorchMatrixHarvester",
    "WheelFilenameError",
    "facts_from_build_script",
    "harvest_pypi",
    "harvest_pytorch_tag",
    "harvest_release",
    "normalise_many",
    "normalise_wheel_filename",
    "normalize_wheel_filename",
    "parse_build_script",
    "parse_driver_table",
    "parse_pypi_payload",
    "parse_release_payload",
    "parse_wheel_asset",
    "try_normalise_wheel_filename",
]
