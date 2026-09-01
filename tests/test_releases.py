from scigantic_comptox.releases import ReleaseCapabilityError, UnknownReleaseError, latest, releases


def test_latest_is_a_known_release():
    assert latest() in {r.release for r in releases()}


def test_v4_3_release_capabilities():
    infos = {r.release: r for r in releases()}
    assert "v4_3" in infos
    v4_3 = infos["v4_3"]
    assert v4_3.bioactivity is True
    assert v4_3.pubchem_bridge is True
    assert v4_3.structures is True
    # PubChem-sourced, not EPA's own DSSTox bulk distribution -- see
    # structures.py's module docstring for why. Real, measured coverage
    # (94.3%), not a guess.
    assert v4_3.structures_source == "pubchem"
    assert v4_3.structures_coverage is not None
    assert 0.9 < v4_3.structures_coverage < 1.0


def test_unknown_release_raises():
    from scigantic_comptox.bioactivity import bioactivity

    try:
        bioactivity(release="not-a-real-release")
    except UnknownReleaseError:
        pass
    else:
        raise AssertionError("expected UnknownReleaseError")


def test_missing_capability_raises_capability_error(monkeypatch):
    # scigantic_comptox/__init__.py does `from .releases import releases`,
    # which shadows the `releases` attribute on the scigantic_comptox
    # package with that function -- sys.modules is the reliable way to
    # reach the actual submodule for internal state, matching how the
    # sibling scigantic-bindingdb package's own tests do this.
    import sys

    releases_mod = sys.modules["scigantic_comptox.releases"]

    real_cache = releases_mod._cache
    releases_mod._cache = {
        "latest": "fake",
        "releases": {"fake": {"structures": False, "bioactivity": False, "pubchem_bridge": False}},
    }
    try:
        from scigantic_comptox.bioactivity import bioactivity

        try:
            bioactivity(release="fake")
        except ReleaseCapabilityError:
            pass
        else:
            raise AssertionError("expected ReleaseCapabilityError")
    finally:
        releases_mod._cache = real_cache
