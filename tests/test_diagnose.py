from __future__ import annotations

from tests.test_resolver import store

from rigsolve.detect import (
    DriverInfo,
    GPUDevice,
    InstalledEnvironment,
    InstalledPackage,
    MachineProfile,
    PlatformInfo,
    TorchBuild,
)
from rigsolve.diagnose import check_environment, format_check_report
from rigsolve.matrix import MatrixStore, load_bundled
from rigsolve.plan.install import InstallPlan, InstallStep
from rigsolve.plan.lockfile import write_lockfile
from rigsolve.solve.resolver import resolve


def test_cuda_line_mismatch_is_actionable() -> None:
    profile = MachineProfile(
        driver=DriverInfo("560.35", "12.6"),
        platform=PlatformInfo(os="linux", architecture="x86_64", python_version="3.12"),
        installed=InstalledEnvironment(
            packages=(
                InstalledPackage("torch", "2.6.0", cuda_line="12.4"),
                InstalledPackage("flash-attn", "2.8.3", cuda_line="11", torch_version="2.6"),
            ),
            torch=TorchBuild("2.6.0", cuda_version="12.4.1", cxx11_abi=False),
        ),
    )
    report = check_environment(profile, store())
    assert not report.healthy
    assert any(item.code == "cuda-line-mismatch" for item in report.violations)
    text = format_check_report(report)
    assert "libcudart.so.11" in text
    assert "fix:" in text
    mismatch = next(item for item in report.violations if item.code == "cuda-line-mismatch")
    assert mismatch.citations == ()


def test_native_mismatch_cites_only_an_applicable_wheel() -> None:
    profile = MachineProfile(
        platform=PlatformInfo(
            os="linux",
            architecture="x86_64",
            python_version="3.12",
            python_abi_tag="cp312",
        ),
        installed=InstalledEnvironment(
            packages=(
                InstalledPackage("torch", "2.6.0", cuda_line="13"),
                InstalledPackage(
                    "flash-attn",
                    "2.8.3",
                    cuda_line="12",
                    torch_version="2.6",
                    cxx11_abi=False,
                ),
            ),
            torch=TorchBuild("2.6.0", cuda_version="13.0", cxx11_abi=False),
        ),
    )
    report = check_environment(profile, store())
    mismatch = next(item for item in report.violations if item.code == "cuda-line-mismatch")
    assert mismatch.citations == ("gh-release example/flash v2.8.3, harvested 2026-08-15",)


def test_unknown_native_metadata_does_not_create_false_positive() -> None:
    profile = MachineProfile(
        platform=PlatformInfo(os="linux", architecture="x86_64", python_version="3.12"),
        installed=InstalledEnvironment(
            packages=(InstalledPackage("transformers", "4.0.0"),),
        ),
    )
    assert check_environment(profile, store()).healthy


def test_lockfile_reports_missing_and_drifted_packages(tmp_path) -> None:
    plan = InstallPlan(
        requested=("flash-attn",),
        steps=(
            InstallStep("torch", "2.6.0"),
            InstallStep("flash-attn", "2.8.3", dependencies=("torch",)),
        ),
        matrix_version="test",
        matrix_digest="a" * 64,
    )
    lockfile = tmp_path / "rigsolve.toml"
    write_lockfile(plan, lockfile)
    profile = MachineProfile(
        installed=InstalledEnvironment(
            packages=(InstalledPackage("torch", "2.5.0"),),
        )
    )
    report = check_environment(profile, store(), lockfile=lockfile)
    codes = {item.code for item in report.violations}
    assert {"lock-version-drift", "lock-missing"}.issubset(codes)


