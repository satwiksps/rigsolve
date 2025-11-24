from __future__ import annotations

import builtins
from pathlib import Path
from typing import Any

from rigsolve.detect.installed import (
    detect_installed,
    inspect_distribution,
    inspect_torch_distribution,
    parse_build_markers,
)

FIXTURES = Path(__file__).parent / "fixtures" / "detect"
SITE_PACKAGES = FIXTURES / "site-packages"


class FakeDistribution:
    def __init__(
        self,
        name: str | None,
        version: str,
        *,
        root: Path = SITE_PACKAGES,
        wheel: str | None = "Wheel-Version: 1.0\nTag: cp312-cp312-linux_x86_64\n",
        direct_url: str | None = None,
    ) -> None:
        self.metadata: dict[str, str] = {} if name is None else {"Name": name}
        self.version = version
        self._root = root
        self._wheel = wheel
        self._direct_url = direct_url

    def locate_file(self, path: str) -> Path:
        return self._root / path

    def read_text(self, filename: str) -> str | None:
        if filename == "WHEEL":
            return self._wheel
        if filename == "direct_url.json":
            return self._direct_url
        return None


def test_native_extension_version_markers() -> None:
    assert parse_build_markers("2.8.3+cu12torch2.8cxx11abiFALSE") == (
        "12",
        "2.8",
        False,
    )
    assert parse_build_markers("0.0.29+cu121torch2.5cxx11abiTRUE") == (
        "12.1",
        "2.5",
        True,
    )
    assert parse_build_markers("4.45.0") == (None, None, None)


def test_distribution_metadata_and_direct_source_url() -> None:
    distribution = FakeDistribution(
        "flash_attn",
        "2.8.3+cu12torch2.8cxx11abiFALSE",
        direct_url='{"url":"https://example.test/flash-attn-2.8.3.tar.gz","archive_info":{}}',
    )
    package = inspect_distribution(distribution)  # type: ignore[arg-type]

    assert package is not None
    assert package.normalized_name == "flash-attn"
    assert package.cuda_version == "12"
    assert package.cuda_line == "12"
    assert package.torch_version == "2.8"
    assert package.cxx11_abi is False
    assert package.wheel_tags == ("cp312-cp312-linux_x86_64",)
    assert package.source_build is True


def test_exact_cuda_marker_keeps_version_and_major_line_distinct() -> None:
    distribution = FakeDistribution("xformers", "0.0.29+cu121torch2.5cxx11abiTRUE")
    package = inspect_distribution(distribution)  # type: ignore[arg-type]

    assert package is not None
    assert package.cuda_version == "12.1"
    assert package.cuda_line == "12"


def test_torch_build_is_recovered_from_files_without_import() -> None:
    distribution = FakeDistribution("torch", "2.6.0")
    build = inspect_torch_distribution(distribution)  # type: ignore[arg-type]

    assert build is not None
    assert build.version == "2.6.0+cu124"
    assert build.cuda_version == "12.4"
    assert build.cuda_line == "12"
    assert build.cxx11_abi is True
    assert build.archs == ("sm_80", "sm_86", "sm_89", "sm_90")
    assert "torch/version.py" in build.evidence


def test_detect_installed_never_imports_torch(monkeypatch: Any) -> None:
    torch_distribution = FakeDistribution("torch", "2.6.0")
    flash_distribution = FakeDistribution("flash-attn", "2.8.3+cu12torch2.8cxx11abiFALSE")
    original_import = builtins.__import__

    def guarded_import(name: str, *args: object, **kwargs: object) -> Any:
        if name == "torch" or name.startswith("torch."):
            raise AssertionError("torch must never be imported during detection")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    result = detect_installed(
        distributions=lambda: [torch_distribution, flash_distribution],  # type: ignore[list-item]
        torch_binary_scan_limit=1024 * 1024,
    )

    assert result.environment.torch is not None
    assert result.environment.get("flash_attn") is not None
    assert result.issues == ()


def test_bad_distribution_metadata_is_skipped() -> None:
    result = detect_installed(
        distributions=lambda: [FakeDistribution(None, "1.0")],  # type: ignore[list-item]
        torch_binary_scan_limit=0,
    )

    assert result.environment.packages == ()
    assert result.issues[0].code == "invalid-distribution-metadata"


def test_metadata_provider_failure_is_structured() -> None:
    def broken_provider() -> object:
        raise RuntimeError("metadata backend exploded")

    result = detect_installed(distributions=broken_provider)  # type: ignore[arg-type]

    assert result.environment.packages == ()
    assert result.issues[0].code == "metadata-enumeration-failed"


def test_direct_wheel_url_is_not_marked_as_source_build() -> None:
    distribution = FakeDistribution(
        "native-demo",
        "1.0",
        direct_url='{"url":"https://example.test/native_demo-1.0-cp312-linux.whl"}',
    )
    package = inspect_distribution(distribution)  # type: ignore[arg-type]

    assert package is not None
    assert package.source_build is False


def test_torch_binary_arch_fallback(tmp_path: Path) -> None:
    torch_root = tmp_path / "torch"
    (torch_root / "lib").mkdir(parents=True)
    (torch_root / "version.py").write_text(
        '__version__ = "2.5.1+cu121"\ncuda = "12.1"\n', encoding="utf-8"
    )
    (torch_root / "lib" / "libtorch_cuda.so").write_bytes(
        b"ELF\x00.target sm_75\x00.target sm_80\x00"
    )
    distribution = FakeDistribution("torch", "2.5.1", root=tmp_path)

    build = inspect_torch_distribution(distribution, binary_scan_limit=1024)  # type: ignore[arg-type]

    assert build is not None
    assert build.archs == ("sm_75", "sm_80")
    assert any(item.startswith("binary:") for item in build.evidence)


def test_torch_distribution_without_package_files_still_reports_metadata(
    tmp_path: Path,
) -> None:
    distribution = FakeDistribution("torch", "2.4.0+cu118", root=tmp_path)

    build = inspect_torch_distribution(distribution)  # type: ignore[arg-type]

    assert build is not None
    assert build.version == "2.4.0+cu118"
    assert build.cuda_version is None
    assert build.evidence == ("distribution-metadata",)


def test_invalid_direct_url_remains_unknown() -> None:
    distribution = FakeDistribution("demo", "1.0", direct_url="{not-json")
    package = inspect_distribution(distribution)  # type: ignore[arg-type]

    assert package is not None
    assert package.source_build is None
