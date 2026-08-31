from scigantic_comptox.connection import connect, query


def test_query_returns_dataframe_with_release_attr():
    df = query("SELECT COUNT(*) AS n FROM bioactivity")
    assert df.attrs["comptox_release"] == "v4_3"
    assert df["n"].iloc[0] > 0


def test_connect_returns_independent_cursor():
    con1 = connect()
    con2 = connect()
    try:
        assert con1 is not con2
        r1 = con1.execute("SELECT 1").fetchone()
        r2 = con2.execute("SELECT 2").fetchone()
        assert r1 == (1,)
        assert r2 == (2,)
    finally:
        con1.close()
        con2.close()


def test_pubchem_bridge_view_registered():
    con = connect()
    try:
        row = con.execute("SELECT COUNT(*) FROM pubchem_bridge").fetchone()
        assert row[0] > 0
    finally:
        con.close()
