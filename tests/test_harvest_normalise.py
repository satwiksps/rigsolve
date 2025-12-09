from __future__ import annotations

import pytest

from rigsolve.harvest.normalise import (
    WheelFilenameError,
    normalise_wheel_filename,
)


def test_flash_attn_local_version_axes_are_parsed_separately_from_pep425() -> None:
    wheel = normalise_wheel_filename(
        "flash_attn-2.8.3+cu12torch2.8cxx11abiFALSE-cp312-cp312-linux_x86_64.whl"
    )
    assert wheel.distribution == "flash-attn"
    assert wheel.public_version == "2.8.3"
    assert wheel.cuda_line == "12"
    assert wheel.torch_version == "2.8"
    assert wheel.cxx11abi is False
    assert wheel.python_tag == "cp312"
    assert wheel.abi_tag == "cp312"
    assert wheel.platform_tag == "linux_x86_64"


def test_percent_encoded_asset_url_and_cu_three_digit_convention() -> None:
    wheel = normalise_wheel_filename(
        "https://example.test/xformers-0.0.30%2Bcu128-cp311-cp311-manylinux_2_28_x86_64.whl"
    )
    assert wheel.filename.startswith("xformers-0.0.30+cu128")
    assert wheel.cuda_line == "12.8"


def test_compressed_pep425_platform_tags_are_not_lost() -> None:
    wheel = normalise_wheel_filename(
        "triton-3.7.1-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl"
    )
    assert wheel.platform_tags == (
        "manylinux_2_27_x86_64",
        "manylinux_2_28_x86_64",
    )
    assert wheel.platform_tag == ("manylinux_2_27_x86_64.manylinux_2_28_x86_64")


def test_distribution_and_version_expectations_use_pep_normalisation() -> None:
    wheel = normalise_wheel_filename(
        "my_pkg-1.0.0-py3-none-any.whl",
        expected_distribution="my-pkg",
        expected_version="1.0",
    )
    assert wheel.distribution == "my-pkg"
    with pytest.raises(WheelFilenameError, match="does not match"):
        normalise_wheel_filename("my_pkg-1.0-py3-none-any.whl", expected_distribution="other")


def test_invalid_wheel_is_rejected() -> None:
    with pytest.raises(WheelFilenameError, match="invalid wheel"):
        normalise_wheel_filename("not-a-wheel.whl")
