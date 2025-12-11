#!/usr/bin/env python3
"""Harvest conservative tier-0 facts and update the bundled matrix atomically."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path
from typing import Any

from packaging.version import InvalidVersion, Version

from rigsolve.harvest import (
    CachedHTTPClient,
    GitHubReleaseHarvester,
    NvidiaTableHarvester,
    PyPIHarvester,
    PyTorchMatrixHarvester,
)
from rigsolve.matrix.provenance import VerificationTier
from rigsolve.matrix.schema import Fact, MatrixData, MatrixMetadata
from rigsolve.matrix.store import MatrixStore, save_matrix

GITHUB_LATEST_PYTORCH = "https://api.github.com/repos/pytorch/pytorch/releases/latest"
DEFAULT_PYPI_PACKAGES = (
    "bitsandbytes",
    "flashinfer-python",
    "transformers",
    "triton",
    "vllm",
    "xformers",
)
FAMILY_ORDER = (
    "wheels",
    "torch_builds",
    "tested_against",
    "constraints",
    "couplings",
    "known_broken",
    "architectures",
    "source_builds",
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Harvest upstream metadata as review-only tier-0 matrix facts."
    )
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument(
        "--pypi-package",
        action="append",
        dest="pypi_packages",
        help="override the default PyPI package set; repeat for multiple packages",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="use only previously cached HTTP responses",
    )
    parser.add_argument(
        "--max-new-facts",
        type=int,
        default=2000,
        help="abort before writing if an upstream change creates too large a diff",
    )
    return parser.parse_args()


def _github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _latest_pytorch_tag(cache: Path, *, offline: bool) -> str:
    client = CachedHTTPClient(cache / "discovery")
    response = client.get(
        GITHUB_LATEST_PYTORCH,
        headers=_github_headers(),
        offline=offline,
    )
    try:
        payload = json.loads(response.text())
    except json.JSONDecodeError as error:
        raise RuntimeError("GitHub returned invalid JSON for the latest PyTorch release") from error
    tag = payload.get("tag_name") if isinstance(payload, dict) else None
    if not isinstance(tag, str) or not tag:
        raise RuntimeError("latest PyTorch release has no tag_name")
    return tag


def _stable_mapping(fact: Fact) -> dict[str, Any]:
    """Ignore response validators and a date-only re-harvest when comparing facts."""

    mapping = fact.to_mapping()
    source = dict(mapping.pop("source"))
    source.pop("harvested", None)
    source.pop("etag", None)
    mapping["source"] = source
    return mapping


_IMMUTABLE_EVIDENCE_FIELDS = {
    "abi",
    "cuda_exact",
    "cuda_line",
    "cxx11abi",
    "filename",
    "kind",
    "path",
    "platform",
    "python",
    "repo",
    "sha256",
    "support",
    "tag",
    "tier",
    "torch",
    "url",
}


def _would_erase_evidence(old: Any, new: Any, path: tuple[str, ...] = ()) -> bool:
    if path and path[-1] in _IMMUTABLE_EVIDENCE_FIELDS and old != new:
        return True
    if isinstance(old, Mapping) and isinstance(new, Mapping):
        return any(
            key not in new or _would_erase_evidence(value, new[key], (*path, str(key)))
            for key, value in old.items()
        )
    if isinstance(old, list) and isinstance(new, list):
        try:
            return not set(old).issubset(new)
        except TypeError:
            return len(new) < len(old)
    return False


def _new_or_changed(incoming: Iterable[Fact], existing: Iterable[Fact]) -> tuple[Fact, ...]:
    old_by_key = {fact.key: fact for fact in existing}
    selected: dict[Any, Fact] = {}
    for fact in incoming:
        if fact.tier is not VerificationTier.DERIVED:
            raise RuntimeError(f"harvester produced non-tier-0 fact: {fact!r}")
        previous = old_by_key.get(fact.key)
        if previous is not None and _stable_mapping(previous) == _stable_mapping(fact):
            continue
        if previous is not None and (
            fact.tier < previous.tier
            or _would_erase_evidence(_stable_mapping(previous), _stable_mapping(fact))
        ):
            print(
                f"warning: preserved curated fact {fact.key!r}; "
                "the harvested replacement would erase recorded evidence",
                file=sys.stderr,
            )
            continue
        duplicate = selected.get(fact.key)
        if duplicate is not None and _stable_mapping(duplicate) != _stable_mapping(fact):
            raise RuntimeError(f"harvesters disagree about fact key {fact.key!r}")
        selected[fact.key] = fact
    return tuple(sorted(selected.values(), key=lambda item: repr(item.key)))


def _harvest(args: argparse.Namespace) -> dict[str, tuple[Fact, ...]]:
    today = date.today()
    cache = args.cache
    token = os.environ.get("GITHUB_TOKEN")

    github = GitHubReleaseHarvester(cache, token=token)
    flash = github.latest(
        "Dao-AILab/flash-attention",
        harvested=today,
        expected_package="flash-attn",
        offline=args.offline,
    )
    try:
        flash_release_version = Version(flash.tag.removeprefix("v"))
    except InvalidVersion as error:
        raise RuntimeError(f"cannot interpret flash-attn release tag {flash.tag!r}") from error
    flash_wheels = tuple(
        fact for fact in flash.wheels if Version(fact.version) == flash_release_version
    )
    mismatched_flash_wheels = len(flash.wheels) - len(flash_wheels)
    if mismatched_flash_wheels:
        print(
            f"warning: ignored {mismatched_flash_wheels} flash-attn wheel(s) whose "
            f"embedded version does not match release tag {flash.tag!r}",
            file=sys.stderr,
        )

    pytorch_tag = _latest_pytorch_tag(cache, offline=args.offline)
    pytorch = PyTorchMatrixHarvester(cache).tag(
        pytorch_tag,
        harvested=today,
        offline=args.offline,
    )

    pypi = PyPIHarvester(cache)
    pypi_wheels: list[Fact] = []
    for package in args.pypi_packages or DEFAULT_PYPI_PACKAGES:
        result = pypi.package(package, harvested=today, offline=args.offline)
        pypi_wheels.extend(result.wheels)

    constraints = NvidiaTableHarvester(cache).driver_table(
        harvested=today,
        offline=args.offline,
    )

    return {
        "wheels": (*flash_wheels, *pypi_wheels),
        "torch_builds": pytorch.builds,
        "tested_against": pytorch.tested_against,
        "constraints": constraints,
        "couplings": (),
        "known_broken": (),
        "architectures": (),
        "source_builds": (),
    }


def main() -> int:
    args = _arguments()
    if args.max_new_facts < 1:
        raise SystemExit("--max-new-facts must be positive")

    base = MatrixStore.load(args.matrix)
    harvested = _harvest(args)
    changes: dict[str, tuple[Fact, ...]] = {}
    for family in FAMILY_ORDER:
        changes[family] = _new_or_changed(
            harvested[family],
            getattr(base.data, family),
        )

    change_count = sum(len(facts) for facts in changes.values())
    if change_count == 0:
        print("No material upstream fact changes.")
        return 0
    if change_count > args.max_new_facts:
        raise SystemExit(
            f"refusing to write {change_count} changed facts; limit is {args.max_new_facts}"
        )

    generated = max(date.today(), base.metadata.generated)
    metadata = MatrixMetadata(
        schema_version=base.metadata.schema_version,
        matrix_version=generated.strftime("%Y.%m.%d"),
        generated=generated,
        description=base.metadata.description,
    )
    incoming = MatrixData(metadata=metadata, **changes)
    merged = base.merge(incoming, conflict="incoming")
    save_matrix(args.matrix, merged)

    summary = ", ".join(
        f"{family}={len(changes[family])}" for family in FAMILY_ORDER if changes[family]
    )
    print(f"Wrote {args.matrix} with {change_count} new or changed tier-0 facts ({summary}).")
    print(f"Matrix {merged.matrix_version}; sha256:{merged.digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
