"""Query EPA's CompTox Chemicals Dashboard: ToxCast bioactivity from a
public S3 mirror (no API key), plus live Chemical/Hazard/Exposure lookups
via EPA's CCTE API (bring your own key)."""

from importlib.metadata import PackageNotFoundError, version as _version

from .bioactivity import bioactivity, bioactivity_many, bioactivity_raw
from .cache import cache_dir, disable_cache, enable_cache, is_cache_enabled
from .cache import resolve as cache_resolve
from .connection import connect, query
from .ctx_cache import disable_ctx_cache, enable_ctx_cache, is_ctx_cache_enabled
from .ctx_client import (
    CtxApiError,
    MissingApiKeyError,
    chemical_detail,
    ctx_get,
    exposure_httk,
    hazard_toxval,
)
from .pubchem_bridge import pubchem_bridge, pubchem_bridge_many
from .reference import analytical_qc, assay_annotations, assay_target_mappings, cytotox
from .releases import (
    ReleaseCapabilityError,
    ReleaseInfo,
    UnknownReleaseError,
    latest,
    releases,
)

try:
    __version__ = _version("scigantic-comptox")
except PackageNotFoundError:
    # Running from a source checkout with no install (editable or not).
    __version__ = "0.0.0"

__all__ = [
    # mirror half
    "connect",
    "query",
    "bioactivity",
    "bioactivity_many",
    "bioactivity_raw",
    "pubchem_bridge",
    "pubchem_bridge_many",
    "assay_annotations",
    "assay_target_mappings",
    "cytotox",
    "analytical_qc",
    "releases",
    "latest",
    "enable_cache",
    "disable_cache",
    "is_cache_enabled",
    "cache_dir",
    "cache_resolve",
    "ReleaseInfo",
    "ReleaseCapabilityError",
    "UnknownReleaseError",
    # live REST half
    "ctx_get",
    "chemical_detail",
    "hazard_toxval",
    "exposure_httk",
    "CtxApiError",
    "MissingApiKeyError",
    "enable_ctx_cache",
    "disable_ctx_cache",
    "is_ctx_cache_enabled",
]