def test_lockfile_checks_target_and_native_build_dimensions(tmp_path) -> None:
    plan = InstallPlan(
        requested=("flash-attn",),
        steps=(
            InstallStep("torch", "2.9.0", cuda_line="12.6", cxx11_abi=True),
            InstallStep(
                "flash-attn",
                "2.8.3",
                dependencies=("torch",),
                cuda_line="12",
                torch_version="2.9",
                cxx11_abi=True,
            ),
        ),
        matrix_version="test",
        matrix_digest="a" * 64,
        target={
            "python_version": "3.12",
            "platform": "linux",
            "architecture": "x86_64",
            "compute_capability": "sm_89",
            "compute_capabilities": ("sm_89", "sm_90"),
            "gpu_count": 2,
            "glibc": "2.35",
        },
    )
    lockfile = tmp_path / "rigsolve.toml"
    write_lockfile(plan, lockfile)
    profile = MachineProfile(
        gpus=(GPUDevice(0, "A100", "sm_80", 40960),),
        platform=PlatformInfo(
            os="linux",
            architecture="x86_64",
            python_version="3.11",
            glibc_version="2.31",
        ),
        installed=InstalledEnvironment(
            packages=(
                InstalledPackage("torch", "2.9.0", cuda_line="13", cxx11_abi=False),
                InstalledPackage(
                    "flash-attn",
                    "2.8.3",
                    cuda_line="13",
                    torch_version="2.8",
                    cxx11_abi=False,
                ),
            ),
            torch=TorchBuild("2.9.0", "13.0.0", False),
        ),
    )

    codes = {
        item.code for item in check_environment(profile, store(), lockfile=lockfile).violations
    }
    assert {
        "lock-target-python",
        "lock-target-gpu-architecture",
        "lock-target-gpu-architectures",
        "lock-target-gpu-count",
        "lock-target-glibc",
        "lock-cuda-drift",
        "lock-cxx11abi-drift",
        "lock-torch-build-drift",
        "lock-matrix-drift",
    }.issubset(codes)


def test_checker_covers_driver_arch_abi_torch_and_known_broken_edges() -> None:
    profile = MachineProfile(
        gpus=(GPUDevice(0, "RTX 4090", "sm_89", 24564),),
        driver=DriverInfo("550.54", "12.4"),
        platform=PlatformInfo(
            os="linux",
            architecture="x86_64",
            python_version="3.12",
            python_abi_tag="cp312",
        ),
        installed=InstalledEnvironment(
            packages=(
                InstalledPackage("torch", "2.9.0", cuda_line="13"),
                InstalledPackage(
                    "flash-attn",
                    "2.8.3.post1",
                    cuda_line="13",
                    torch_version="2.9",
                    cxx11_abi=False,
                    source_build=False,
                ),
                InstalledPackage("xformers", "0.0.35", torch_version="2.8"),
                InstalledPackage("torchvision", "0.21.0"),
            ),
            torch=TorchBuild(
                "2.9.0",
                cuda_version="13.0.0",
                cxx11_abi=True,
                archs=("sm_80",),
            ),
        ),
    )
    report = check_environment(profile, load_bundled())
    codes = {item.code for item in report.violations}
    assert "torch-build-mismatch" in codes
    assert "cxx11abi-mismatch" in codes
    assert "driver-too-old" in codes
    assert "missing-kernel-architecture" in codes
    assert "release-coupling" in codes
    assert "known-broken:flashattn-post1-torch29-filename" in codes


def test_successful_source_build_is_not_the_post1_filename_failure() -> None:
    profile = MachineProfile(
        platform=PlatformInfo(
            os="linux",
            architecture="x86_64",
            python_version="3.12",
            python_abi_tag="cp312",
        ),
        installed=InstalledEnvironment(
            packages=(
                InstalledPackage("torch", "2.9.0", cuda_line="13"),
                InstalledPackage(
                    "flash-attn",
                    "2.8.3.post1",
                    cuda_line="13",
                    torch_version="2.9",
                    cxx11_abi=True,
                    source_build=True,
                ),
            ),
            torch=TorchBuild("2.9.0", cuda_version="13.0", cxx11_abi=True),
        ),
    )

    codes = {item.code for item in check_environment(profile, load_bundled()).violations}
    assert "known-broken:flashattn-post1-torch29-filename" not in codes


