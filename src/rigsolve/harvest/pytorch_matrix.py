"""Extract PyTorch's binary CUDA matrix from tagged build scripts."""

from __future__ import annotations

import ast
import hashlib
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote

from packaging.version import InvalidVersion, Version

from rigsolve.matrix.provenance import Source, VerificationTier
from rigsolve.matrix.schema import TestedAgainstFact, TorchBuildFact

from .cache import CachedHTTPClient, HarvestHTTPError

PYTORCH_REPO = "pytorch/pytorch"
BUILD_MATRIX_PATH = ".github/scripts/generate_binary_build_matrix.py"


class PyTorchHarvestError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ParsedBuildMatrix:
    cuda_lines: tuple[str, ...]
    exact_versions: tuple[tuple[str, str], ...]
    python_versions: tuple[str, ...]

    @property
    def exact_version_map(self) -> dict[str, str]:
        return dict(self.exact_versions)


@dataclass(frozen=True, slots=True)
class PyTorchHarvest:
    tag: str
    version: str
    builds: tuple[TorchBuildFact, ...]
    tested_against: tuple[TestedAgainstFact, ...]
    parsed: ParsedBuildMatrix


def _literal_assignments(source: str) -> dict[str, Any]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise PyTorchHarvestError(f"invalid Python build script: {exc}") from exc
    values: dict[str, Any] = {}
    wanted = {
        "CUDA_ARCHES",
        "CUDA_ARCHES_FULL_VERSION",
        "FULL_PYTHON_VERSIONS",
    }
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
            selected = wanted.intersection(names)
            if not selected:
                continue
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
            for name in selected:
                values[name] = value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id not in wanted or node.value is None:
                continue
            try:
                values[node.target.id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
    return values


def parse_build_script(source: str) -> ParsedBuildMatrix:
    """Statically read literal matrix constants; never execute upstream code."""

    assignments = _literal_assignments(source)
    cuda = assignments.get("CUDA_ARCHES")
    if not isinstance(cuda, (list, tuple)) or not cuda:
        raise PyTorchHarvestError("build script has no literal CUDA_ARCHES list")
    cuda_lines = tuple(str(item) for item in cuda)
    if any(not all(part.isdigit() for part in item.split(".")) for item in cuda_lines):
        raise PyTorchHarvestError("CUDA_ARCHES contains a non-version value")

    raw_exact = assignments.get("CUDA_ARCHES_FULL_VERSION", {})
    if not isinstance(raw_exact, dict):
        raise PyTorchHarvestError("CUDA_ARCHES_FULL_VERSION is not a literal table")
    exact: list[tuple[str, str]] = []
    for line, full in raw_exact.items():
        line_string = str(line)
        full_string = str(full)
        if line_string not in cuda_lines:
            continue
        if not full_string.startswith(line_string + ".") and full_string != line_string:
            raise PyTorchHarvestError(
                f"full CUDA version {full_string!r} does not match line {line_string!r}"
            )
        exact.append((line_string, full_string))

    raw_python = assignments.get("FULL_PYTHON_VERSIONS", [])
    if not isinstance(raw_python, (list, tuple)):
        raise PyTorchHarvestError("FULL_PYTHON_VERSIONS is not a literal list")
    python_versions = tuple(str(item) for item in raw_python)
    return ParsedBuildMatrix(
        cuda_lines=tuple(dict.fromkeys(cuda_lines)),
        exact_versions=tuple(sorted(exact)),
        python_versions=tuple(dict.fromkeys(python_versions)),
    )


def _version_from_tag(tag: str) -> str:
    candidate = tag[1:] if tag.startswith("v") else tag
    try:
        return str(Version(candidate))
    except InvalidVersion as exc:
        raise PyTorchHarvestError(f"cannot derive PyTorch version from tag {tag!r}") from exc


def facts_from_build_script(
    source_text: str,
    *,
    tag: str,
    harvested: date | str,
    source_url: str | None = None,
    etag: str | None = None,
) -> PyTorchHarvest:
    parsed = parse_build_script(source_text)
    version = _version_from_tag(tag)
    url = source_url or (
        f"https://raw.githubusercontent.com/{PYTORCH_REPO}/{quote(tag, safe='')}/"
        f"{BUILD_MATRIX_PATH}"
    )
    source = Source(
        kind="build-script",
        repo=PYTORCH_REPO,
        tag=tag,
        path=BUILD_MATRIX_PATH,
        url=url,
        harvested=harvested,
        etag=etag,
        sha256=hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
    )
    exact = parsed.exact_version_map
    builds = tuple(
        TorchBuildFact(
            version=version,
            cuda_line=cuda_line,
            cuda_exact=exact.get(cuda_line),
            index_url=("https://download.pytorch.org/whl/cu" + cuda_line.replace(".", "")),
            pythons=parsed.python_versions,
            # The script names build axes.  It does not by itself establish a
            # C++ ABI value, wheel platform compatibility, or kernel arch list.
            platforms=(),
            cxx11abi=None,
            tier=VerificationTier.DERIVED,
            source=source,
        )
        for cuda_line in parsed.cuda_lines
    )
    tested = tuple(
        TestedAgainstFact(
            package="torch",
            version=version,
            cuda_exact=full,
            note=(
                f"Exact CUDA version declared for the {line} binary-build axis; "
                "tier 0 records build metadata, not a runtime verification."
            ),
            tier=VerificationTier.DERIVED,
            source=source,
        )
        for line, full in parsed.exact_versions
    )
    return PyTorchHarvest(
        tag=tag,
        version=version,
        builds=builds,
        tested_against=tested,
        parsed=parsed,
    )


class PyTorchMatrixHarvester:
    def __init__(
        self,
        cache_dir: str | os.PathLike[str],
        *,
        client: CachedHTTPClient | None = None,
    ) -> None:
        self.client = client or CachedHTTPClient(Path(cache_dir) / "pytorch")

    def tag(
        self,
        tag: str,
        *,
        harvested: date | str | None = None,
        offline: bool = False,
    ) -> PyTorchHarvest:
        url = (
            f"https://raw.githubusercontent.com/{PYTORCH_REPO}/"
            f"{quote(tag, safe='')}/{BUILD_MATRIX_PATH}"
        )
        try:
            response = self.client.get(url, offline=offline)
        except HarvestHTTPError as exc:
            raise PyTorchHarvestError(str(exc)) from exc
        return facts_from_build_script(
            response.text(),
            tag=tag,
            harvested=harvested or date.today(),
            source_url=url,
            etag=response.etag,
        )


def harvest_pytorch_tag(tag: str, *, cache_dir: str | os.PathLike[str]) -> PyTorchHarvest:
    return PyTorchMatrixHarvester(cache_dir).tag(tag)


__all__ = [
    "BUILD_MATRIX_PATH",
    "PYTORCH_REPO",
    "ParsedBuildMatrix",
    "PyTorchHarvest",
    "PyTorchHarvestError",
    "PyTorchMatrixHarvester",
    "facts_from_build_script",
    "harvest_pytorch_tag",
    "parse_build_script",
]
