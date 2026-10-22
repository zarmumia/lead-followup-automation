"""Load leads from a CRM CSV export. Column names are mapped in one place."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .rules import Lead, Status

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


def _dt(value: str) -> datetime | None:
    value = (value or "").strip()
    return datetime.fromisoformat(value) if value else None


def load_csv(path: str | Path) -> list[Lead]:
    leads = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            g = lambda k: row.get(COLUMNS[k], "")
            leads.append(
                Lead(
                    id=g("id"),
                    name=g("name"),
                    phone=g("phone"),
                    source=g("source"),
                    owner=g("owner").strip() or None,
                    status=Status(g("status").strip()),
                    created_at=_dt(g("created_at")),
                    last_contact_at=_dt(g("last_contact_at")),
                    callback_at=_dt(g("callback_at")),
                    reminders_sent=int(g("reminders_sent") or 0),
                )
            )
    return leads


def mask_phone(phone: str) -> str:
    """Privacy: never print full phone numbers in reports or logs."""
    digits = "".join(ch for ch in phone if ch.isdigit())
    return f"***-***{digits[-4:]}" if len(digits) >= 4 else "***"
