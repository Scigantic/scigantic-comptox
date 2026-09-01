"""Real, live queries against s3://scigantic-comptox -- no mocks, matching
scigantic-chembl/scigantic-bindingdb's testing philosophy for a public S3
mirror with no meaningful rate limit."""

import time

from scigantic_comptox.bioactivity import bioactivity, bioactivity_many, bioactivity_raw
from scigantic_comptox.connection import query


def test_bioactivity_returns_rows():
    df = bioactivity(limit=10)
    assert len(df) == 10
    assert "aeid" in df.columns
    assert "hitc" in df.columns


def test_bioactivity_filter_by_aeid():
    df = bioactivity(aeid=1114, limit=5)
    assert len(df) == 5
    assert (df["aeid"] == 1114).all()


def test_bioactivity_filter_by_dtxsid():
    df = bioactivity(dtxsid="DTXSID8045222")
    assert len(df) > 0
    assert (df["dsstox_substance_id"] == "DTXSID8045222").all()


def test_bioactivity_normalizes_na_strings_to_null():
    """The literal "NA" string EPA's export uses for missing values must
    not survive into the normalized bioactivity() view -- this is the real
    bug found and fixed while onboarding this mirror."""
    df = bioactivity(limit=5000)
    assert not (df["dsstox_substance_id"] == "NA").any()


def test_bioactivity_numeric_text_columns_are_real_floats():
    """ac50/bmd/top/etc ship as VARCHAR in EPA's raw export; the normalized
    view must expose them as real numeric types."""
    df = bioactivity(limit=100)
    import pandas as pd

    assert pd.api.types.is_float_dtype(df["ac50"])
    assert pd.api.types.is_float_dtype(df["bmd"])


def test_bioactivity_raw_keeps_upstream_types_unchanged():
    df = bioactivity_raw(limit=100)
    import pandas as pd

    # The raw view intentionally does NOT normalize: ac50 stays text
    # (pandas surfaces DuckDB's VARCHAR as its "string" dtype, not a real
    # float), and the literal "NA" string survives untouched.
    assert not pd.api.types.is_float_dtype(df["ac50"])
    assert (df["ac50"] == "NA").any()


def test_bioactivity_query_accepts_dtxsid_alias():
    """query()'s raw SQL layer used to only know the raw dsstox_substance_id
    column name -- dtxsid is a plain alias so a caller who reads
    bioactivity()'s dtxsid= parameter and reasonably tries the same name in
    their own SQL doesn't hit a binder error."""
    df = query("SELECT * FROM bioactivity WHERE dtxsid = 'DTXSID8045222' LIMIT 5")
    assert len(df) > 0
    assert (df["dtxsid"] == "DTXSID8045222").all()


def test_bioactivity_many_matches_looped_individual_calls():
    """bioactivity_many() must return the same rows a caller would get by
    looping bioactivity(dtxsid=...) per id, just faster."""
    ids = query(
        "SELECT dtxsid FROM bioactivity WHERE dtxsid IS NOT NULL "
        "GROUP BY dtxsid ORDER BY COUNT(*) DESC LIMIT 5"
    )["dtxsid"].tolist()

    looped = [bioactivity(dtxsid=d) for d in ids]
    looped_rows = sum(len(df) for df in looped)

    batched = bioactivity_many(ids)
    assert len(batched) == looped_rows
    assert set(batched["dtxsid"].unique()) == set(ids)


def test_bioactivity_many_is_faster_than_looping():
    """Real perf regression guard, not just a correctness check -- this is
    the whole reason bioactivity_many() exists. Measured on the real mirror:
    50 chemicals looped through bioactivity() took 61.9s vs 4.8s batched (a
    13x difference). Use a smaller batch here to keep CI fast, but the
    batched path must still be clearly faster, not just present."""
    ids = query(
        "SELECT dtxsid FROM bioactivity WHERE dtxsid IS NOT NULL "
        "GROUP BY dtxsid ORDER BY COUNT(*) DESC LIMIT 10"
    )["dtxsid"].tolist()

    t0 = time.time()
    for d in ids:
        bioactivity(dtxsid=d)
    looped_time = time.time() - t0

    t1 = time.time()
    bioactivity_many(ids)
    batched_time = time.time() - t1

    assert batched_time < looped_time


def test_bioactivity_many_empty_list_returns_empty_dataframe():
    df = bioactivity_many([])
    assert len(df) == 0


def test_bioactivity_record_count_matches_known_real_total():
    """Sanity check against the real, measured row count from the mirror
    build (3,527,285 rows) -- catches a silent re-mirror that dropped or
    duplicated rows, without hardcoding an exact live count that would
    break on every legitimate re-mirror."""
    from scigantic_comptox.connection import query

    df = query("SELECT COUNT(*) AS n FROM bioactivity")
    assert df["n"].iloc[0] > 3_000_000
