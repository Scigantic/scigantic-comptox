"""EPA's own per-assay-endpoint PubChem BioAssay submission data, wrapped
as a single table rather than 1,536 separate files.

CORRECTION (as of the structures/v0.3.0 release): despite this table's
original name, it does NOT contain a PubChem CID. `tx_sample_id` is EPA's
own ToxCast sample identifier, used when EPA submits this bioactivity data
TO PubChem's BioAssay system (`pubchem_invitrodb_v4_3_*.zip`, 1,536 files,
one per assay endpoint) -- it is not something a caller can resolve back
into a CID. There is no `cid` column in this table, and never was; earlier
docs (including this module's own, before this correction) described it as
a "PubChem CID cross-reference," which was wrong.

For an actual chemical-to-PubChem-CID cross-reference, use `structures()`
(structures.py) instead -- built separately by resolving each chemical's
DTXSID against PubChem's own live compound search, not sourced from this
table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .connection import connect
from .releases import _require, latest

if TYPE_CHECKING:
    import pandas as pd


def pubchem_bridge(
    dtxsid: str | None = None,
    aeid: int | None = None,
    release: str | None = None,
    limit: int | None = None,
) -> "pd.DataFrame":
    """EPA's ToxCast-to-PubChem cross-reference: (aeid, tx_sample_id,
    dtxsid, activity_outcome, ac50_um, hitc, bmd_um) rows, one per assay
    endpoint's tested samples.

    release defaults to the manifest's current latest().
    """
    release = release or latest()
    _require(release, "pubchem_bridge")
    con = connect(release)
    try:
        where: list[str] = []
        params: list[str | int] = []
        if dtxsid is not None:
            where.append("dtxsid = ?")
            params.append(dtxsid)
        if aeid is not None:
            where.append("aeid = ?")
            params.append(aeid)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        sql = f"SELECT * FROM pubchem_bridge {clause}"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        return con.execute(sql, params).df()
    finally:
        con.close()


def pubchem_bridge_many(
    dtxsids: list[str],
    release: str | None = None,
) -> "pd.DataFrame":
    """pubchem_bridge() rows for MANY chemicals in one batched query.

    Same reasoning as bioactivity_many(): the mirror isn't sorted or
    partitioned by chemical id, so looping pubchem_bridge(dtxsid=...) per id
    pays a near-full-scan cost per call. Use this for anything beyond a
    handful of lookups.
    """
    release = release or latest()
    _require(release, "pubchem_bridge")
    import pandas as pd

    if not dtxsids:
        return pd.DataFrame()
    con = connect(release)
    try:
        placeholders = ", ".join(["?"] * len(dtxsids))
        sql = f"SELECT * FROM pubchem_bridge WHERE dtxsid IN ({placeholders})"
        return con.execute(sql, list(dtxsids)).df()
    finally:
        con.close()
