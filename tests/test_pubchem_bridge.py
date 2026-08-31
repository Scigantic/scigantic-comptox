from scigantic_comptox.pubchem_bridge import pubchem_bridge


def test_pubchem_bridge_returns_rows():
    df = pubchem_bridge(limit=10)
    assert len(df) == 10
    assert set(df.columns) == {
        "aeid",
        "tx_sample_id",
        "dtxsid",
        "activity_outcome",
        "ac50_um",
        "hitc",
        "bmd_um",
    }


def test_pubchem_bridge_filter_by_aeid():
    df = pubchem_bridge(aeid=1114, limit=5)
    assert len(df) == 5
    assert (df["aeid"] == 1114).all()
