from sre_toolkit.configmap import (
    check_config_maps,
    config_maps_from_json,
    to_markdown,
    ConfigMap,
)


def _cm(**kwargs) -> ConfigMap:
    defaults = dict(
        name="app-config",
        namespace="prod",
        keys=4,
        empty_keys=0,
        size_kb=12,
        owner="platform",
    )
    defaults.update(kwargs)
    return ConfigMap(**defaults)


def test_clean_ok():
    results = check_config_maps([_cm()])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_no_data_keys_blocked():
    results = check_config_maps([_cm(keys=0)])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no data keys"]


def test_exceeds_limit_blocked():
    results = check_config_maps([_cm(size_kb=2048)])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["exceeds 1MiB limit"]


def test_empty_values_risky():
    results = check_config_maps([_cm(empty_keys=1)])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["empty values"]


def test_large_configmap_risky():
    results = check_config_maps([_cm(size_kb=800)])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["large configmap"]


def test_missing_owner_risky():
    results = check_config_maps([_cm(owner="")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no owner"]


def test_blocked_beats_risky():
    results = check_config_maps([_cm(keys=0, owner="")])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no data keys", "no owner"]


def test_size_boundary_not_large():
    results = check_config_maps([_cm(size_kb=512)])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_markdown_counts_and_sorted():
    maps = [
        _cm(namespace="staging", name="cache-config", keys=0),
        _cm(),
    ]
    md = to_markdown(check_config_maps(maps))
    assert "ConfigMaps checked: 2" in md
    assert "Blocked: 1" in md
    assert "OK: 1" in md
    assert md.index("prod") < md.index("staging")
    assert (
        "| staging | cache-config | 0 | 0 | 12 | platform "
        "| blocked | no data keys |" in md
    )
    assert (
        "| prod | app-config | 4 | 0 | 12 | platform | ok | — |"
        in md
    )


def test_markdown_empty():
    md = to_markdown([])
    assert "ConfigMaps checked: 0" in md
    assert "No ConfigMaps to check." in md


def test_config_maps_from_json_defaults():
    maps = config_maps_from_json([{"name": "x", "namespace": "y"}])
    assert maps[0].keys == 0
    assert maps[0].empty_keys == 0
    assert maps[0].size_kb == 0
    assert maps[0].owner == ""
