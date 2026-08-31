"""Live wrapper over EPA's CCTE API (Chemical/Hazard/Exposure microservices),
the optional half of this package -- the mirror half (bioactivity.py,
pubchem_bridge.py) needs no API key at all.

Requires the caller's OWN EPA API key, deliberately. EPA's own docs describe
it as "an individual API key" that "uniquely identifies the user", and
issuance is manually gated through ccte_api@epa.gov rather than self-serve
-- a real signal against a shared/pooled key. EPA's own reference client
(github.com/USEPA/ctx-python, read directly to confirm real endpoint paths
and conventions used here) never embeds a key and always requires the
caller to supply their own; this package does the same. Get a key by
emailing ccte_api@epa.gov (see CTX_API_INFO_URL).

Endpoint coverage here is intentionally a starting set (one representative,
real, verified-path endpoint per microservice: chemical detail, a ToxValDB
hazard search, and HTTK exposure data), not a full reimplementation of
ctx-python -- ctx-python already covers Chemical/Exposure/Hazard
comprehensively; this package's real differentiator is the bioactivity
mirror, not REST-endpoint parity with EPA's own client. Point users at
ctx-python directly if they need broader REST coverage than what's here.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

import requests

from . import ctx_cache
from ._constants import CTX_API_BASE, CTX_API_INFO_URL, CTX_API_KEY_CONTACT, CTX_API_KEY_ENV

_USER_AGENT = "scigantic-comptox (+https://scigantic.com; mailto:support@scigantic.com)"
_MAX_RETRIES = 5
_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
_BACKOFF_BASE_SECONDS = 1.0


class CtxApiError(Exception):
    """Raised for a CCTE API error response after retries are exhausted."""


class MissingApiKeyError(CtxApiError):
    """Raised when no EPA CCTE API key is configured.

    This package never embeds or shares a key -- see module docstring.
    """

    def __init__(self) -> None:
        super().__init__(
            f"No EPA CCTE API key found. Set the {CTX_API_KEY_ENV} environment "
            f"variable, or pass api_key= directly. Get a free key by emailing "
            f"{CTX_API_KEY_CONTACT} -- see {CTX_API_INFO_URL}."
        )


_session: requests.Session | None = None
_session_lock = threading.Lock()


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        with _session_lock:
            if _session is None:  # re-check: another thread may have won the race
                _session = requests.Session()
                _session.headers["User-Agent"] = _USER_AGENT
                _session.headers["Accept"] = "application/json"
    return _session


def _resolve_api_key(api_key: str | None) -> str:
    key = api_key or os.environ.get(CTX_API_KEY_ENV)
    if not key:
        raise MissingApiKeyError()
    return key


def ctx_get(
    endpoint: str,
    api_key: str | None = None,
    params: dict[str, Any] | None = None,
    use_cache: bool = True,
) -> Any:
    """A GET against `{CTX_API_BASE}/{endpoint}`, JSON-decoded.

    Retries 429/5xx with exponential backoff. Results are cached (see
    ctx_cache.py, ON by default) keyed on the exact endpoint + params, so
    a repeated identical lookup makes no network call while the cache
    entry is still fresh.
    """
    resolve_key = _resolve_api_key(api_key)
    cache_key = f"GET {endpoint} {params!r}"
    if use_cache:
        cached = ctx_cache.get(cache_key)
        if cached is not None:
            return cached

    session = _get_session()
    url = f"{CTX_API_BASE}/{endpoint.lstrip('/')}"
    last_exc: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            response = session.get(
                url, headers={"x-api-key": resolve_key}, params=params, timeout=30
            )
        except requests.RequestException as exc:
            last_exc = exc
            time.sleep(_BACKOFF_BASE_SECONDS * (2**attempt))
            continue

        if response.status_code == 200:
            data = response.json()
            if use_cache:
                ctx_cache.put(cache_key, data)
            return data
        if response.status_code in _RETRY_STATUS_CODES and attempt < _MAX_RETRIES - 1:
            time.sleep(_BACKOFF_BASE_SECONDS * (2**attempt))
            continue
        raise CtxApiError(
            f"CCTE API request failed: {response.status_code} {response.reason} "
            f"for {url}"
        )

    raise CtxApiError(f"CCTE API request failed after {_MAX_RETRIES} attempts: {last_exc!r}")


def chemical_detail(
    dtxsid: str, api_key: str | None = None, projection: str = "chemicaldetailall"
) -> Any:
    """Chemical details for a single DTXSID (structure, identifiers,
    physicochemical properties). Real endpoint path confirmed against EPA's
    own ctx-python client source: `chemical/detail/search/by-dtxsid/{dtxsid}`.
    """
    return ctx_get(
        f"chemical/detail/search/by-dtxsid/{dtxsid}",
        api_key=api_key,
        params={"projection": projection},
    )


def hazard_toxval(dtxsid: str, api_key: str | None = None) -> Any:
    """ToxValDB hazard records for a single DTXSID. Real endpoint path
    confirmed against ctx-python: `hazard/toxval/search/by-dtxsid/{dtxsid}`.
    """
    return ctx_get(f"hazard/toxval/search/by-dtxsid/{dtxsid}", api_key=api_key)


def exposure_httk(dtxsid: str, api_key: str | None = None) -> Any:
    """High-Throughput Toxicokinetics (HTTK) exposure data for a single
    DTXSID. Real endpoint path confirmed against ctx-python:
    `exposure/httk/search/by-dtxsid/{dtxsid}`.
    """
    return ctx_get(f"exposure/httk/search/by-dtxsid/{dtxsid}", api_key=api_key)
