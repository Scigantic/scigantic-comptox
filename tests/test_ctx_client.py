"""Mocked tests for the live REST half -- no real EPA API key is available
in CI, so these exercise the retry/backoff/caching/error-handling logic
against a fake requests.Session rather than the real CCTE API."""

import pytest

from scigantic_comptox import ctx_cache, ctx_client
from scigantic_comptox.ctx_client import CtxApiError, MissingApiKeyError


class _FakeResponse:
    def __init__(self, status_code, json_data=None, reason="error"):
        self.status_code = status_code
        self._json_data = json_data
        self.reason = reason

    def json(self):
        return self._json_data


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(ctx_client, "_session", None)
    ctx_cache.enable_ctx_cache(str(tmp_path))
    yield
    ctx_cache.disable_ctx_cache()


def test_missing_api_key_raises_actionable_error(monkeypatch):
    monkeypatch.delenv("COMPTOX_API_KEY", raising=False)
    with pytest.raises(MissingApiKeyError) as exc_info:
        ctx_client.ctx_get("chemical/detail/search/by-dtxsid/DTXSID7020182")
    assert "ccte_api@epa.gov" in str(exc_info.value)


def test_successful_get_is_cached(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, headers=None, params=None, timeout=None):
        calls["n"] += 1
        return _FakeResponse(200, json_data={"ok": True})

    session = ctx_client._get_session()
    monkeypatch.setattr(session, "get", fake_get)

    result1 = ctx_client.ctx_get("chemical/detail/search/by-dtxsid/DTXSID7020182", api_key="fake-key")
    result2 = ctx_client.ctx_get("chemical/detail/search/by-dtxsid/DTXSID7020182", api_key="fake-key")

    assert result1 == {"ok": True}
    assert result2 == {"ok": True}
    assert calls["n"] == 1  # second call served from cache, no real request


def test_retries_on_429_then_succeeds(monkeypatch):
    responses = [_FakeResponse(429, reason="Too Many Requests"), _FakeResponse(200, json_data={"ok": True})]

    def fake_get(url, headers=None, params=None, timeout=None):
        return responses.pop(0)

    session = ctx_client._get_session()
    monkeypatch.setattr(session, "get", fake_get)
    monkeypatch.setattr(ctx_client.time, "sleep", lambda _seconds: None)

    result = ctx_client.ctx_get("hazard/toxval/search/by-dtxsid/DTXSID7020182", api_key="fake-key")
    assert result == {"ok": True}


def test_raises_ctx_api_error_on_persistent_failure(monkeypatch):
    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeResponse(500, reason="Server Error")

    session = ctx_client._get_session()
    monkeypatch.setattr(session, "get", fake_get)
    monkeypatch.setattr(ctx_client.time, "sleep", lambda _seconds: None)

    with pytest.raises(CtxApiError):
        ctx_client.ctx_get("exposure/httk/search/by-dtxsid/DTXSID7020182", api_key="fake-key")


def test_chemical_detail_builds_expected_path(monkeypatch):
    captured = {}

    def fake_get(url, headers=None, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse(200, json_data={})

    session = ctx_client._get_session()
    monkeypatch.setattr(session, "get", fake_get)

    ctx_client.chemical_detail("DTXSID7020182", api_key="fake-key")
    assert captured["url"].endswith("chemical/detail/search/by-dtxsid/DTXSID7020182")
    assert captured["params"] == {"projection": "chemicaldetailall"}
