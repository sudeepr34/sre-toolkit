"""Generate on-call shift handoff notes: incidents, follow-ups, watch items."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HandoffItem:
    title: str
    status: str = "open"  # open | mitigated | resolved
    owner: str = "on-call"
    link: str = ""


@dataclass
class Handoff:
    author: str
    shift_date: str = ""
    items: list[HandoffItem] = field(default_factory=list)
    watch_items: list[str] = field(default_factory=list)

    def add(self, title: str, status: str = "open", owner: str = "on-call", link: str = "") -> HandoffItem:
        item = HandoffItem(title=title, status=status, owner=owner, link=link)
        self.items.append(item)
        return item

    def watch(self, note: str) -> None:
        self.watch_items.append(note)

    @property
    def open_count(self) -> int:
        return sum(1 for i in self.items if i.status == "open")

    def to_markdown(self) -> str:
        lines = [f"# On-call handoff — {self.shift_date or 'today'} (by {self.author})", ""]
        lines.append("## Incidents & follow-ups")
        for item in self.items or [HandoffItem("nothing to hand off — quiet shift", status="resolved")]:
            lines.append(f"- [{item.status}] {item.title} (owner: {item.owner})" + (f" — {item.link}" if item.link else ""))
        if self.watch_items:
            lines.append("")
            lines.append("## Watch items")
            lines.extend(f"- {w}" for w in self.watch_items)
        lines.append("")
        lines.append(f"Open items: {self.open_count}")
        return "\n".join(lines)
