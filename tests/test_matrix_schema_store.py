from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from rigsolve.matrix import (
    CouplingFact,
    MatrixStore,
    MatrixValidationError,
    Source,
    TorchBuildFact,
    VerificationTier,
    WheelFact,
    dump_matrix,
    load_bundled,
)


def test_source_requires_date_and_stable_locator() -> None:
    with pytest.raises(ValueError, match="url or repo"):
        Source(kind="gh-release", harvested="2026-08-15")
    with pytest.raises(ValueError, match="ISO date"):
        Source(kind="gh-release", harvested="yesterday", repo="owner/repo")


def test_fact_schema_is_frozen_and_normalises_package_names() -> None:
    source = Source(
        kind="gh-release",
        harvested=date(2026, 8, 15),
        repo="owner/repo",
        tag="v1.0",
    )
    fact = WheelFact(
        package="Flash_Attn",
        version="2.8.3",
        url="https://example.test/example.whl",
        source=source,
    )
    assert fact.package == "flash-attn"
    with pytest.raises(FrozenInstanceError):
        fact.version = "9"  # type: ignore[misc]


def test_tier_zero_is_explicitly_not_verified() -> None:
    assert VerificationTier.DERIVED.label == "derived"
    assert not VerificationTier.DERIVED.verified
    assert VerificationTier.RUNS.verified


def test_every_toml_fact_must_have_provenance() -> None:
    text = """
[meta]
schema_version = 1
matrix_version = "test"
generated = "2026-08-15"

[[wheel]]
package = "example"
version = "1.0"
url = "https://example.test/example.whl"
tier = 0
"""
    with pytest.raises(MatrixValidationError, match="source"):
        MatrixStore.from_toml(text)


def test_unknown_fields_fail_instead_of_being_silently_ignored() -> None:
    text = """
[meta]
schema_version = 1
matrix_version = "test"
generated = "2026-08-15"
typo = "unsafe"
"""
    with pytest.raises(MatrixValidationError, match="unknown meta field"):
        MatrixStore.from_toml(text)


def test_bundled_matrix_is_offline_and_honestly_tier_zero() -> None:
    matrix = load_bundled()
    assert matrix.matrix_version == "2026.08.15"
    assert matrix.stats().fact_count >= 30
    assert set(matrix.packages) >= {
        "torch",
        "torchvision",
        "torchaudio",
        "flash-attn",
        "xformers",
        "bitsandbytes",
        "triton",
        "vllm",
        "flashinfer-python",
        "transformers",
    }
    assert all(fact.tier is VerificationTier.DERIVED for fact in matrix.facts)
    assert all(not fact.archs for fact in matrix.wheels)


def test_bundled_queries_normalise_names_and_package_specific_cuda_line() -> None:
    matrix = load_bundled()
    wheels = matrix.wheels_for(
        "flash_attn",
        version="2.8.3",
        torch="2.8.0",
        cuda_line="12.8",
        python="3.12",
    )
    assert len(wheels) == 2
    assert {wheel.cxx11abi for wheel in wheels} == {False, True}
    assert matrix.driver_minimum("12.8") == "525"


def test_release_sets_are_tuples_not_false_version_lockstep() -> None:
    matrix = load_bundled()
    release = next(
        fact
        for fact in matrix.compatible_release_sets("torch")
        if fact.version_map["torch"] == "2.8.0"
    )
    assert release.version_map == {
        "torch": "2.8.0",
        "torchvision": "0.23.0",
        "torchaudio": "2.8.0",
    }


def test_coupling_package_and_version_order_is_canonical() -> None:
    source = Source(
        kind="official-docs",
        harvested="2026-08-15",
        url="https://example.test/compatibility",
    )
    forward = CouplingFact(
        kind="compatible-release-set",
        packages=("torchvision", "torch"),
        versions=(("torchvision", "0.23.0"), ("torch", "2.8.0")),
        source=source,
    )
    reverse = CouplingFact(
        kind="compatible-release-set",
        packages=("torch", "torchvision"),
        versions={"torch": "2.8.0", "torchvision": "0.23.0"},
        source=source,
    )

    assert forward == reverse
    assert forward.packages == ("torch", "torchvision")
    assert forward.versions == (("torch", "2.8.0"), ("torchvision", "0.23.0"))
    assert forward.key == reverse.key


