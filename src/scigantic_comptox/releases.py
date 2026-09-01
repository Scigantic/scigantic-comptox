"""Release metadata: what's mirrored, and what each release supports.

Reads a small manifest at s3://scigantic-comptox/_MANIFEST.json, the same
mechanism scigantic-chembl and scigantic-bindingdb use. The v4_3 release
carries `bioactivity`, `pubchem_bridge`, and four small reference tables
(`assay_annotations`, `assay_target_mappings`, `cytotox`, `analytical_qc`)
mirrored alongside EPA's fact table rather than just the fact table alone
-- see reference.py's module docstring for why. `structures` is False
because DSSTox bulk chemical structures aren't mirrored yet (EPA's bulk
distribution for that turned out to be a messy institutional drive, not a
clean single file) -- a future release can add a structures.parquet
without breaking anything that calls releases() to check what's available
first.

The manifest is fetched once per process and cached. If it can't be fetched,
calls fall back to the snapshot below rather than failing outright.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import warnings
from dataclasses import dataclass
from typing import Any, cast

from ._constants import BUCKET, REGION

_MANIFEST_URL = f"https://{BUCKET}.s3.{REGION}.amazonaws.com/_MANIFEST.json"
_TIMEOUT_SECONDS = 5

# Last-known-good snapshot, shipped with this package version.
_FALLBACK_LATEST = "v4_3"
_FALLBACK_RELEASES = {
    "v4_3": {
        "structures": False,
        "bioactivity": True,
        "pubchem_bridge": True,
        "assay_annotations": True,
        "assay_target_mappings": True,
        "cytotox": True,
        "analytical_qc": True,
    },
}


class UnknownReleaseError(LookupError):
    """Raised when a release isn't mirrored at all."""


class ReleaseCapabilityError(LookupError):
    """Raised when a release doesn't carry the artifact a call asked for."""


@dataclass(frozen=True)
class ReleaseInfo:
    release: str
    structures: bool
    bioactivity: bool
    pubchem_bridge: bool
    assay_annotations: bool
    assay_target_mappings: bool
    cytotox: bool
    analytical_qc: bool


_cache: dict[str, Any] | None = None


def _manifest() -> dict[str, Any]:
    global _cache
    if _cache is not None:
        return _cache
    try:
        with urllib.request.urlopen(_MANIFEST_URL, timeout=_TIMEOUT_SECONDS) as response:
            _cache = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        if isinstance(exc, urllib.error.HTTPError):
            exc.close()
        warnings.warn(
            f"could not fetch the live release manifest ({exc!r}); falling back "
            "to the snapshot shipped with this package version, which may be stale",
            stacklevel=3,
        )
        _cache = {"latest": _FALLBACK_LATEST, "releases": _FALLBACK_RELEASES}
    return _cache


def releases() -> list[ReleaseInfo]:
    """List every release the mirror carries, and what each one supports."""
    data = _manifest()
    return [ReleaseInfo(release=name, **caps) for name, caps in data["releases"].items()]


def latest() -> str:
    """The release the archive treats as its current default."""
    return cast(str, _manifest()["latest"])


def _validate_release(release: str) -> None:
    data = _manifest()
    if release not in data["releases"]:
        known = ", ".join(data["releases"])
        raise UnknownReleaseError(f"{release!r} is not mirrored. Known releases: {known}.")


def _require(release: str, capability: str) -> None:
    _validate_release(release)
    data = _manifest()
    if not data["releases"][release][capability]:
        raise ReleaseCapabilityError(
            f"{release!r} has no {capability.replace('_', ' ')}. Call releases() to "
            "see what each release supports."
        )
