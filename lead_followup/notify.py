"""Turn actions into messages: a daily call list per rep, a manager digest,
and client reminder texts. Delivery is pluggable (console, webhook)."""
from __future__ import annotations

import json
import urllib.request
from collections import defaultdict

from .crm_io import mask_phone
from .rules import Action, Reason

CLIENT_TEMPLATES = {
    Reason.DOCS_REMINDER: (
        "Hi {first_name}, a quick reminder: we're still missing a few documents "
        "to move your case forward. Reply here and we'll tell you exactly what's needed."
    ),
}


def daily_call_lists(actions: list[Action]) -> dict[str, list[str]]:
    """One prioritized list per rep. Each line is something to do today."""
    lists: dict[str, list[str]] = defaultdict(list)
    for a in actions:
        if "rep" in a.notify:
            lists[a.assignee].append(
                f"P{a.priority} · {a.lead.name} ({mask_phone(a.lead.phone)}) · {a.reason.value}"
            )
    return dict(lists)


def manager_digest(actions: list[Action]) -> str:
    flagged = [a for a in actions if "manager" in a.notify]
    if not flagged:
        return "All clear: no leads need escalation."
    counts: dict[str, int] = defaultdict(int)
    for a in flagged:
        counts[a.reason.value] += 1
    lines = [f"{n} × {reason}" for reason, n in sorted(counts.items(), key=lambda x: -x[1])]
    return "Needs your attention today:\n" + "\n".join(f"  • {l}" for l in lines)


def client_messages(actions: list[Action]) -> list[dict]:
    out = []
    for a in actions:
        if "client" in a.notify and a.reason in CLIENT_TEMPLATES:
            out.append({
                "lead_id": a.lead.id,
                "to": a.lead.phone,
                "text": CLIENT_TEMPLATES[a.reason].format(first_name=a.lead.name.split()[0]),
            })
    return out


def post_webhook(url: str, payload: dict) -> int:
    """Send to any automation tool that accepts a webhook (Make, Zapier, n8n, a CRM)."""
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status
