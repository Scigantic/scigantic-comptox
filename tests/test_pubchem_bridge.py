from scigantic_comptox.connection import query
from scigantic_comptox.pubchem_bridge import pubchem_bridge, pubchem_bridge_many


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


def test_pubchem_bridge_many_matches_looped_individual_calls():
    ids = query(
        "SELECT dtxsid FROM pubchem_bridge WHERE dtxsid IS NOT NULL "
        "GROUP BY dtxsid ORDER BY COUNT(*) DESC LIMIT 5"
    )["dtxsid"].tolist()

    looped_rows = sum(len(pubchem_bridge(dtxsid=d)) for d in ids)

    batched = pubchem_bridge_many(ids)
    assert len(batched) == looped_rows
    assert set(batched["dtxsid"].unique()) == set(ids)


def test_pubchem_bridge_many_empty_list_returns_empty_dataframe():
    df = pubchem_bridge_many([])
    assert len(df) == 0
