"""PEP 440/425-aware normalisation of wheel asset filenames."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse

from packaging.tags import Tag
from packaging.utils import InvalidWheelFilename, canonicalize_name, parse_wheel_filename
from packaging.version import Version

from rigsolve.matrix.provenance import Source, VerificationTier
from rigsolve.matrix.schema import WheelFact


class WheelFilenameError(ValueError):
    """A release asset claims to be a wheel but is not a valid wheel name."""


_CUDA_RE = re.compile(r"(?:^|[.+_-])cu(?P<cuda>\d{2,4})(?=torch|[.+_-]|$)", re.IGNORECASE)
_TORCH_RE = re.compile(
    r"torch(?P<torch>\d+(?:\.\d+){1,2})(?=cxx11abi|[.+_-]|$)",
    re.IGNORECASE,
)
_CXX11_RE = re.compile(r"cxx11abi(?P<abi>true|false|1|0)(?=[.+_-]|$)", re.IGNORECASE)


def _asset_basename(filename_or_url: str) -> str:
    parsed = urlparse(filename_or_url)
    path = parsed.path if parsed.scheme and parsed.netloc else filename_or_url
    return unquote(PurePosixPath(path.replace("\\", "/")).name)


def _cuda_token(token: str) -> str:
    """Decode conventional ``cu118`` while retaining package-specific ``cu12``."""

    if len(token) == 2:
        return str(int(token))
    if len(token) == 3:
        return f"{int(token[:2])}.{int(token[2])}"
    if len(token) == 4:
        # No standard assigns semantics beyond ``cuXY``/``cuXYZ``.  Keeping a
        # dotted best-effort label is preferable to silently dropping metadata.
        return f"{int(token[:2])}.{int(token[2:])}"
    return token


@dataclass(frozen=True, slots=True)
class NormalizedWheel:
    filename: str
    distribution: str
    version: str
    public_version: str
    build_tag: str | None
    tags: tuple[str, ...]
    python_tags: tuple[str, ...]
    abi_tags: tuple[str, ...]
    platform_tags: tuple[str, ...]
    cuda_line: str | None = None
    torch_version: str | None = None
    cxx11abi: bool | None = None

    @property
    def python_tag(self) -> str | None:
        return ".".join(self.python_tags) if self.python_tags else None

    @property
    def abi_tag(self) -> str | None:
        return ".".join(self.abi_tags) if self.abi_tags else None

    @property
    def platform_tag(self) -> str | None:
        return ".".join(self.platform_tags) if self.platform_tags else None

    def to_fact(
        self,
        *,
        url: str,
        source: Source,
        tier: int | VerificationTier = VerificationTier.DERIVED,
        size: int | None = None,
        sha256: str | None = None,
        yanked: bool = False,
        yanked_reason: str | None = None,
    ) -> WheelFact:
        """Create a tier-0 existence fact without inferring glibc or GPU archs."""

        return WheelFact(
            package=self.distribution,
            version=self.public_version,
            cuda_line=self.cuda_line,
            torch=self.torch_version,
            cxx11abi=self.cxx11abi,
            python=self.python_tag,
            abi=self.abi_tag,
            platform=self.platform_tag,
            archs=(),
            url=url,
            filename=self.filename,
            build_tag=self.build_tag,
            size=size,
            sha256=sha256,
            yanked=yanked,
            yanked_reason=yanked_reason,
            tier=VerificationTier.coerce(tier),
            source=source,
        )


def normalise_wheel_filename(
    filename_or_url: str,
    *,
    expected_distribution: str | None = None,
    expected_version: str | Version | None = None,
) -> NormalizedWheel:
    """Parse a wheel filename using ``packaging``, then decode known local tags.

    CUDA, torch, and C++11 ABI are *not* wheel tags.  They are conventions used
    by projects such as flash-attn and are decoded only from the PEP 440 local
    version segment.  Python ABI and platform always come from PEP 425 tags.
    """

    filename = _asset_basename(filename_or_url)
    try:
        distribution, parsed_version, raw_build, parsed_tags = parse_wheel_filename(filename)
    except InvalidWheelFilename as exc:
        raise WheelFilenameError(f"invalid wheel filename {filename!r}: {exc}") from exc

    normalized_distribution = canonicalize_name(distribution)
    if expected_distribution is not None and normalized_distribution != canonicalize_name(
        expected_distribution
    ):
        raise WheelFilenameError(
            f"wheel distribution {normalized_distribution!r} does not match "
            f"{canonicalize_name(expected_distribution)!r}"
        )
    if expected_version is not None and Version(parsed_version.public) != Version(
        str(expected_version)
    ):
        raise WheelFilenameError(
            f"wheel version {parsed_version.public!r} does not match "
            f"{Version(str(expected_version)).public!r}"
        )

    tags: tuple[Tag, ...] = tuple(sorted(parsed_tags, key=str))
    python_tags = tuple(sorted({tag.interpreter for tag in tags}))
    abi_tags = tuple(sorted({tag.abi for tag in tags}))
    platform_tags = tuple(sorted({tag.platform for tag in tags}))

    # ``packaging`` canonicalises the local segment to lowercase, which is
    # useful here: upstream uses both TRUE/FALSE and lowercase variants.
    local = parsed_version.local or ""
    cuda_match = _CUDA_RE.search("+" + local)
    torch_match = _TORCH_RE.search("+" + local)
    cxx11_match = _CXX11_RE.search(local)
    cuda_line = _cuda_token(cuda_match.group("cuda")) if cuda_match else None
    torch_version = torch_match.group("torch") if torch_match else None
    cxx11abi = None
    if cxx11_match:
        cxx11abi = cxx11_match.group("abi").lower() in {"true", "1"}

    build_tag: str | None = (
        parsed_version.local if not raw_build else "".join(str(part) for part in raw_build)
    )
    return NormalizedWheel(
        filename=filename,
        distribution=normalized_distribution,
        version=str(parsed_version),
        public_version=parsed_version.public,
        build_tag=build_tag,
        tags=tuple(str(tag) for tag in tags),
        python_tags=python_tags,
        abi_tags=abi_tags,
        platform_tags=platform_tags,
        cuda_line=cuda_line,
        torch_version=torch_version,
        cxx11abi=cxx11abi,
    )


def try_normalise_wheel_filename(filename_or_url: str) -> NormalizedWheel | None:
    try:
        return normalise_wheel_filename(filename_or_url)
    except WheelFilenameError:
        return None


def normalise_many(filenames: Iterable[str]) -> tuple[NormalizedWheel, ...]:
    """Parse wheel assets, skipping non-wheel release files deterministically."""

    result: list[NormalizedWheel] = []
    for filename in filenames:
        if _asset_basename(filename).lower().endswith(".whl"):
            result.append(normalise_wheel_filename(filename))
    return tuple(result)


# American spelling and an older draft name are kept as tiny API aliases.
normalize_wheel_filename = normalise_wheel_filename
parse_wheel_asset = normalise_wheel_filename


__all__ = [
    "NormalizedWheel",
    "WheelFilenameError",
    "normalise_many",
    "normalise_wheel_filename",
    "normalize_wheel_filename",
    "parse_wheel_asset",
    "try_normalise_wheel_filename",
]
