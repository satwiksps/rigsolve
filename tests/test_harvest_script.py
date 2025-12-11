from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from rigsolve.matrix import Source, VerificationTier, WheelFact


def _script_module() -> ModuleType:
    path = Path(__file__).parents[1] / ".github" / "scripts" / "harvest_matrix.py"
    spec = importlib.util.spec_from_file_location("rigsolve_harvest_script", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_harvester_never_downgrades_verified_evidence() -> None:
    script = _script_module()
    common = {
        "package": "example-native",
        "version": "1.0.0",
        "url": "https://example.test/example_native-1.0.0-cp312-cp312-linux_x86_64.whl",
        "filename": "example_native-1.0.0-cp312-cp312-linux_x86_64.whl",
        "python": "cp312",
        "abi": "cp312",
        "platform": "linux_x86_64",
        "sha256": "a" * 64,
    }
    verified = WheelFact(
        **common,
        tier=VerificationTier.INSTALLS,
        source=Source(
            kind="install-test",
            harvested="2026-08-15",
            url="https://example.test/runs/1",
        ),
    )
    harvested = WheelFact(
        **common,
        tier=VerificationTier.DERIVED,
        source=Source(
            kind="pypi-json",
            harvested="2026-08-15",
            url="https://pypi.org/pypi/example-native/1.0.0/json",
        ),
    )

    assert script._new_or_changed((harvested,), (verified,)) == ()


def test_harvester_preserves_immutable_artifact_identity() -> None:
    script = _script_module()
    common = {
        "package": "example-native",
        "version": "1.0.0",
        "url": "https://example.test/example_native-1.0.0-cp312-cp312-linux_x86_64.whl",
        "filename": "example_native-1.0.0-cp312-cp312-linux_x86_64.whl",
        "python": "cp312",
        "abi": "cp312",
        "platform": "linux_x86_64",
        "tier": VerificationTier.DERIVED,
        "source": Source(
            kind="pypi-json",
            harvested="2026-08-15",
            url="https://pypi.org/pypi/example-native/1.0.0/json",
        ),
    }
    existing = WheelFact(**common, sha256="a" * 64)
    changed = WheelFact(**common, sha256="b" * 64)

    assert script._new_or_changed((changed,), (existing,)) == ()
