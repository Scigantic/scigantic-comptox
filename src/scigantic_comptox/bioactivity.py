"""ToxCast bioactivity: the winning dose-response model and hit-call for
each (chemical, assay endpoint) pair, from EPA's `invitrodb` v4.3 summary
tier (`mc5-6_winning_model_fits`), the same level of detail as PubChem's
own `concise` BioAssay tables. This is the real, verified gap versus EPA's
own `ctx-python` client, which covers Chemical/Exposure/Hazard but not
Bioactivity/ToxCast at all.

Deliberately NOT mirrored: `mc4_all_model_fits` (every losing candidate
curve model alongside the winner) -- that's what made EPA's "summary"
bundle grow from 1.5GB at v3.3 to 7.0GB at v4.3, for detail almost no
caller needs (the winning model plus hit-call is what a bioactivity lookup
actually wants).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .connection import connect
from .releases import _require, latest

if TYPE_CHECKING:
    import pandas as pd


def bioactivity(
    dtxsid: str | None = None,
    aeid: int | None = None,
    hitc: float | None = None,
    release: str | None = None,
    limit: int | None = None,
) -> "pd.DataFrame":
    """Winning-model bioactivity results, optionally filtered.

    dtxsid: a single DSSTox substance id (e.g. "DTXSID7020182"), matched
    against the normalized dsstox_substance_id column (the raw "NA" string
    EPA's export uses for missing values is already excluded, see
    connection.py).
    aeid: a single ToxCast assay endpoint id.
    hitc: filter to an exact hit-call value (1.0 = active, 0.0 = inactive,
    other fractional values represent ambiguous/borderline calls per EPA's
    own tcpl methodology).
    release defaults to the manifest's current latest().
    """
    release = release or latest()
    _require(release, "bioactivity")
    con = connect(release)
    try:
        where: list[str] = []
        params: list[str | int | float] = []
        if dtxsid is not None:
            where.append("dsstox_substance_id = ?")
            params.append(dtxsid)
        if aeid is not None:
            where.append("aeid = ?")
            params.append(aeid)
        if hitc is not None:
            where.append("hitc = ?")
            params.append(hitc)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        sql = f"SELECT * FROM bioactivity {clause}"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        return con.execute(sql, params).df()
    finally:
        con.close()


def bioactivity_raw(
    release: str | None = None,
    limit: int | None = None,
) -> "pd.DataFrame":
    """The winning-model table exactly as EPA ships it, with no
    normalization: the literal "NA" strings and text-typed numeric columns
    (ac50, bmd, top, and others -- see connection.py's module docstring)
    are left as-is. Use bioactivity() for a cleaned version.
    """
    release = release or latest()
    _require(release, "bioactivity")
    con = connect(release)
    try:
        sql = "SELECT * FROM bioactivity_raw"
        params: list[int] = []
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        return con.execute(sql, params).df()
    finally:
        con.close()
