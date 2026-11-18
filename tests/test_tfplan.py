from sre_toolkit.tfplan import (
    check_plan,
    changes_from_json,
    to_markdown,
    PlannedChange,
)


def _change(**kwargs) -> PlannedChange:
    defaults = dict(
        address="aws_instance.web",
        resource_type="aws_instance",
        action="create",
        owner="platform",
        approved=True,
    )
    defaults.update(kwargs)
    return PlannedChange(**defaults)


def test_clean_create_ok():
    results = check_plan([_change()])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_clean_update_ok():
    results = check_plan([_change(action="update")])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_noop_ok():
    results = check_plan([_change(action="no-op")])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_destroy_stateful_blocked():
    results = check_plan(
        [_change(action="destroy", resource_type="aws_db_instance")]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["destroy of stateful resource"]


def test_destroy_bucket_blocked():
    results = check_plan(
        [_change(action="destroy", resource_type="aws_s3_bucket")]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["destroy of stateful resource"]


def test_replace_volume_blocked():
    results = check_plan(
        [_change(action="replace", resource_type="aws_ebs_volume")]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == [
        "replace of stateful resource",
        "replace",
    ]


def test_destroy_without_approval_blocked():
    results = check_plan(
        [_change(action="destroy", approved=False)]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["destroy without approval"]


def test_replace_without_approval_blocked():
    results = check_plan(
        [_change(action="replace", approved=False)]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["replace without approval", "replace"]


def test_replace_approved_risky():
    results = check_plan(
        [_change(action="replace", approved=True)]
    )
    assert results[0].verdict == "risky"
    assert results[0].issues == ["replace"]


def test_update_iam_risky():
    results = check_plan(
        [_change(action="update", resource_type="aws_iam_role")]
    )
    assert results[0].verdict == "risky"
    assert results[0].issues == ["update to IAM resource"]


def test_update_security_group_risky():
    results = check_plan(
        [_change(action="update", resource_type="aws_security_group")]
    )
    assert results[0].verdict == "risky"
    assert results[0].issues == ["update to security group"]


def test_update_kms_risky():
    results = check_plan(
        [_change(action="update", resource_type="aws_kms_key")]
    )
    assert results[0].verdict == "risky"
    assert results[0].issues == ["update to KMS resource"]


def test_update_network_risky():
    results = check_plan(
        [_change(action="update", resource_type="aws_vpc")]
    )
    assert results[0].verdict == "risky"
    assert results[0].issues == ["update to network resource"]


def test_missing_owner_risky():
    results = check_plan([_change(owner="")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no owner"]


def test_blocked_beats_risky():
    results = check_plan(
        [_change(action="destroy", resource_type="aws_db_instance",
                 approved=False, owner="")]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == [
        "destroy of stateful resource",
        "destroy without approval",
        "no owner",
    ]


def test_markdown_counts_and_sorted():
    changes = [
        _change(address="aws_db_instance.main",
                resource_type="aws_db_instance", action="destroy"),
        _change(),
    ]
    md = to_markdown(check_plan(changes))
    assert "Changes checked: 2" in md
    assert "Blocked: 1" in md
    assert "OK: 1" in md
    assert md.index("aws_db_instance.main") < md.index("aws_instance.web")
    assert (
        "| aws_db_instance.main | aws_db_instance | destroy | yes "
        "| platform | blocked | destroy of stateful resource |" in md
    )
    assert (
        "| aws_instance.web | aws_instance | create | yes "
        "| platform | ok | — |" in md
    )


def test_markdown_empty():
    md = to_markdown([])
    assert "Changes checked: 0" in md
    assert "No changes to check." in md


def test_changes_from_json_defaults():
    changes = changes_from_json([{"address": "aws_instance.web"}])
    assert changes[0].resource_type == ""
    assert changes[0].action == "no-op"
    assert changes[0].owner == ""
    assert changes[0].approved is False
