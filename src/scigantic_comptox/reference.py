"""Small reference tables EPA publishes alongside the ToxCast winning-model
fact table, mirrored for the same reason the fact table itself is: a real
external evaluation of this package (using it as a transfer-learning signal
for a chemistry challenge) needed all four and had to work around their
absence -- filtering assays by target family via string-matching on assay
names instead of a real annotation, no cytotoxicity-burst context to judge
whether a hit call sits in a chemically-uninterpretable concentration range,
no sample-level QC to weight readouts by reliability. All four are small
(under 3MB combined) and ship from the same EPA release as the fact table,
so mirroring them alongside it closes a class of gap rather than one
instance of it.

- `assay_annotations()`: per-assay-endpoint design and target metadata,
  including `intended_target_family` -- the actual fix for "filter to
  CYP-relevant (or any target-family-relevant) assays" without guessing
  from assay names.
- `assay_target_mappings()`: assay-to-gene mapping in long form (one row per
  assay/target pair; a single assay can map to multiple targets, including
  non-gene target types like AOPs). Genuinely distinct from
  assay_annotations() -- that table's target_family/target_type columns are
  broad categories, this one carries actual Entrez gene ids and official
  gene symbols.
- `cytotox()`: per-chemical cytotoxicity burst summary. A hit call near a
  chemical's cytotoxic concentration is a well-known ToxCast confound --
  this is what lets a caller check for it.
- `analytical_qc()`: per-chemical/per-sample QC pass/caution flags, plus a
  few OPERA-predicted physicochemical properties (molecular weight, vapor
  pressure, logKow) that happen to ride along in this file -- not a
  substitute for the still-unmirrored DSSTox structures, but real signal
  where it's available.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .connection import connect
from .releases import _require, latest

if TYPE_CHECKING:
    import pandas as pd


def assay_annotations(
    aeid: int | None = None,
    intended_target_family: str | None = None,
    release: str | None = None,
    limit: int | None = None,
) -> "pd.DataFrame":
    """Per-assay-endpoint design and target metadata.

    aeid: a single ToxCast assay endpoint id.
    intended_target_family: exact match against EPA's own target-family
    category (e.g. "nuclear receptor", "cyp"; call without a filter first
    to see the real category values before assuming one).
    """
    release = release or latest()
    _require(release, "assay_annotations")
    con = connect(release)
    try:
        where: list[str] = []
        params: list[str | int] = []
        if aeid is not None:
            where.append("aeid = ?")
            params.append(aeid)
        if intended_target_family is not None:
            where.append("intended_target_family = ?")
            params.append(intended_target_family)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        sql = f"SELECT * FROM assay_annotations {clause}"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        return con.execute(sql, params).df()
    finally:
        con.close()


def assay_target_mappings(
    aeid: int | None = None,
    official_symbol: str | None = None,
    release: str | None = None,
    limit: int | None = None,
) -> "pd.DataFrame":
    """Assay-to-gene/target mapping, one row per (assay, target) pair.

    aeid: a single ToxCast assay endpoint id.
    official_symbol: exact match against a gene's official symbol (e.g.
    "CYP2D6", "ESR1"). Rows with a non-gene target_type (e.g. "aop") have
    no official_symbol and won't match this filter.
    """
    release = release or latest()
    _require(release, "assay_target_mappings")
    con = connect(release)
    try:
        where: list[str] = []
        params: list[str | int] = []
        if aeid is not None:
            where.append("aeid = ?")
            params.append(aeid)
        if official_symbol is not None:
            where.append("official_symbol = ?")
            params.append(official_symbol)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        sql = f"SELECT * FROM assay_target_mappings {clause}"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        return con.execute(sql, params).df()
    finally:
        con.close()


def cytotox(
    dtxsid: str | None = None,
    release: str | None = None,
    limit: int | None = None,
) -> "pd.DataFrame":
    """Per-chemical cytotoxicity burst summary (median/lower-bound active
    concentration across the ToxCast cytotoxicity assay panel, plus a
    global median absolute deviation used to judge how far a hit call sits
    from the cytotoxic range).

    dtxsid: a single DSSTox substance id.
    """
    release = release or latest()
    _require(release, "cytotox")
    con = connect(release)
    try:
        where: list[str] = []
        params: list[str | int] = []
        if dtxsid is not None:
            where.append("dsstox_substance_id = ?")
            params.append(dtxsid)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        sql = f"SELECT * FROM cytotox {clause}"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        return con.execute(sql, params).df()
    finally:
        con.close()


def analytical_qc(
    dtxsid: str | None = None,
    release: str | None = None,
    limit: int | None = None,
) -> "pd.DataFrame":
    """Per-chemical/per-sample analytical QC: pass/caution flags, a
    stability call, and a few OPERA-predicted physicochemical properties
    (average_mass, vapor pressure, logKow) that ship in this file.

    dtxsid: a single DSSTox substance id.
    """
    release = release or latest()
    _require(release, "analytical_qc")
    con = connect(release)
    try:
        where: list[str] = []
        params: list[str | int] = []
        if dtxsid is not None:
            where.append("dsstox_substance_id = ?")
            params.append(dtxsid)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        sql = f"SELECT * FROM analytical_qc {clause}"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        return con.execute(sql, params).df()
    finally:
        con.close()
