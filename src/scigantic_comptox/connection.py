"""DuckDB connection helpers for the mirror half. Queries run against the
public S3 mirror over httpfs, no download, no API key.

connect() hands out a cursor() on a lazily-created, shared base connection
per release rather than a brand new duckdb.connect() on every call: setup
(INSTALL/LOAD httpfs, the anonymous S3 secret, registering the two views
below) happens once per (release, process), matching scigantic-bindingdb's
connection.py, which measured this as a real cost when a caller loops a
query-returning function.

The `bioactivity` view normalizes two known data-quality issues in the
source file rather than leaving them for every caller to rediscover:

- `dsstox_substance_id` (and several other identifier columns) use the
  literal string "NA" for a small fraction of rows (~0.3%), not a real SQL
  NULL -- confirmed against the real mirrored data. `IS NOT NULL` silently
  misses these; the view applies NULLIF(..., 'NA') so a real NULL check
  works as expected.
- Several genuinely numeric columns (ac50, bmd, top, bmdl, bmdu, rmse, and
  others -- EPA's own CSV export ships these as text because "NA" rows
  forced the column to infer as a string) are TRY_CAST to DOUBLE here, with
  "NA" treated as NULL first. A value that still fails to parse becomes
  NULL rather than raising, since a handful of non-numeric outliers in a
  ~3.5M-row export are expected, not a reason to fail every query.

The view also adds a `dtxsid` column, a plain alias for the normalized
`dsstox_substance_id` (EPA's raw column name). `bioactivity()`'s `dtxsid=`
parameter always worked against `dsstox_substance_id` directly, but anyone
writing their own SQL through `query()`/`connect()` had no way to know that
without reading this module -- `pubchem_bridge`'s own source column is
already natively named `dtxsid`, so this makes the two views consistent
instead of only the Python function signatures agreeing.

`p_ac50`/`p_bmd` are computed log-potency columns, the same shape as
scigantic-chembl's `pchembl_value` / scigantic-bindingdb's `p_affinity`:
`6 - log10(value_in_uM)`, i.e. -log10(molar concentration), higher meaning
more potent. Computed ONLY where `conc_unit = 'uM'` -- verified against the
real mirror: 98.8% of rows (3,485,260 / 3,527,285) carry `uM`, but 0.09%
(3,342 rows) carry `mg/l` instead (a mass-based unit that would need each
compound's molecular weight to convert correctly, not available in this
table) and about 1% are `NA`/`CF`. Applying the uM-based transform to those
rows would silently produce a wrong potency value for a real chemical, not
just a missing one -- NULL is correct for anything not verified as `uM`.

`bioactivity_raw` (in bioactivity.py) reads the file directly with no
normalization, for anyone who wants the exact upstream types.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from ._constants import BUCKET, REGION
from .releases import _validate_release, latest

if TYPE_CHECKING:
    import duckdb
    import pandas as pd

# Text columns known to carry the literal string "NA" in place of a real
# NULL, confirmed against the live mirror.
_NA_STRING_COLUMNS = (
    "spid",
    "chid",
    "casn",
    "chnm",
    "dsstox_substance_id",
    "code",
    "aenm",
    "modl",
    "fitc",
    "mc6_flags",
)

# Columns that are genuinely numeric but shipped as VARCHAR in EPA's export
# (see module docstring). TRY_CAST after NULLIF('NA', ...) turns each into a
# real DOUBLE, NULL on anything that still doesn't parse.
_NUMERIC_TEXT_COLUMNS = (
    "top_over_cutoff",
    "rmse",
    "a",
    "p",
    "er",
    "bmdl",
    "bmdu",
    "caikwt",
    "mll",
    "ac50",
    "top",
    "ac5",
    "ac10",
    "ac20",
    "ac1sd",
    "bmd",
    "tp",
    "q",
    "ga",
    "la",
    "ac50_loss",
    "b",
    "acc",
    "loec",
)


def _bioactivity_select_list() -> str:
    parts = []
    for col in _NA_STRING_COLUMNS:
        parts.append(f"NULLIF({col}, 'NA') AS {col}")
    for col in _NUMERIC_TEXT_COLUMNS:
        parts.append(f"TRY_CAST(NULLIF({col}, 'NA') AS DOUBLE) AS {col}")
    # Everything else (aeid, m4id, bmad, hitc, hitcall, and the other
    # already-numeric columns, plus the odd "flag.length" name) passes
    # through unchanged via EXCLUDE.
    already_handled = ", ".join(_NA_STRING_COLUMNS + _NUMERIC_TEXT_COLUMNS)
    parts.append("NULLIF(dsstox_substance_id, 'NA') AS dtxsid")
    # See module docstring: only a verified `uM` conc_unit gets a potency
    # transform, everything else (mg/l, NA, CF) stays NULL rather than
    # guessing the unit.
    parts.append(
        "CASE WHEN conc_unit = 'uM' AND TRY_CAST(NULLIF(ac50, 'NA') AS DOUBLE) > 0 "
        "THEN 6 - LOG10(TRY_CAST(NULLIF(ac50, 'NA') AS DOUBLE)) ELSE NULL END AS p_ac50"
    )
    parts.append(
        "CASE WHEN conc_unit = 'uM' AND TRY_CAST(NULLIF(bmd, 'NA') AS DOUBLE) > 0 "
        "THEN 6 - LOG10(TRY_CAST(NULLIF(bmd, 'NA') AS DOUBLE)) ELSE NULL END AS p_bmd"
    )
    return f"* EXCLUDE ({already_handled}), " + ", ".join(parts)


_base_cons: dict[str, "duckdb.DuckDBPyConnection"] = {}
_base_cons_lock = threading.Lock()


def _get_base_connection(release: str) -> "duckdb.DuckDBPyConnection":
    con = _base_cons.get(release)
    if con is not None:
        return con
    with _base_cons_lock:
        con = _base_cons.get(release)
        if con is None:  # re-check: another thread may have won the race
            import duckdb

            new_con = duckdb.connect()
            new_con.execute("SET enable_progress_bar=false")
            new_con.execute("INSTALL httpfs")
            new_con.execute("LOAD httpfs")
            new_con.execute(f"SET s3_region='{REGION}'")
            # The mirror is public-read. Without this, DuckDB looks for AWS
            # credentials and fails on a machine that has none configured.
            new_con.execute(
                "CREATE OR REPLACE SECRET scigantic_comptox "
                "(TYPE s3, PROVIDER config, KEY_ID '', SECRET '')"
            )

            base = f"s3://{BUCKET}/{release}"
            bioactivity_path = f"{base}/bioactivity/mc5_6_winning_model_fits.parquet"
            new_con.execute(
                f"CREATE OR REPLACE VIEW bioactivity_raw AS "
                f"SELECT * FROM read_parquet('{bioactivity_path}')"
            )
            new_con.execute(
                f"CREATE OR REPLACE VIEW bioactivity AS "
                f"SELECT {_bioactivity_select_list()} "
                f"FROM read_parquet('{bioactivity_path}')"
            )
            pubchem_bridge_path = f"{base}/derived/pubchem_bridge.parquet"
            new_con.execute(
                f"CREATE OR REPLACE VIEW pubchem_bridge AS "
                f"SELECT * FROM read_parquet('{pubchem_bridge_path}')"
            )
            for view_name, filename in (
                ("assay_annotations", "assay_annotations.parquet"),
                ("assay_target_mappings", "assay_target_mappings.parquet"),
                ("cytotox", "cytotox.parquet"),
                ("analytical_qc", "analytical_qc.parquet"),
            ):
                path = f"{base}/reference/{filename}"
                new_con.execute(
                    f"CREATE OR REPLACE VIEW {view_name} AS "
                    f"SELECT * FROM read_parquet('{path}')"
                )
            _base_cons[release] = new_con
            con = new_con
    return con


def connect(release: str | None = None) -> "duckdb.DuckDBPyConnection":
    """A DuckDB connection against s3://scigantic-comptox.

    `SELECT * FROM bioactivity` gives the normalized winning-model table
    (see module docstring); `bioactivity_raw` and `pubchem_bridge` are also
    registered as views. release defaults to the manifest's latest().

    Returns an independent cursor() on a shared base connection for this
    release, safe to use and close() on its own without affecting other
    callers or re-paying the view-registration setup cost.
    """
    release = release or latest()
    _validate_release(release)
    return _get_base_connection(release).cursor()


def query(sql: str, release: str | None = None) -> "pd.DataFrame":
    """Run SQL against a release and return a pandas DataFrame.

    For several queries against the same release, call connect() once and
    reuse it instead, to avoid opening and closing a cursor per query.
    """
    resolved_release = release or latest()
    con = connect(resolved_release)
    try:
        df = con.execute(sql).df()
        df.attrs["comptox_release"] = resolved_release
        return df
    finally:
        con.close()