def test_source_build_warning_when_exact_wheel_exists() -> None:
    profile = MachineProfile(
        platform=PlatformInfo(
            os="linux",
            architecture="x86_64",
            python_version="3.12",
            python_abi_tag="cp312",
        ),
        installed=InstalledEnvironment(
            packages=(
                InstalledPackage("torch", "2.8.0", cuda_line="12", cxx11_abi=False),
                InstalledPackage(
                    "flash-attn",
                    "2.8.3",
                    cuda_line="12",
                    torch_version="2.8",
                    cxx11_abi=False,
                    source_build=True,
                ),
            ),
            torch=TorchBuild("2.8.0", "12.6.3", False),
        ),
    )
    report = check_environment(profile, load_bundled())
    warning = next(item for item in report.violations if item.code == "avoidable-source-build")
    assert warning.severity == "warning"
    assert warning.fix and warning.fix.endswith(".whl")


def test_source_build_repair_never_recommends_a_foreign_platform_wheel() -> None:
    profile = MachineProfile(
        platform=PlatformInfo(
            os="windows",
            architecture="x86_64",
            python_version="3.12",
            python_abi_tag="cp312",
        ),
        installed=InstalledEnvironment(
            packages=(
                InstalledPackage("torch", "2.8.0", cuda_line="12", cxx11_abi=False),
                InstalledPackage(
                    "flash-attn",
                    "2.8.3",
                    cuda_line="12",
                    torch_version="2.8",
                    cxx11_abi=False,
                    source_build=True,
                ),
            ),
            torch=TorchBuild("2.8.0", "12.6.3", False),
        ),
    )

    report = check_environment(profile, load_bundled())
    assert not any(item.code == "avoidable-source-build" for item in report.violations)


def test_windows_checker_uses_the_windows_driver_floor() -> None:
    driver_store = MatrixStore.from_toml(
        """
[meta]
schema_version = 1
matrix_version = "windows-driver-test"
generated = "2026-08-15"

[[constraint]]
kind = "driver-min"
cuda_runtime = "12.x"
min_driver = { linux = "525", windows = "600" }
[constraint.source]
kind = "nvidia-docs"
url = "https://example.test/driver"
harvested = "2026-08-15"
"""
    )
    profile = MachineProfile(
        driver=DriverInfo("550.0", "12.8"),
        platform=PlatformInfo(os="windows", architecture="x86_64"),
        installed=InstalledEnvironment(
            packages=(InstalledPackage("torch", "2.9.0", cuda_line="12.8"),),
            torch=TorchBuild("2.9.0", "12.8"),
        ),
    )

    report = check_environment(profile, driver_store)
    assert any(
        item.code == "driver-too-old" and "600" in item.summary for item in report.violations
    )


def test_official_release_couplings_accept_cuda_local_version_labels() -> None:
    profile = MachineProfile(
        installed=InstalledEnvironment(
            packages=(
                InstalledPackage("torch", "2.9.0+cu126"),
                InstalledPackage("torchvision", "0.24.0+cu126"),
                InstalledPackage("torchaudio", "2.9.0+cu126"),
            )
        )
    )
    report = check_environment(profile, load_bundled())
    assert not any(item.code == "release-coupling" for item in report.violations)


def test_release_couplings_do_not_reject_unrepresented_versions() -> None:
    profile = MachineProfile(
        installed=InstalledEnvironment(
            packages=(
                InstalledPackage("torch", "9.9.0"),
                InstalledPackage("torchvision", "9.9.0"),
            )
        )
    )
    report = check_environment(profile, load_bundled())
    assert not any(item.code == "release-coupling" for item in report.violations)


def test_release_couplings_do_not_reject_when_only_one_release_is_known() -> None:
    profile = MachineProfile(
        installed=InstalledEnvironment(
            packages=(
                InstalledPackage("torch", "2.9.0"),
                InstalledPackage("torchvision", "9.9.0"),
            )
        )
    )
    report = check_environment(profile, load_bundled())
    assert not any(item.code == "release-coupling" for item in report.violations)


def test_release_couplings_reject_a_wrong_pair_when_both_releases_are_known() -> None:
    profile = MachineProfile(
        installed=InstalledEnvironment(
            packages=(
                InstalledPackage("torch", "2.9.0"),
                InstalledPackage("torchvision", "0.21.0"),
            )
        )
    )
    report = check_environment(profile, load_bundled())
    assert any(item.code == "release-coupling" for item in report.violations)


