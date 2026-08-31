"""Optional local caching for the mirror half: download once, then work
with no network.

Off by default, matching scigantic-chembl/scigantic-bindingdb's convention
for a public S3 mirror with no meaningful rate limit -- caching is a pure
convenience here, opt-in rather than a default that changes behavior:

    import scigantic_comptox as comptox
    comptox.enable_cache()

This is the mirror half's cache only. The live REST half (ctx_client.py)
has its own separate cache, default ON with a TTL, since that side calls a
real government API per lookup rather than reading an unlimited public
mirror -- see ctx_cache.py for why that default is the opposite of this
one.

connect() / query() / bioactivity() / pubchem_bridge() do not use this:
connect() registers views on every call to the shared base connection, so
caching would mean eagerly downloading a 600+ MB file regardless of what a
query actually touches. Use cache_resolve("<release>/<path>.parquet") to
pull a specific file locally and read it directly with read_parquet(...).
"""

from __future__ import annotations

import os
import sys
import threading
import urllib.request
import uuid
from pathlib import Path

from ._constants import BUCKET, REGION

_enabled = False
_cache_dir: Path | None = None

_CHUNK_BYTES = 1024 * 1024

# One lock per key, guarding resolve()'s check-then-download against
# concurrent callers asking for the same key at once. Ported from
# scigantic-bindingdb's cache.py, which measured this as a real bug: 16
# threads racing an empty cache each triggered a full separate download
# before this fix.
_resolve_locks: dict[str, threading.Lock] = {}
_resolve_locks_guard = threading.Lock()


def _lock_for(key: str) -> threading.Lock:
    lock = _resolve_locks.get(key)
    if lock is not None:
        return lock
    with _resolve_locks_guard:
        return _resolve_locks.setdefault(key, threading.Lock())


def _default_cache_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Caches")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "scigantic-comptox"


def enable_cache(cache_dir: str | None = None) -> Path:
    """Turn on local caching for the mirror half.

    Cache location: `cache_dir` if given, else the SCIGANTIC_COMPTOX_CACHE
    environment variable, else a platform-appropriate user cache directory.
    Returns the resolved directory.
    """
    global _enabled, _cache_dir
    if cache_dir is not None:
        resolved = Path(cache_dir)
    elif os.environ.get("SCIGANTIC_COMPTOX_CACHE"):
        resolved = Path(os.environ["SCIGANTIC_COMPTOX_CACHE"])
    else:
        resolved = _default_cache_dir()
    resolved.mkdir(parents=True, exist_ok=True)
    _cache_dir = resolved
    _enabled = True
    return resolved


def disable_cache() -> None:
    """Turn caching back off. Later calls go straight to S3 again.

    Anything already downloaded stays on disk; this only stops using it.
    """
    global _enabled
    _enabled = False


def is_cache_enabled() -> bool:
    return _enabled


def cache_dir() -> Path | None:
    """The resolved cache directory, or None if caching has never been enabled."""
    return _cache_dir


def _atomic_download(url: str, local_path: Path) -> None:
    """Stream `url` to a sibling temp file, then rename it into place.

    The temp filename is unique per call (UUID-suffixed), not shared per
    `local_path`: two threads racing to fill the same key must not share a
    temp path, or the second os.replace() raises FileNotFoundError once the
    first has already consumed it -- the exact bug scigantic-chembl's
    original cache.py had and scigantic-bindingdb fixed; this package
    starts from the fixed version.
    """
    tmp_path = local_path.with_name(local_path.name + f".{uuid.uuid4().hex}.part")
    with urllib.request.urlopen(url) as response, open(tmp_path, "wb") as fh:
        while chunk := response.read(_CHUNK_BYTES):
            fh.write(chunk)
    os.replace(tmp_path, local_path)


def resolve(key: str) -> str:
    """An S3 URL, or a local cached file path if caching is on.

    `key` is a path relative to the bucket root, e.g.
    "v4_3/derived/pubchem_bridge.parquet". Downloads to the cache on first
    access; later calls for the same key reuse the local file. Concurrent
    callers asking for the same key while it's still downloading wait for
    that download rather than each starting their own.
    """
    if not _enabled:
        return f"s3://{BUCKET}/{key}"

    assert _cache_dir is not None
    local_path = _cache_dir / key
    if local_path.exists():
        return str(local_path)

    with _lock_for(key):
        if local_path.exists():  # another thread finished it while we waited
            return str(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://{BUCKET}.s3.{REGION}.amazonaws.com/{key}"
        print(f"scigantic-comptox: caching {key} ...", file=sys.stderr, flush=True)
        _atomic_download(url, local_path)
    return str(local_path)