def test_dump_round_trip_is_byte_stable_and_digest_stable() -> None:
    original = load_bundled()
    payload = dump_matrix(original)
    loaded = MatrixStore.from_toml(payload)
    assert dump_matrix(loaded) == payload
    assert loaded.digest == original.digest


def test_stats_report_fact_families_sources_and_harvest_window() -> None:
    stats = load_bundled().stats().as_dict()
    assert stats["families"]["wheel"] >= 10
    assert stats["sources"]["build-script"] >= 1
    assert stats["tiers"] == {"0": stats["fact_count"]}
    assert stats["oldest_harvest"] == "2026-08-15"


def test_known_broken_matching_requires_every_recorded_dimension() -> None:
    matrix = MatrixStore.from_toml(
        """
[meta]
schema_version = 1
matrix_version = "negative-test"
generated = "2026-08-15"

[[known_broken]]
id = "bad-edge"
description = "An upstream-reported bad edge."
match = { package = "flash_attn", version = "2.8.3", torch = "2.9" }
workaround = "Use the explicit fixed asset."
tier = 0
[known_broken.source]
kind = "user-report"
url = "https://example.test/issues/1"
confirmed_by = 1
harvested = "2026-08-15"
"""
    )
    assert not matrix.known_broken_for({"package": "flash-attn", "version": "2.8.3"})
    assert [
        fact.id
        for fact in matrix.known_broken_for(
            {"package": "flash_attn", "version": "2.8.3", "torch": "2.9.0"}
        )
    ] == ["bad-edge"]


def test_known_broken_scopes_are_directional_and_never_broadened() -> None:
    matrix = MatrixStore.from_toml(
        """
[meta]
schema_version = 1
matrix_version = "negative-scope-test"
generated = "2026-08-15"

[[known_broken]]
id = "narrow-edge"
description = "A narrowly scoped edge."
match = { package = "flash-attn", version = "2.8.3", torch = "2.9.0", cuda_line = "12.4" }
workaround = "Use another build."
tier = 0
[known_broken.source]
kind = "user-report"
url = "https://example.test/issues/2"
harvested = "2026-08-15"
"""
    )
    exact = {
        "package": "flash-attn",
        "version": "2.8.3+local",
        "torch": "2.9.0+cu124",
        "cuda_line": "12.4.1",
    }
    assert [fact.id for fact in matrix.known_broken_for(exact)] == ["narrow-edge"]
    assert not matrix.known_broken_for({**exact, "torch": "2.9.1"})
    assert not matrix.known_broken_for({**exact, "cuda_line": "12"})
    assert not matrix.known_broken_for({**exact, "torch": "2.9.0rc1"})


def test_known_broken_matches_any_recorded_wheel_axis_value() -> None:
    matrix = MatrixStore.from_toml(
        """
[meta]
schema_version = 1
matrix_version = "negative-wheel-axis-test"
generated = "2026-08-15"

[[known_broken]]
id = "platform-edge"
description = "A platform-specific edge."
match = { package = "demo", version = "1.0", python = "cp312", platform = "linux_x86_64", source_build = false }
workaround = "Use another wheel."
[known_broken.source]
kind = "user-report"
url = "https://example.test/issues/3"
harvested = "2026-08-15"
"""
    )
    assignment = {
        "package": "demo",
        "version": "1.0",
        "python": ("cp311", "cp312"),
        "platform": ("manylinux_2_28_x86_64", "linux_x86_64"),
        "source_build": False,
    }
    assert [fact.id for fact in matrix.known_broken_for(assignment)] == ["platform-edge"]


def test_matrix_rejects_mixed_coupling_semantics_for_one_package_set() -> None:
    with pytest.raises(MatrixValidationError, match="mixes incompatible coupling kinds"):
        MatrixStore.from_toml(
            """
[meta]
schema_version = 1
matrix_version = "mixed-coupling"
generated = "2026-08-15"

[[couple]]
kind = "exact-version-lockstep"
packages = ["a", "b"]
[couple.source]
kind = "official-docs"
url = "https://example.test/lockstep"
harvested = "2026-08-15"

[[couple]]
kind = "compatible-release-set"
packages = ["a", "b"]
versions = { a = "1", b = "2" }
[couple.source]
kind = "official-docs"
url = "https://example.test/tuple"
harvested = "2026-08-15"
"""
        )


