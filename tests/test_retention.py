from sre_toolkit.retention import (
    check_retention,
    records_from_json,
    to_markdown,
    RetentionRecord,
)


def _record(**kwargs) -> RetentionRecord:
    defaults = dict(service="api", log_type="access",
                    retention_days=90, required_days=30)
    defaults.update(kwargs)
    return RetentionRecord(**defaults)


def test_compliant_when_above_policy():
    results = check_retention([_record()])
    assert results[0].status == "compliant"
    assert "90d retained (policy 30d)" in results[0].detail


def test_exactly_at_policy_is_compliant():
    results = check_retention([_record(retention_days=30)])
    assert results[0].status == "compliant"


def test_shortfall_reports_gap():
    results = check_retention([_record(retention_days=7)])
    assert results[0].status == "shortfall"
    assert "7d retained, 23d short of policy 30d" in results[0].detail


def test_missing_when_not_configured():
    results = check_retention([_record(retention_days=None)])
    assert results[0].status == "missing"
    assert "not configured" in results[0].detail


def test_label_combines_service_and_log_type():
    results = check_retention([_record()])
    assert results[0].label == "api/access"


def test_markdown_lists_gaps():
    results = check_retention([
        _record(),
        _record(service="db", retention_days=7),
        _record(service="queue", retention_days=None),
    ])
    md = to_markdown(results)
    assert "# Retention check" in md
    assert "Checked 3 records: 1 compliant, 1 missing, 1 shortfall" in md
    assert "| db/access | shortfall |" in md
    assert "| queue/access | missing |" in md
    assert "## Gaps" in md
    assert "- db/access: 7d retained, 23d short of policy 30d" in md


def test_markdown_all_compliant_message():
    md = to_markdown(check_retention([_record()]))
    assert "All retention meets policy." in md


def test_records_from_json_defaults():
    records = records_from_json([{"service": "x"}])
    assert records[0].log_type == "all"
    assert records[0].retention_days is None
    assert records[0].required_days == 30


def test_records_from_json_null_retention():
    records = records_from_json([{
        "service": "x", "retention_days": None, "required_days": 90,
    }])
    assert records[0].retention_days is None
    assert records[0].required_days == 90
