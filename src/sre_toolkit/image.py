"""Container image audit.

A workload running `latest` is running whatever happened to be
newest when the pod started — unrepeatable, unreviewable, and one
bad push away from a silent downgrade. This checks a JSON list of
container images and flags the ones that must not reach production
unpinned, so the image list is gated — or the reference fixed —
before the rollout runs.
"""
from __future__ import annotations

from dataclasses import dataclass

STALE_DAYS = 180


@dataclass
class ImageRef:
    image: str = "unnamed"
    tag: str = ""
    digest_pinned: bool = False
    age_days: int = 0
    owner: str = ""


@dataclass
class ImageResult:
    image: ImageRef
    verdict: str  # ok, risky, blocked
    issues: list  # e.g. ["latest tag"]


def check_images(images: list) -> list:
    results = []
    for image in images:
        issues = []
        blocked = False
        tag = image.tag.strip().lower()
        if not tag:
            issues.append("no tag")
            blocked = True
        elif tag == "latest":
            issues.append("latest tag")
            blocked = True
        if not image.digest_pinned:
            issues.append("not pinned by digest")
        if image.age_days > STALE_DAYS:
            issues.append(f"image older than {STALE_DAYS} days")
        if not image.owner:
            issues.append("no owner")
        if blocked:
            verdict = "blocked"
        elif issues:
            verdict = "risky"
        else:
            verdict = "ok"
        results.append(ImageResult(image, verdict, issues))
    return results


def to_markdown(results: list) -> str:
    counts: dict[str, int] = {}
    for result in results:
        counts[result.verdict] = counts.get(result.verdict, 0) + 1
    lines = ["# Container image audit", ""]
    lines.append(f"- Images checked: {len(results)}")
    lines.append(f"- OK: {counts.get('ok', 0)}")
    lines.append(f"- Risky: {counts.get('risky', 0)}")
    lines.append(f"- Blocked: {counts.get('blocked', 0)}")
    lines.append("")
    if not results:
        lines.append("No images to check.")
        return "\n".join(lines) + "\n"
    lines.append("## Images")
    lines.append(
        "| Image | Tag | Digest pinned | Age (days) | Owner | Verdict | Issues |"
    )
    lines.append(
        "| ----- | --- | ------------- | ---------- | ----- | ------- | ------ |"
    )
    for result in sorted(results, key=lambda r: r.image.image):
        image = result.image
        pinned = "yes" if image.digest_pinned else "no"
        owner = image.owner or "—"
        issues = ", ".join(result.issues) if result.issues else "—"
        lines.append(
            f"| {image.image} | {image.tag} "
            f"| {pinned} | {image.age_days} | {owner} "
            f"| {result.verdict} | {issues} |"
        )
    return "\n".join(lines) + "\n"


def images_from_json(data: list) -> list:
    images = []
    for item in data:
        images.append(
            ImageRef(
                image=item.get("image", "unnamed"),
                tag=item.get("tag", ""),
                digest_pinned=bool(item.get("digest_pinned", False)),
                age_days=int(item.get("age_days", 0)),
                owner=item.get("owner", ""),
            )
        )
    return images
