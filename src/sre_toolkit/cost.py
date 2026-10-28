"""Cost attribution.

Turns a JSON list of spend records into a report an SRE can take to a
planning review: total spend, top spenders with share, month-over-month
change, and services over budget. Currency-agnostic: amounts are just
numbers, so it works for dollars, rupees, or cloud credits.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CostRecord:
    service: str
    amount: float
    month: str = ""  # YYYY-MM; empty means unassigned to a month


def total(records: list) -> float:
    return sum(r.amount for r in records)


def by_service(records: list) -> list:
    """(service, amount) pairs, highest spend first."""
    totals: dict[str, float] = {}
    for record in records:
        totals[record.service] = totals.get(record.service, 0.0) + record.amount
    return sorted(totals.items(), key=lambda item: item[1], reverse=True)


def top_spenders(records: list, n: int = 5) -> list:
    """Top n services with their share of total spend."""
    grand = total(records)
    return [
        {
            "service": service,
            "amount": amount,
            "share": (amount / grand) if grand else 0.0,
        }
        for service, amount in by_service(records)[:n]
    ]


def month_totals(records: list) -> dict:
    totals: dict[str, float] = {}
    for record in records:
        if record.month:
            totals[record.month] = totals.get(record.month, 0.0) + record.amount
    return totals


def mom_change(records: list, month: str, prev_month: str) -> dict | None:
    """Month-over-month change; None when either month has no records."""
    totals = month_totals(records)
    if month not in totals or prev_month not in totals:
        return None
    current, previous = totals[month], totals[prev_month]
    delta = current - previous
    pct = (delta / previous) if previous else None
    return {"month": month, "prev_month": prev_month,
            "current": current, "previous": previous,
            "delta": delta, "pct": pct}


def over_budget(records: list, budgets: dict) -> list:
    """Services whose spend exceeds their budget, worst overrun first."""
    spent = dict(by_service(records))
    over = [
        {
            "service": service,
            "spent": spent[service],
            "budget": budget,
            "over": spent[service] - budget,
        }
        for service, budget in budgets.items()
        if service in spent and spent[service] > budget
    ]
    return sorted(over, key=lambda item: item["over"], reverse=True)


def to_markdown(
    records: list,
    budgets: dict | None = None,
    month: str = "",
    prev_month: str = "",
    top_n: int = 5,
) -> str:
    lines = ["# Cost report", ""]
    lines.append(f"- Total spend: {total(records):,.2f}")
    lines.append(f"- Services: {len(by_service(records))}")
    lines.append("")
    lines.append("## Top spenders")
    lines.append("| Service | Spend | Share |")
    lines.append("| ------- | ----- | ----- |")
    for entry in top_spenders(records, top_n):
        lines.append(
            f"| {entry['service']} | {entry['amount']:,.2f} | {entry['share'] * 100:.1f}% |"
        )
    if month and prev_month:
        lines.append("")
        change = mom_change(records, month, prev_month)
        if change is None:
            lines.append(f"## Month over month\nNo data for {month} vs {prev_month}.")
        else:
            pct = (
                f"{change['pct'] * 100:+.1f}%"
                if change["pct"] is not None else "n/a (no prior spend)"
            )
            lines.append(
                f"## Month over month\n{month}: {change['current']:,.2f} "
                f"vs {prev_month}: {change['previous']:,.2f} "
                f"({change['delta']:+,.2f}, {pct})."
            )
    if budgets:
        lines.append("")
        over = over_budget(records, budgets)
        if over:
            lines.append("## Over budget")
            for entry in over:
                lines.append(
                    f"- {entry['service']}: spent {entry['spent']:,.2f} "
                    f"on a {entry['budget']:,.2f} budget "
                    f"(over by {entry['over']:,.2f})"
                )
        else:
            lines.append("All services within budget.")
    return "\n".join(lines) + "\n"


def records_from_json(data: list) -> list:
    return [
        CostRecord(
            service=item.get("service", "unnamed"),
            amount=float(item.get("amount", 0)),
            month=item.get("month", ""),
        )
        for item in data
    ]
