import threading

import scigantic_comptox as comptox


def test_cache_disabled_by_default_returns_s3_url():
    comptox.disable_cache()
    assert comptox.cache_resolve("v4_3/derived/pubchem_bridge.parquet").startswith("s3://")


def test_enable_cache_downloads_and_reuses(tmp_path):
    comptox.enable_cache(str(tmp_path))
    try:
        path = comptox.cache_resolve("v4_3/derived/pubchem_bridge.parquet")
        assert path.startswith(str(tmp_path))
        import os

        assert os.path.exists(path)
        # Second call reuses the cached file, no re-download.
        path2 = comptox.cache_resolve("v4_3/derived/pubchem_bridge.parquet")
        assert path2 == path
    finally:
        comptox.disable_cache()


def test_concurrent_resolve_of_same_key_triggers_one_download(tmp_path):
    """16 threads racing the first resolve() of a key must not each start
    their own download -- the exact bug scigantic-chembl's original cache.py
    had, fixed via a per-key lock ported from scigantic-bindingdb."""
    comptox.enable_cache(str(tmp_path))
    try:
        from scigantic_comptox import cache as cache_mod

        original_download = cache_mod._atomic_download
        call_count = {"n": 0}
        lock = threading.Lock()

        def counting_download(url, local_path):
            with lock:
                call_count["n"] += 1
            original_download(url, local_path)

        cache_mod._atomic_download = counting_download
        try:
            key = "v4_3/derived/pubchem_bridge.parquet"
            threads = [
                threading.Thread(target=comptox.cache_resolve, args=(key,))
                for _ in range(16)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            assert call_count["n"] == 1
        finally:
            cache_mod._atomic_download = original_download
    finally:
        comptox.disable_cache()
