from sre_toolkit.audit import diff_configs, to_markdown


def _drifts(expected, actual):
    return [(d.path, d.kind) for d in diff_configs(expected, actual)]


def test_no_drift():
    assert diff_configs({"a": 1, "b": {"c": 2}}, {"a": 1, "b": {"c": 2}}) == []


def test_changed_leaf():
    drifts = diff_configs({"replicas": 3}, {"replicas": 2})
    assert len(drifts) == 1
    assert drifts[0].path == "replicas"
    assert drifts[0].kind == "changed"
    assert drifts[0].expected == 3
    assert drifts[0].actual == 2


def test_missing_key():
    drifts = diff_configs({"a": 1, "b": 2}, {"a": 1})
    assert _drifts({"a": 1, "b": 2}, {"a": 1}) == [("b", "missing")]
    assert drifts[0].expected == 2
    assert drifts[0].actual is None


def test_extra_key():
    drifts = diff_configs({"a": 1}, {"a": 1, "b": 2})
    assert _drifts({"a": 1}, {"a": 1, "b": 2}) == [("b", "extra")]
    assert drifts[0].actual == 2


def test_nested_drift_path():
    drifts = diff_configs(
        {"db": {"pool": 10, "timeout": 30}},
        {"db": {"pool": 20, "timeout": 30}},
    )
    assert _drifts(
        {"db": {"pool": 10, "timeout": 30}},
        {"db": {"pool": 20, "timeout": 30}},
    ) == [("db.pool", "changed")]


def test_nested_missing_and_extra():
    drifts = _drifts(
        {"db": {"pool": 10, "host": "a"}},
        {"db": {"pool": 10, "port": 5432}},
    )
    assert drifts == [("db.host", "missing"), ("db.port", "extra")]


def test_dict_vs_scalar_is_changed():
    drifts = diff_configs({"db": {"pool": 10}}, {"db": 5})
    assert _drifts({"db": {"pool": 10}}, {"db": 5}) == [("db", "changed")]


def test_list_difference_is_changed():
    drifts = diff_configs({"zones": ["a", "b"]}, {"zones": ["a"]})
    assert _drifts({"zones": ["a", "b"]}, {"zones": ["a"]}) == [("zones", "changed")]


def test_empty_configs():
    assert diff_configs({}, {}) == []


def test_markdown_clean():
    md = to_markdown([])
    assert "Drifts found: 0" in md
    assert "No drift" in md


def test_markdown_table():
    drifts = diff_configs(
        {"replicas": 3, "db": {"pool": 10}},
        {"replicas": 2, "db": {"pool": 10}, "extra": True},
    )
    md = to_markdown(drifts)
    assert "Drifts found: 2" in md
    assert "- changed: 1" in md
    assert "- extra: 1" in md
    assert "| replicas | changed | 3 | 2 |" in md
    assert "| extra | extra | - | True |" in md