def test_validation_rejects_tier_three_wheel_without_tested_architecture() -> None:
    text = """
[meta]
schema_version = 1
matrix_version = "test"
generated = "2026-08-15"

[[wheel]]
package = "example"
version = "1.0"
url = "https://example.test/example.whl"
sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
python = "cp312"
abi = "cp312"
platform = "linux_x86_64"
tier = 3
[wheel.source]
kind = "gpu-run"
url = "https://example.test/runs/1"
harvested = "2026-08-15"
"""
    with pytest.raises(MatrixValidationError, match="tier 3"):
        MatrixStore.from_toml(text)


@pytest.mark.parametrize("url", ["http://example.test/example.whl", "/example.whl"])
def test_wheel_install_url_must_be_absolute_https(url: str) -> None:
    source = Source(kind="gh-release", harvested="2026-08-15", repo="owner/repo")
    with pytest.raises(MatrixValidationError, match=r"wheel\.url must be an absolute HTTPS URL"):
        WheelFact(package="example", version="1", url=url, source=source)


@pytest.mark.parametrize("url", ["http://download.example.test/cu124", "/cu124"])
def test_torch_index_url_must_be_absolute_https(url: str) -> None:
    source = Source(kind="build-script", harvested="2026-08-15", repo="owner/repo")
    with pytest.raises(
        MatrixValidationError,
        match=r"torch_build\.index_url must be an absolute HTTPS URL",
    ):
        TorchBuildFact(
            version="2.6.0",
            cuda_line="12.4",
            index_url=url,
            source=source,
        )


def test_source_provenance_url_may_remain_http() -> None:
    source = Source(
        kind="gh-release",
        harvested="2026-08-15",
        url="http://evidence.example.test/release",
    )
    fact = WheelFact(
        package="example",
        version="1",
        url="https://example.test/example.whl",
        source=source,
    )
    assert fact.source.url == "http://evidence.example.test/release"


@pytest.mark.parametrize(
    ("tier", "kind"),
    [
        (VerificationTier.INSTALLS, "install-test"),
        (VerificationTier.IMPORTS, "import-test"),
        (VerificationTier.RUNS, "gpu-run"),
    ],
)
def test_verified_wheel_requires_artifact_digest_and_tier_capable_execution_source(
    tier: VerificationTier,
    kind: str,
) -> None:
    source = Source(kind=kind, harvested="2026-08-15", url="https://example.test/run/1")
    fact = WheelFact(
        package="example",
        version="1",
        url="https://example.test/example.whl",
        source=source,
        sha256="a" * 64,
        python="cp312",
        abi="cp312",
        platform="linux_x86_64",
        archs=("sm_89",) if tier is VerificationTier.RUNS else (),
        tier=tier,
    )
    assert fact.tier is tier


def test_verified_wheel_rejects_missing_artifact_digest() -> None:
    source = Source(kind="import-test", harvested="2026-08-15", url="https://example.test/run/1")
    with pytest.raises(MatrixValidationError, match=r"require wheel\.sha256"):
        WheelFact(
            package="example",
            version="1",
            url="https://example.test/example.whl",
            source=source,
            tier=VerificationTier.IMPORTS,
        )


def test_verified_wheel_requires_immutable_platform_scope() -> None:
    source = Source(kind="install-test", harvested="2026-08-15", url="https://example.test/run/1")
    with pytest.raises(MatrixValidationError, match=r"wheel\.python"):
        WheelFact(
            package="example",
            version="1",
            url="https://example.test/example.whl",
            source=source,
            sha256="a" * 64,
            tier=VerificationTier.INSTALLS,
        )


