"""Real, live queries against s3://scigantic-comptox's small reference
tables -- no mocks, matching the rest of this package's testing philosophy."""

from scigantic_comptox.reference import (
    analytical_qc,
    assay_annotations,
    assay_target_mappings,
    cytotox,
)


def test_assay_annotations_returns_rows():
    df = assay_annotations(limit=5)
    assert len(df) == 5
    assert "aeid" in df.columns
    assert "intended_target_family" in df.columns


def test_assay_annotations_filter_by_aeid():
    df = assay_annotations(aeid=1114)
    assert len(df) == 1
    assert (df["aeid"] == 1114).all()


def test_assay_annotations_filter_by_target_family():
    # Discover a real category value first rather than assuming one --
    # every real target family this table carries has at least one row.
    families = assay_annotations(limit=2000)["intended_target_family"].dropna().unique()
    assert len(families) > 0
    family = families[0]
    df = assay_annotations(intended_target_family=family)
    assert len(df) > 0
    assert (df["intended_target_family"] == family).all()


def test_assay_target_mappings_returns_rows():
    df = assay_target_mappings(limit=5)
    assert len(df) == 5
    assert "aeid" in df.columns
    assert "target_type" in df.columns


def test_assay_target_mappings_filter_by_official_symbol():
    # Find a real gene symbol present in the live mirror first.
    symbols = assay_target_mappings(limit=2000)["official_symbol"].dropna().unique()
    assert len(symbols) > 0
    symbol = symbols[0]
    df = assay_target_mappings(official_symbol=symbol)
    assert len(df) > 0
    assert (df["official_symbol"] == symbol).all()


def test_cytotox_returns_rows():
    df = cytotox(limit=5)
    assert len(df) == 5
    assert "dsstox_substance_id" in df.columns
    assert "cytotox_median_um" in df.columns


def test_cytotox_filter_by_dtxsid():
    df = cytotox(dtxsid="DTXSID7020005")
    assert len(df) > 0
    assert (df["dsstox_substance_id"] == "DTXSID7020005").all()


def test_analytical_qc_returns_rows():
    df = analytical_qc(limit=5)
    assert len(df) == 5
    assert "dsstox_substance_id" in df.columns
    assert "pass_or_caution" in df.columns


def test_analytical_qc_filter_by_dtxsid():
    df = analytical_qc(dtxsid="DTXSID0020020")
    assert len(df) > 0
    assert (df["dsstox_substance_id"] == "DTXSID0020020").all()
