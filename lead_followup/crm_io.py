"""Load leads from a CRM CSV export. Column names are mapped in one place.

Rows that can't be trusted (unknown status, missing or malformed dates) are
not silently dropped or guessed: they are skipped and reported back, so the
data problem gets fixed at the source.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .rules import Lead, Status

# Timestamps in most CRM exports carry no offset; they are in the business's local time.
DEFAULT_TZ = ZoneInfo("Asia/Jerusalem")

# Map your CRM's export headers to the fields we need.
COLUMNS = {
    "id": "id",
    "name": "name",
    "phone": "phone",
    "source": "source",
    "owner": "owner",
    "status": "status",
    "created_at": "created_at",
    "last_contact_at": "last_contact_at",
    "callback_at": "callback_at",
    "reminders_sent": "reminders_sent",
}


@dataclass
class RowIssue:
    line: int
    lead_id: str
    problem: str


def parse_dt(value: str | None, tz: ZoneInfo = DEFAULT_TZ) -> datetime | None:
    """Parse an ISO timestamp; naive values are interpreted in the business timezone."""
    value = (value or "").strip()
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=tz)


def load_csv_with_issues(path: str | Path, tz: ZoneInfo = DEFAULT_TZ) -> tuple[list[Lead], list[RowIssue]]:
    leads: list[Lead] = []
    issues: list[RowIssue] = []
    with open(path, newline="", encoding="utf-8") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            def g(key: str, row: dict[str, str] = row) -> str:
                return (row.get(COLUMNS[key]) or "").strip()

            lead_id = g("id") or f"(line {line})"
            try:
                created = parse_dt(g("created_at"), tz)
                if created is None:
                    raise ValueError("missing created_at")
                leads.append(
                    Lead(
                        id=lead_id,
                        name=g("name"),
                        phone=g("phone"),
                        source=g("source"),
                        owner=g("owner") or None,
                        status=Status(g("status")),
                        created_at=created,
                        last_contact_at=parse_dt(g("last_contact_at"), tz),
                        callback_at=parse_dt(g("callback_at"), tz),
                        reminders_sent=int(g("reminders_sent") or 0),
                    )
                )
            except ValueError as e:
                issues.append(RowIssue(line, lead_id, str(e)))
    return leads, issues


def load_csv(path: str | Path, tz: ZoneInfo = DEFAULT_TZ) -> list[Lead]:
    """Convenience wrapper: valid leads only. Use load_csv_with_issues to see what was skipped."""
    return load_csv_with_issues(path, tz)[0]


def mask_phone(phone: str) -> str:
    """Privacy: never print full phone numbers in reports or logs."""
    digits = "".join(ch for ch in phone if ch.isdigit())
    return f"***-***{digits[-4:]}" if len(digits) >= 4 else "***"