def test_verified_native_wheel_requires_build_axes() -> None:
    source = Source(kind="import-test", harvested="2026-08-15", url="https://example.test/run/1")
    with pytest.raises(MatrixValidationError, match=r"flash-attn.*cuda_line"):
        WheelFact(
            package="flash-attn",
            version="2.8.3",
            url="https://example.test/flash.whl",
            source=source,
            sha256="a" * 64,
            python="cp312",
            abi="cp312",
            platform="linux_x86_64",
            tier=VerificationTier.IMPORTS,
        )


def test_known_broken_rejects_unmatchable_fields() -> None:
    with pytest.raises(MatrixValidationError, match="unknown field"):
        MatrixStore.from_mapping(
            {
                "meta": {
                    "schema_version": 1,
                    "matrix_version": "test",
                    "generated": "2026-08-15",
                },
                "known_broken": [
                    {
                        "id": "typo",
                        "description": "typo",
                        "match": {"pakcage": "torch"},
                        "workaround": "fix it",
                        "tier": 0,
                        "source": {
                            "kind": "issue",
                            "url": "https://example.test/issue/1",
                            "harvested": "2026-08-15",
                        },
                    }
                ],
            }
        )


@pytest.mark.parametrize("kind", ["gh-release", "official-docs", "build-script"])
def test_verified_wheel_rejects_generic_artifact_or_documentation_source(kind: str) -> None:
    source = Source(kind=kind, harvested="2026-08-15", repo="owner/repo")
    with pytest.raises(MatrixValidationError, match="requires execution provenance"):
        WheelFact(
            package="example",
            version="1",
            url="https://example.test/example.whl",
            source=source,
            sha256="a" * 64,
            tier=VerificationTier.INSTALLS,
        )


def test_execution_source_cannot_claim_a_higher_tier_than_it_demonstrates() -> None:
    source = Source(kind="install-test", harvested="2026-08-15", url="https://example.test/run/1")
    with pytest.raises(MatrixValidationError, match="wheel tier 2"):
        WheelFact(
            package="example",
            version="1",
            url="https://example.test/example.whl",
            source=source,
            sha256="a" * 64,
            tier=VerificationTier.IMPORTS,
        )


@pytest.mark.parametrize(
    "fact",
    [
        """
[[torch_build]]
version = "2.6.0"
cuda_line = "12.4"
index_url = "https://download.example.test/cu124"
tier = 1
[torch_build.source]
kind = "install-test"
url = "https://example.test/run/1"
harvested = "2026-08-15"
""",
        """
[[tested_against]]
package = "torch"
version = "2.6.0"
cuda_exact = "12.4.1"
tier = 1
[tested_against.source]
kind = "install-test"
url = "https://example.test/run/1"
harvested = "2026-08-15"
""",
        """
[[constraint]]
kind = "driver-min"
cuda_runtime = "12.x"
min_driver = { linux = "525" }
tier = 1
[constraint.source]
kind = "install-test"
url = "https://example.test/run/1"
harvested = "2026-08-15"
""",
        """
[[couple]]
kind = "compatible-release-set"
packages = ["torch", "torchvision"]
versions = { torch = "2.6.0", torchvision = "0.21.0" }
tier = 1
[couple.source]
kind = "install-test"
url = "https://example.test/run/1"
harvested = "2026-08-15"
""",
        """
[[known_broken]]
id = "example-failure"
description = "An example failure."
match = { package = "example", version = "1" }
workaround = "Use version 2."
tier = 1
[known_broken.source]
kind = "install-test"
url = "https://example.test/run/1"
harvested = "2026-08-15"
""",
        """
[[architecture]]
arch = "sm_89"
cuda_min = "11.8"
tier = 1
[architecture.source]
kind = "install-test"
url = "https://example.test/run/1"
harvested = "2026-08-15"
""",
        """
[[source_build]]
package = "example"
tier = 1
[source_build.source]
kind = "install-test"
url = "https://example.test/run/1"
harvested = "2026-08-15"
""",
    ],
)
def test_non_artifact_fact_families_cannot_claim_execution_tiers(fact: str) -> None:
    text = f"""\
[meta]
schema_version = 1
matrix_version = "test"
generated = "2026-08-15"
{fact}
"""
    with pytest.raises(MatrixValidationError, match=r"tier must be 0.*immutable artifact"):
        MatrixStore.from_toml(text)