def test_permuted_coupling_packages_keep_resolver_and_checker_in_parity() -> None:
    coupling_store = MatrixStore.from_toml(
        """
[meta]
schema_version = 1
matrix_version = "permuted-coupling-test"
generated = "2026-08-15"

[[wheel]]
package = "package-a"
version = "1.0"
python = "py3"
abi = "none"
platform = "any"
url = "https://example.test/package_a-1.0-py3-none-any.whl"
tier = 0
[wheel.source]
kind = "gh-release"
url = "https://example.test/package-a/1.0"
harvested = "2026-08-15"

[[wheel]]
package = "package-a"
version = "2.0"
python = "py3"
abi = "none"
platform = "any"
url = "https://example.test/package_a-2.0-py3-none-any.whl"
tier = 0
[wheel.source]
kind = "gh-release"
url = "https://example.test/package-a/2.0"
harvested = "2026-08-15"

[[wheel]]
package = "package-b"
version = "10.0"
python = "py3"
abi = "none"
platform = "any"
url = "https://example.test/package_b-10.0-py3-none-any.whl"
tier = 0
[wheel.source]
kind = "gh-release"
url = "https://example.test/package-b/10.0"
harvested = "2026-08-15"

[[wheel]]
package = "package-b"
version = "20.0"
python = "py3"
abi = "none"
platform = "any"
url = "https://example.test/package_b-20.0-py3-none-any.whl"
tier = 0
[wheel.source]
kind = "gh-release"
url = "https://example.test/package-b/20.0"
harvested = "2026-08-15"

[[couple]]
kind = "compatible-release-set"
packages = ["package-a", "package-b"]
versions = { package-a = "1.0", package-b = "10.0" }
tier = 0
[couple.source]
kind = "official-docs"
url = "https://example.test/tuple-one"
harvested = "2026-08-15"

[[couple]]
kind = "compatible-release-set"
packages = ["package-b", "package-a"]
versions = { package-b = "20.0", package-a = "2.0" }
tier = 0
[couple.source]
kind = "official-docs"
url = "https://example.test/tuple-two"
harvested = "2026-08-15"
"""
    )
    target = MachineProfile(
        platform=PlatformInfo(
            os="linux",
            architecture="x86_64",
            python_version="3.12",
            python_abi_tag="cp312",
        )
    )

    incompatible = resolve(("package-a==1.0", "package-b==20.0"), target, coupling_store)
    compatible = resolve(("package-a==2.0", "package-b==20.0"), target, coupling_store)

    assert not incompatible.satisfiable
    assert compatible.satisfiable

    incompatible_profile = MachineProfile(
        installed=InstalledEnvironment(
            packages=(
                InstalledPackage("package-a", "1.0"),
                InstalledPackage("package-b", "20.0"),
            )
        )
    )
    compatible_profile = MachineProfile(
        installed=InstalledEnvironment(
            packages=(
                InstalledPackage("package-a", "2.0"),
                InstalledPackage("package-b", "20.0"),
            )
        )
    )

    incompatible_report = check_environment(incompatible_profile, coupling_store)
    compatible_report = check_environment(compatible_profile, coupling_store)

    assert any(item.code == "release-coupling" for item in incompatible_report.violations)
    assert not any(item.code == "release-coupling" for item in compatible_report.violations)


def test_exact_lockstep_still_applies_to_unrepresented_versions() -> None:
    lockstep_store = MatrixStore.from_toml(
        """
[meta]
schema_version = 1
matrix_version = "lockstep-test"
generated = "2026-08-15"

[[couple]]
kind = "exact-version-lockstep"
packages = ["package-a", "package-b"]
tier = 0
[couple.source]
kind = "official-docs"
url = "https://example.test/lockstep"
harvested = "2026-08-15"
"""
    )
    profile = MachineProfile(
        installed=InstalledEnvironment(
            packages=(
                InstalledPackage("package-a", "9.9.0"),
                InstalledPackage("package-b", "9.8.0"),
            )
        )
    )
    report = check_environment(profile, lockstep_store)
    assert any(item.code == "release-coupling" for item in report.violations)


