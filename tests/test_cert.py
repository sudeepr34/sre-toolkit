from datetime import date

from sre_toolkit.cert import (
    attention_needed,
    check_certs,
    records_from_json,
    to_markdown,
    CertRecord,
)

TODAY = date(2026, 11, 6)


def test_ok_cert():
    results = check_certs([CertRecord("a.example.com", "2027-01-01")], TODAY)
    assert results[0].status == "ok"
    assert results[0].days_left == 56


def test_warn_cert():
    results = check_certs([CertRecord("a.example.com", "2026-11-25")], TODAY)
    assert results[0].status == "warn"
    assert results[0].days_left == 19


def test_critical_cert():
    results = check_certs([CertRecord("a.example.com", "2026-11-10")], TODAY)
    assert results[0].status == "critical"
    assert results[0].days_left == 4


def test_expired_cert():
    results = check_certs([CertRecord("a.example.com", "2026-11-01")], TODAY)
    assert results[0].status == "expired"
    assert results[0].days_left == -5


def test_boundary_exactly_warn_days_is_ok():
    results = check_certs([CertRecord("a.example.com", "2026-12-06")], TODAY)
    assert results[0].status == "ok"


def test_boundary_exactly_critical_days_is_warn():
    results = check_certs([CertRecord("a.example.com", "2026-11-13")], TODAY)
    assert results[0].status == "warn"


def test_unknown_expiry():
    results = check_certs([CertRecord("a.example.com", "soon")], TODAY)
    assert results[0].status == "unknown"
    assert results[0].days_left is None


def test_attention_needed():
    ok = check_certs([CertRecord("a.example.com", "2027-01-01")], TODAY)
    assert attention_needed(ok) is False
    warn = check_certs([CertRecord("a.example.com", "2026-11-25")], TODAY)
    assert attention_needed(warn) is False
    critical = check_certs([CertRecord("a.example.com", "2026-11-10")], TODAY)
    assert attention_needed(critical) is True


def test_markdown_summary():
    records = [
        CertRecord("a.example.com", "2027-01-01"),
        CertRecord("b.example.com", "2026-11-10"),
        CertRecord("c.example.com", "2026-11-01"),
    ]
    md = to_markdown(check_certs(records, TODAY))
    assert "Certificates checked: 3" in md
    assert "- Expired: 1" in md
    assert "- Critical: 1" in md
    assert "- OK: 1" in md
    assert "| b.example.com | 2026-11-10 | 4 | critical |" in md


def test_records_from_json_defaults():
    records = records_from_json([{"host": "x.example.com", "expires": "2027-01-01"}])
    assert records[0].issuer == ""
