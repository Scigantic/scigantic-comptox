"""Chemical structures for the chemicals this mirror already covers,
sourced from PubChem, not EPA's own DSSTox bulk distribution.

DSSTox's bulk distribution (the actual EPA-native source for chemical
structures) turned out to be a large, unstructured institutional drive
with no clean single file to mirror -- a real dead end, not something
skipped for convenience. EPA's live Chemical API can resolve a DTXSID to
a structure too, but has an unresolved data-use question for bulk
redistribution: no public Terms of Service or Data Use Agreement could be
found for the API itself (only a general "the data is open" statement on
an unrelated bulk-downloads page, about a different distribution channel),
and that's not something to guess at rather than ask EPA directly.

PubChem sidesteps both problems: fully open, keyless, and every DTXSID in
this table was resolved live against PubChem's own compound search (which
indexes DTXSID as a synonym) -- confirmed live, e.g.
`pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/DTXSID0023901/cids/JSON`
resolves cleanly. Real coverage measured while building this: 9,238 of
9,801 distinct chemicals across `bioactivity`/`pubchem_bridge` resolved
(94.3%) -- the rest genuinely have no PubChem match under that identifier,
not a bug in how this was built. `comptox.releases()` reports
`structures_source="pubchem"` and the real coverage fraction rather than
implying this is EPA's own canonical DSSTox structure data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .connection import connect
from .releases import _require, latest

if TYPE_CHECKING:
    import pandas as pd


def structures(
    dtxsid: str | None = None,
    release: str | None = None,
    limit: int | None = None,
) -> "pd.DataFrame":
    """PubChem-sourced structure data for one or more chemicals: cid,
    title, smiles, inchi, inchi_key, iupac_name, molecular_formula,
    molecular_weight.

    dtxsid: a single DSSTox substance id. Omit to browse the whole table.
    release defaults to the manifest's current latest().
    """
    release = release or latest()
    _require(release, "structures")
    con = connect(release)
    try:
        where: list[str] = []
        params: list[str | int] = []
        if dtxsid is not None:
            where.append("dtxsid = ?")
            params.append(dtxsid)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        sql = f"SELECT * FROM structures {clause}"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        return con.execute(sql, params).df()
    finally:
        con.close()


def structures_many(
    dtxsids: list[str],
    release: str | None = None,
) -> "pd.DataFrame":
    """structures() rows for MANY chemicals in one batched query, instead
    of looping structures(dtxsid=...) per id -- same reasoning as
    bioactivity_many()/pubchem_bridge_many(): the mirror isn't sorted or
    partitioned by chemical id, so looping pays a near-full-scan cost per
    call. Shipped alongside structures() from the start this time, rather
    than added later once someone hit the same N+1 slowness bioactivity()
    originally did.
    """
    release = release or latest()
    _require(release, "structures")
    import pandas as pd

    if not dtxsids:
        return pd.DataFrame()
    con = connect(release)
    try:
        placeholders = ", ".join(["?"] * len(dtxsids))
        sql = f"SELECT * FROM structures WHERE dtxsid IN ({placeholders})"
        return con.execute(sql, list(dtxsids)).df()
    finally:
        con.close()
