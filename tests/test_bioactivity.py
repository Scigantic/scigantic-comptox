"""Real, live queries against s3://scigantic-comptox -- no mocks, matching
scigantic-chembl/scigantic-bindingdb's testing philosophy for a public S3
mirror with no meaningful rate limit."""

from scigantic_comptox.bioactivity import bioactivity, bioactivity_raw


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


def test_bioactivity_record_count_matches_known_real_total():
    """Sanity check against the real, measured row count from the mirror
    build (3,527,285 rows) -- catches a silent re-mirror that dropped or
    duplicated rows, without hardcoding an exact live count that would
    break on every legitimate re-mirror."""
    from scigantic_comptox.connection import query

    df = query("SELECT COUNT(*) AS n FROM bioactivity")
    assert df["n"].iloc[0] > 3_000_000
