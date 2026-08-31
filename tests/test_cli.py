from scigantic_comptox.cli import main


def test_info_command(capsys):
    exit_code = main(["info"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "v4_3" in out
    assert "bioactivity" in out


def test_query_command(capsys):
    exit_code = main(["query", "SELECT COUNT(*) AS n FROM bioactivity"])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "n" in out
