from sre_toolkit.pdb import (
    check_pdbs,
    pdbs_from_json,
    to_markdown,
    PodDisruptionBudget,
)


def _pdb(**kwargs) -> PodDisruptionBudget:
    defaults = dict(
        name="api",
        namespace="prod",
        min_available=1,
        max_unavailable=None,
        disruptions_allowed=2,
        replicas=3,
        owner="platform",
    )
    defaults.update(kwargs)
    return PodDisruptionBudget(**defaults)


def test_clean_ok():
    results = check_pdbs([_pdb()])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_blocks_all_drains():
    results = check_pdbs([_pdb(disruptions_allowed=0)])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["blocks all drains"]


def test_min_equals_replicas_blocked():
    results = check_pdbs(
        [_pdb(min_available=3, disruptions_allowed=0)]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == [
        "min available equals replicas",
        "blocks all drains",
    ]


def test_max_unavailable_zero_blocked():
    results = check_pdbs(
        [_pdb(min_available=None, max_unavailable=0,
              disruptions_allowed=0)]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == [
        "blocks all drains",
        "max unavailable is 0",
    ]


def test_no_min_or_max_blocked():
    results = check_pdbs(
        [_pdb(min_available=None, max_unavailable=None)]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no min or max set"]


def test_max_unavailable_ok():
    results = check_pdbs(
        [_pdb(min_available=None, max_unavailable=1)]
    )
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_missing_owner_risky():
    results = check_pdbs([_pdb(owner="")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no owner"]


def test_blocked_beats_risky():
    results = check_pdbs(
        [_pdb(disruptions_allowed=0, owner="")]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["blocks all drains", "no owner"]


def test_markdown_counts_and_sorted():
    pdbs = [
        _pdb(namespace="staging", name="web", disruptions_allowed=0),
        _pdb(),
    ]
    md = to_markdown(check_pdbs(pdbs))
    assert "PDBs checked: 2" in md
    assert "Blocked: 1" in md
    assert "OK: 1" in md
    assert md.index("prod") < md.index("staging")
    assert "| staging | web | 1 | — | 0 | 3 | platform | blocked | blocks all drains |" in md
    assert "| prod | api | 1 | — | 2 | 3 | platform | ok | — |" in md


def test_markdown_empty():
    md = to_markdown([])
    assert "PDBs checked: 0" in md
    assert "No PDBs to check." in md


def test_pdbs_from_json_defaults():
    pdbs = pdbs_from_json([{"name": "x", "namespace": "y"}])
    assert pdbs[0].min_available is None
    assert pdbs[0].max_unavailable is None
    assert pdbs[0].disruptions_allowed == 0
    assert pdbs[0].replicas == 0
    assert pdbs[0].owner == ""
