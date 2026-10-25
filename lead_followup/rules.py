"""Follow-up rules: decide which leads need attention right now.

The rules are deliberately simple and readable so a business owner can
review them. All thresholds live in one config object.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum


class Status(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    CALLBACK = "callback"          # rep promised to call back
    WAITING_DOCS = "waiting_docs"
    SIGNED = "signed"
    CLOSED_LOST = "closed_lost"


OPEN_STATUSES = {Status.NEW, Status.CONTACTED, Status.CALLBACK, Status.WAITING_DOCS}


@dataclass
class Lead:
    id: str
    name: str
    phone: str
    source: str
    owner: str | None
    status: Status
    created_at: datetime
    last_contact_at: datetime | None = None
    callback_at: datetime | None = None
    reminders_sent: int = 0


@dataclass
class Config:
    # A brand-new lead should get a first call within this window.
    first_contact_sla: timedelta = timedelta(hours=2)
    # A lead in conversation that has gone quiet.
    stale_after: timedelta = timedelta(days=3)
    # Documents requested but not received.
    docs_reminder_every: timedelta = timedelta(days=4)
    max_doc_reminders: int = 3
    # Business hours for the daily call list.
    workday_start_hour: int = 9
    workday_end_hour: int = 18


class Reason(str, Enum):
    UNASSIGNED = "Unassigned lead"
    FIRST_CONTACT_OVERDUE = "No first contact within SLA"
    CALLBACK_DUE = "Promised callback is due"
    CALLBACK_MISSED = "Promised callback was missed"
    STALE = "Conversation went quiet"
    DOCS_REMINDER = "Client still missing documents"
    DOCS_ESCALATE = "Documents still missing after max reminders"


@dataclass
class Action:
    lead: Lead
    reason: Reason
    priority: int                  # 1 = most urgent
    notify: list[str] = field(default_factory=list)  # who to alert: "rep", "manager", "client"

    @property
    def assignee(self) -> str:
        return self.lead.owner or "unassigned"


def _require_aware(name: str, value: datetime | None) -> None:
    if value is not None and value.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware (got naive {value.isoformat()})")


def evaluate(lead: Lead, now: datetime, cfg: Config | None = None) -> list[Action]:
    """Return every action this lead needs at `now`. Empty list = all good.

    All datetimes must be timezone-aware, so leads exported from a CRM in one
    timezone are never compared against a clock in another.
    """
    cfg = cfg or Config()
    _require_aware("now", now)
    for field_name in ("created_at", "last_contact_at", "callback_at"):
        _require_aware(f"lead {lead.id}: {field_name}", getattr(lead, field_name))
    if lead.status not in OPEN_STATUSES:
        return []

    actions: list[Action] = []

    if lead.owner is None:
        actions.append(Action(lead, Reason.UNASSIGNED, 1, ["manager"]))

    if lead.status == Status.NEW and lead.last_contact_at is None:
        if now - lead.created_at > cfg.first_contact_sla:
            actions.append(Action(lead, Reason.FIRST_CONTACT_OVERDUE, 1, ["rep", "manager"]))

    if lead.status == Status.CALLBACK and lead.callback_at is not None:
        if now - lead.callback_at > timedelta(hours=24):
            actions.append(Action(lead, Reason.CALLBACK_MISSED, 1, ["rep", "manager"]))
        elif lead.callback_at <= now:
            actions.append(Action(lead, Reason.CALLBACK_DUE, 2, ["rep"]))

    if lead.status in {Status.CONTACTED, Status.CALLBACK} and lead.last_contact_at:
        if now - lead.last_contact_at > cfg.stale_after and not any(
            a.reason in {Reason.CALLBACK_DUE, Reason.CALLBACK_MISSED} for a in actions
        ):
            actions.append(Action(lead, Reason.STALE, 3, ["rep"]))

    if lead.status == Status.WAITING_DOCS:
        last = lead.last_contact_at or lead.created_at
        if now - last > cfg.docs_reminder_every:
            if lead.reminders_sent >= cfg.max_doc_reminders:
                actions.append(Action(lead, Reason.DOCS_ESCALATE, 2, ["rep"]))
            else:
                actions.append(Action(lead, Reason.DOCS_REMINDER, 3, ["client"]))

    return actions


def evaluate_all(leads: list[Lead], now: datetime, cfg: Config | None = None) -> list[Action]:
    cfg = cfg or Config()
    actions = [a for lead in leads for a in evaluate(lead, now, cfg)]
    return sorted(actions, key=lambda a: (a.priority, a.lead.created_at))
