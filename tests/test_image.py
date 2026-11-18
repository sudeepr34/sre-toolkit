from sre_toolkit.image import (
    check_images,
    images_from_json,
    to_markdown,
    ImageRef,
)


def _image(**kwargs) -> ImageRef:
    defaults = dict(
        image="api",
        tag="1.4.2",
        digest_pinned=True,
        age_days=12,
        owner="platform",
    )
    defaults.update(kwargs)
    return ImageRef(**defaults)


def test_clean_image_ok():
    results = check_images([_image()])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_latest_tag_blocked():
    results = check_images([_image(tag="latest")])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["latest tag"]


def test_latest_tag_case_insensitive():
    results = check_images([_image(tag="Latest")])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["latest tag"]


def test_no_tag_blocked():
    results = check_images([_image(tag="")])
    assert results[0].verdict == "blocked"
    assert results[0].issues == ["no tag"]


def test_not_pinned_risky():
    results = check_images([_image(digest_pinned=False)])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["not pinned by digest"]


def test_stale_image_risky():
    results = check_images([_image(age_days=200)])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["image older than 180 days"]


def test_fresh_image_ok():
    results = check_images([_image(age_days=180)])
    assert results[0].verdict == "ok"
    assert results[0].issues == []


def test_missing_owner_risky():
    results = check_images([_image(owner="")])
    assert results[0].verdict == "risky"
    assert results[0].issues == ["no owner"]


def test_blocked_beats_risky():
    results = check_images(
        [_image(tag="latest", digest_pinned=False, owner="")]
    )
    assert results[0].verdict == "blocked"
    assert results[0].issues == [
        "latest tag",
        "not pinned by digest",
        "no owner",
    ]


def test_multiple_risky_issues():
    results = check_images(
        [_image(digest_pinned=False, age_days=300, owner="")]
    )
    assert results[0].verdict == "risky"
    assert results[0].issues == [
        "not pinned by digest",
        "image older than 180 days",
        "no owner",
    ]


def test_markdown_counts_and_sorted():
    images = [
        _image(image="worker", tag="latest"),
        _image(),
    ]
    md = to_markdown(check_images(images))
    assert "Images checked: 2" in md
    assert "Blocked: 1" in md
    assert "OK: 1" in md
    assert md.index("api") < md.index("worker")
    assert (
        "| api | 1.4.2 | yes | 12 | platform | ok | — |" in md
    )
    assert (
        "| worker | latest | yes | 12 | platform | blocked "
        "| latest tag |" in md
    )


def test_markdown_empty():
    md = to_markdown([])
    assert "Images checked: 0" in md
    assert "No images to check." in md


def test_images_from_json_defaults():
    images = images_from_json([{"image": "api"}])
    assert images[0].tag == ""
    assert images[0].digest_pinned is False
    assert images[0].age_days == 0
    assert images[0].owner == ""
