"""Local response cache for the live REST half, ON by default -- the
opposite default from cache.py (the mirror half), and deliberately so: this
side calls EPA's rate-limited CCTE API for every lookup, while the mirror
half reads an unlimited public S3 mirror. Re-fetching the same DTXSID
repeatedly in a notebook loop is both slow and the kind of load a live
government API shouldn't take unnecessarily. Matches scigantic-pubchem's
identical reasoning for its own default-on cache.

Entries expire after ttl_days (30 by default, same as scigantic-pubchem).
Pass ttl_days=None to disable expiry.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

_enabled = True
_cache_dir: Path | None = None
_ttl_seconds: float | None = 30 * 86400


def _default_cache_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Caches")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "scigantic-comptox" / "ctx-api"


def _resolve_dir() -> Path:
    global _cache_dir
    if _cache_dir is None:
        env = os.environ.get("SCIGANTIC_COMPTOX_CTX_CACHE")
        _cache_dir = Path(env) if env else _default_cache_dir()
        _cache_dir.mkdir(parents=True, exist_ok=True)
    return _cache_dir


def enable_ctx_cache(cache_dir: str | None = None, ttl_days: float | None = 30) -> Path:
    """Turn caching on for the live REST half (it already is, by default)."""
    global _enabled, _cache_dir, _ttl_seconds
    if cache_dir is not None:
        _cache_dir = Path(cache_dir)
        _cache_dir.mkdir(parents=True, exist_ok=True)
    else:
        _resolve_dir()
    _ttl_seconds = ttl_days * 86400 if ttl_days is not None else None
    _enabled = True
    return _cache_dir  # type: ignore[return-value]


def disable_ctx_cache() -> None:
    global _enabled
    _enabled = False


def is_ctx_cache_enabled() -> bool:
    return _enabled


def _key_path(key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return _resolve_dir() / f"{digest}.json"


def get(key: str) -> Any | None:
    """A cached JSON value for `key`, or None on a miss or expired entry."""
    if not _enabled:
        return None
    path = _key_path(key)
    if not path.exists():
        return None
    if _ttl_seconds is not None and (time.time() - path.stat().st_mtime) > _ttl_seconds:
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def put(key: str, value: Any) -> None:
    """Cache `value` (must be JSON-serializable) under `key`."""
    if not _enabled:
        return
    path = _key_path(key)
    tmp_path = path.with_name(path.name + f".{uuid.uuid4().hex}.part")
    tmp_path.write_text(json.dumps(value))
    os.replace(tmp_path, path)
