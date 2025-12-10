from __future__ import annotations

import json

from rigsolve.harvest.gh_release import parse_release_payload
from rigsolve.harvest.nvidia_tables import parse_driver_table
from rigsolve.harvest.pypi_index import parse_pypi_payload
from rigsolve.harvest.pytorch_matrix import facts_from_build_script, parse_build_script
from rigsolve.matrix import Source, VerificationTier


def test_github_release_payload_becomes_tier_zero_fact_without_arch_claim() -> None:
    name = "flash_attn-2.8.3+cu12torch2.9cxx11abiTRUE-cp312-cp312-linux_x86_64.whl"
    result = parse_release_payload(
        {
            "tag_name": "v2.8.3",
            "html_url": "https://github.com/example/repo/releases/tag/v2.8.3",
            "assets": [
                {
                    "name": name,
                    "browser_download_url": "https://example.test/" + name,
                    "size": 42,
                    "digest": "sha256:" + "a" * 64,
                },
                {"name": "checksums.txt", "browser_download_url": "https://example.test/c"},
            ],
        },
        repo="example/repo",
        harvested="2026-08-15",
        expected_package="flash-attn",
    )
    assert len(result.wheels) == 1
    fact = result.wheels[0]
    assert fact.tier is VerificationTier.DERIVED
    assert fact.archs == ()
    assert fact.platform == "linux_x86_64"
    assert fact.sha256 == "a" * 64
    assert result.skipped_assets == ("checksums.txt",)


def test_pypi_payload_retains_hash_yank_and_source_only_state() -> None:
    payload = {
        "info": {"name": "demo_pkg", "version": "1.2.0"},
        "urls": [
            {
                "filename": "demo_pkg-1.2.0-py3-none-any.whl",
                "url": "https://files.pythonhosted.org/demo.whl",
                "packagetype": "bdist_wheel",
                "size": 123,
                "digests": {"sha256": "b" * 64},
                "yanked": True,
                "yanked_reason": "bad metadata",
            },
            {
                "filename": "demo_pkg-1.2.0.tar.gz",
                "url": "https://files.pythonhosted.org/demo.tar.gz",
                "packagetype": "sdist",
            },
        ],
    }
    result = parse_pypi_payload(
        json.dumps(payload),
        harvested="2026-08-15",
        api_url="https://pypi.org/pypi/demo-pkg/1.2.0/json",
    )
    assert result.package == "demo-pkg"
    assert result.wheels[0].yanked
    assert result.wheels[0].yanked_reason == "bad metadata"
    assert result.wheels[0].sha256 == "b" * 64
    assert result.sdist_urls == ("https://files.pythonhosted.org/demo.tar.gz",)


BUILD_SCRIPT = """
CUDA_ARCHES = ["11.8", "12.4", "12.6"]
CUDA_ARCHES_FULL_VERSION = {
    "11.8": "11.8.0",
    "12.4": "12.4.1",
    "12.6": "12.6.3",
}
FULL_PYTHON_VERSIONS = ["3.9", "3.10", "3.11", "3.12"]
"""


def test_pytorch_parser_is_static_and_retains_exact_patch_versions() -> None:
    parsed = parse_build_script(BUILD_SCRIPT)
    assert parsed.cuda_lines == ("11.8", "12.4", "12.6")
    assert parsed.exact_version_map["12.4"] == "12.4.1"
    harvested = facts_from_build_script(BUILD_SCRIPT, tag="v2.6.0", harvested="2026-08-15")
    assert [fact.cuda_exact for fact in harvested.builds] == [
        "11.8.0",
        "12.4.1",
        "12.6.3",
    ]
    assert all(fact.support == "build-axis" for fact in harvested.builds)
    assert all(fact.cxx11abi is None for fact in harvested.builds)
    assert all(not fact.platforms for fact in harvested.builds)


def test_nvidia_parser_keeps_minor_and_corresponding_floors_distinct() -> None:
    source = Source(
        kind="nvidia-docs",
        url="https://docs.nvidia.com/example",
        harvested="2026-08-15",
    )
    minor = parse_driver_table(
        """
<table>
  <tr><th>CUDA Toolkit</th><th>Minimum Driver</th><th>Upper</th></tr>
  <tr><td>CUDA 12.x</td><td>&gt;= 525</td><td>&lt; 580</td></tr>
</table>
""",
        source=source,
        compatibility="minor-compatible",
    )
    assert minor[0].cuda_runtime == "12.x"
    assert minor[0].minimum_for("linux") == "525"
    assert minor[0].compatibility == "minor-compatible"

    corresponding = parse_driver_table(
        "CUDA 12.0.x | >=525.60.13 | >=527.41",
        source=source,
        compatibility="toolkit-corresponding",
    )
    assert corresponding[0].minimum_for("linux") == "525.60.13"
    assert corresponding[0].minimum_for("windows") == "527.41"
    assert corresponding[0].compatibility == "toolkit-corresponding"
