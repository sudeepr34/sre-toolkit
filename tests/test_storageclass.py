from sre_toolkit.storageclass import (
    check_storage_classes,
    storage_classes_from_json,
    to_markdown,
    StorageClass,
)


def _sc(**kwargs) -> StorageClass:
    defaults = dict(
        name="fast",
        provisioner="ebs.csi.aws.com",
        reclaim_policy="Retain",
        is_default=True,
        owner="platform",
    )
    defaults.update(kwargs)
    return StorageClass(**defaults)


def test_clean_ok():
    results = check_storage_classes([_sc()])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_delete_reclaim_risky():
    results = check_storage_classes([_sc(reclaim_policy="Delete")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["delete reclaim policy"]


def test_no_provisioner_blocked():
    results = check_storage_classes([_sc(provisioner="")])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no provisioner"]


def test_duplicate_default_risky():
    results = check_storage_classes([_sc(), _sc(name="slow")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["duplicate default class"]
    assert results[1].verdict == "risky"
    assert results[1].issues == ["duplicate default class"]


def test_no_default_risky():
    results = check_storage_classes(
        [_sc(is_default=False), _sc(name="slow", is_default=False)]
    )
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no default storage class"]
    assert results[1].verdict == "risky"
    assert results[1].issues == ["no default storage class"]


def test_no_provisioner_plugin_risky():
    results = check_storage_classes(
        [_sc(provisioner="kubernetes.io/no-provisioner")]
    )
    assert results[0].verdict == "risky"
    assert results[0].issues == ["manual provisioning only"]


def test_missing_owner_risky():
    results = check_storage_classes([_sc(owner="")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no owner"]


def test_delete_reclaim_and_no_default():
    results = check_storage_classes(
        [_sc(reclaim_policy="Delete", is_default=False)]
    )
    assert results[0].verdict == "risky"
    assert results[0].issues == [
        "delete reclaim policy",
        "no default storage class",
    ]


def test_blocked_beats_risky():
    results = check_storage_classes([_sc(provisioner="", owner="")])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no provisioner", "no owner"]


def test_markdown_counts_and_sorted():
    classes = [
        _sc(name="slow", provisioner="", reclaim_policy="Retain",
            is_default=False),
        _sc(),
    ]
    md = to_markdown(check_storage_classes(classes))
    assert "StorageClasses checked: 2" in md
    assert "Blocked: 1" in md
    assert "OK: 1" in md
    assert md.index("fast") < md.index("slow")
    assert "| slow | — | Retain | no | platform | blocked | no provisioner |" in md
    assert "| fast | ebs.csi.aws.com | Retain | yes | platform | ok | — |" in md


def test_markdown_empty():
    md = to_markdown([])
    assert "StorageClasses checked: 0" in md
    assert "No StorageClasses to check." in md


def test_storage_classes_from_json_defaults():
    classes = storage_classes_from_json([{"name": "x"}])
    assert classes[0].provisioner == ""
    assert classes[0].reclaim_policy == "Delete"
    assert classes[0].is_default is False
    assert classes[0].owner == ""
