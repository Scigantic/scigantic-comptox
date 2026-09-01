from scigantic_comptox.connection import query
from scigantic_comptox.structures import structures, structures_many


def test_structures_returns_rows():
    df = structures(limit=10)
    assert len(df) == 10
    assert set(df.columns) == {
        "dtxsid",
        "cid",
        "title",
        "smiles",
        "inchi",
        "inchi_key",
        "iupac_name",
        "molecular_formula",
        "molecular_weight",
    }


def test_structures_filter_by_dtxsid():
    row = query("SELECT dtxsid FROM structures LIMIT 1")["dtxsid"].iloc[0]
    df = structures(dtxsid=row)
    assert len(df) == 1
    assert df["dtxsid"].iloc[0] == row


def test_structures_real_coverage_matches_known_measurement():
    """Sanity check against the real, measured row count from the build
    (9,238 chemicals resolved out of 9,801, 94.3%) -- catches a silent
    re-mirror that dropped or duplicated rows, without hardcoding an exact
    count that would break on every legitimate re-mirror."""
    n = query("SELECT COUNT(*) AS n FROM structures")["n"].iloc[0]
    assert n > 9000


def test_structures_smiles_are_real_non_empty_strings():
    df = structures(limit=50)
    assert (df["smiles"].str.len() > 0).all()


def test_structures_many_matches_looped_individual_calls():
    ids = query("SELECT dtxsid FROM structures LIMIT 5")["dtxsid"].tolist()

    looped_rows = sum(len(structures(dtxsid=d)) for d in ids)

    batched = structures_many(ids)
    assert len(batched) == looped_rows
    assert set(batched["dtxsid"].unique()) == set(ids)


def test_structures_many_empty_list_returns_empty_dataframe():
    df = structures_many([])
    assert len(df) == 0