def test_exact_lockstep_does_not_reject_unparseable_installed_versions() -> None:
    lockstep_store = MatrixStore.from_toml(
        """
[meta]
schema_version = 1
matrix_version = "lockstep-test"
generated = "2026-08-15"

[[couple]]
kind = "exact-version-lockstep"
packages = ["package-a", "package-b"]
tier = 0
[couple.source]
kind = "official-docs"
url = "https://example.test/lockstep"
harvested = "2026-08-15"
"""
    )
    profile = MachineProfile(
        installed=InstalledEnvironment(
            packages=(
                InstalledPackage("package-a", "vendor-head"),
                InstalledPackage("package-b", "9.8.0"),
            )
        )
    )
    report = check_environment(profile, lockstep_store)
    assert not any(item.code == "release-coupling" for item in report.violations)


def test_release_coupling_cites_only_tuples_anchored_to_observed_versions() -> None:
    coupling_store = MatrixStore.from_toml(
        """
[meta]
schema_version = 1
matrix_version = "citation-test"
generated = "2026-08-15"

[[couple]]
kind = "compatible-release-set"
packages = ["package-a", "package-b"]
versions = { package-a = "1.0", package-b = "10.0" }
tier = 0
[couple.source]
kind = "official-docs"
url = "https://example.test/tuple-one"
harvested = "2026-08-15"

[[couple]]
kind = "compatible-release-set"
packages = ["package-a", "package-b"]
versions = { package-a = "2.0", package-b = "20.0" }
tier = 0
[couple.source]
kind = "official-docs"
url = "https://example.test/tuple-two"
harvested = "2026-08-15"

[[couple]]
kind = "compatible-release-set"
packages = ["package-a", "package-b"]
versions = { package-a = "3.0", package-b = "30.0" }
tier = 0
[couple.source]
kind = "official-docs"
url = "https://example.test/unrelated-tuple"
harvested = "2026-08-15"
"""
    )
    profile = MachineProfile(
        installed=InstalledEnvironment(
            packages=(
                InstalledPackage("package-a", "1.0"),
                InstalledPackage("package-b", "20.0"),
            )
        )
    )
    report = check_environment(profile, coupling_store)
    mismatch = next(item for item in report.violations if item.code == "release-coupling")
    assert mismatch.citations == (
        "official-docs https://example.test/tuple-one, harvested 2026-08-15",
        "official-docs https://example.test/tuple-two, harvested 2026-08-15",
    )


def test_lockfile_version_check_ignores_expected_local_build_label(tmp_path) -> None:
    plan = InstallPlan(
        requested=("torch",),
        steps=(InstallStep("torch", "2.9.0", cuda_line="12.6"),),
        matrix_version="test",
        matrix_digest=store().digest,
    )
    lockfile = tmp_path / "rigsolve.toml"
    write_lockfile(plan, lockfile)
    profile = MachineProfile(
        installed=InstalledEnvironment(
            packages=(InstalledPackage("torch", "2.9.0+cu126", cuda_line="12.6"),)
        )
    )
    report = check_environment(profile, store(), lockfile=lockfile)
    assert not any(item.code == "lock-version-drift" for item in report.violations)


def test_lockfile_torch_build_check_accepts_public_release_prefix(tmp_path) -> None:
    plan = InstallPlan(
        requested=("flash-attn",),
        steps=(
            InstallStep(
                "flash-attn",
                "2.8.3",
                torch_version="2.9",
            ),
        ),
        matrix_version="test",
        matrix_digest=store().digest,
    )
    lockfile = tmp_path / "rigsolve.toml"
    write_lockfile(plan, lockfile)
    profile = MachineProfile(
        installed=InstalledEnvironment(
            packages=(
                InstalledPackage(
                    "flash-attn",
                    "2.8.3",
                    torch_version="2.9.0+cu126",
                ),
            )
        )
    )
    report = check_environment(profile, store(), lockfile=lockfile)
    assert not any(item.code == "lock-torch-build-drift" for item in report.violations)
