from sre_toolkit.dns import check_dns, resolve_host, to_markdown


def test_localhost_resolves():
    result = resolve_host("localhost")
    assert result.ok
    assert "127.0.0.1" in result.addresses
    assert result.error == ""


def test_invalid_host_fails():
    result = resolve_host("not a host")
    assert not result.ok
    assert result.addresses == []
    assert result.error


def test_check_dns_mixed():
    results = check_dns(["localhost", "not a host"])
    assert [r.ok for r in results] == [True, False]
    assert results[0].host == "localhost"
    assert results[1].host == "not a host"


def test_markdown_summary():
    results = check_dns(["localhost", "not a host"])
    md = to_markdown(results)
    assert "Hosts checked: 2" in md
    assert "- Resolved: 1" in md
    assert "- Failed: 1" in md
    assert "| localhost | 127.0.0.1 | ok |" in md
    assert "failed:" in md


def test_markdown_empty():
    md = to_markdown([])
    assert "Hosts checked: 0" in md
    assert "No hosts to check." in md
