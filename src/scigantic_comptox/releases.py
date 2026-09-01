"""Release metadata: what's mirrored, and what each release supports.

Reads a small manifest at s3://scigantic-comptox/_MANIFEST.json, the same
mechanism scigantic-chembl and scigantic-bindingdb use. The v4_3 release
carries `bioactivity`, `pubchem_bridge`, and four small reference tables
(`assay_annotations`, `assay_target_mappings`, `cytotox`, `analytical_qc`)
mirrored alongside EPA's fact table rather than just the fact table alone
-- see reference.py's module docstring for why.

`structures` is True as of this release, but NOT sourced from EPA's own
DSSTox bulk distribution -- that turned out to be a messy institutional
drive with no clean single file to mirror, and EPA's live Chemical API has
an unresolved data-use question for bulk redistribution that wasn't worth
blocking on. Instead, every chemical this mirror already covers was
resolved against PubChem's own open, keyless compound search by DTXSID.
`structures_source` and `structures_coverage` record this plainly rather
than silently implying full DSSTox coverage: 94.3% of chemicals resolved
(9,238 of 9,801), the rest genuinely have no PubChem match under that
name.

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
        "structures": True,
        "structures_source": "pubchem",
        "structures_coverage": 0.943,
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
    # None for a release published before structures existed, or for a
    # manifest fetched from a package version older than this one's
    # ReleaseInfo shape -- both real cases, not defensive padding.
    structures_source: str | None = None
    structures_coverage: float | None = None


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
