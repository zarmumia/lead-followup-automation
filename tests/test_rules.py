from datetime import datetime, timedelta
from pathlib import Path

from lead_followup.crm_io import load_csv, mask_phone
from lead_followup.notify import client_messages, daily_call_lists, manager_digest
from lead_followup.rules import Lead, Reason, Status, evaluate, evaluate_all

NOW = datetime(2026, 10, 20, 12, 0)


def lead(**kw):
    base = dict(id="x", name="Test Person", phone="050-0000000", source="web",
                owner="Rep A", status=Status.NEW, created_at=NOW - timedelta(hours=1))
    base.update(kw)
    return Lead(**base)


def reasons(l):
    return {a.reason for a in evaluate(l, NOW)}


def test_fresh_lead_needs_nothing():
    assert reasons(lead()) == set()


def test_first_contact_overdue():
    assert Reason.FIRST_CONTACT_OVERDUE in reasons(lead(created_at=NOW - timedelta(hours=3)))


def test_unassigned_goes_to_manager():
    acts = evaluate(lead(owner=None), NOW)
    assert acts[0].reason == Reason.UNASSIGNED and "manager" in acts[0].notify


def test_callback_due_vs_missed():
    due = lead(status=Status.CALLBACK, callback_at=NOW - timedelta(hours=1),
               last_contact_at=NOW - timedelta(days=1))
    missed = lead(status=Status.CALLBACK, callback_at=NOW - timedelta(days=2),
                  last_contact_at=NOW - timedelta(days=5))
    assert reasons(due) == {Reason.CALLBACK_DUE}
    assert reasons(missed) == {Reason.CALLBACK_MISSED}  # not also flagged as stale


def test_stale_conversation():
    assert reasons(lead(status=Status.CONTACTED, last_contact_at=NOW - timedelta(days=4))) == {Reason.STALE}


def test_docs_reminder_then_escalation():
    old = NOW - timedelta(days=5)
    assert reasons(lead(status=Status.WAITING_DOCS, last_contact_at=old, reminders_sent=1)) == {Reason.DOCS_REMINDER}
    assert reasons(lead(status=Status.WAITING_DOCS, last_contact_at=old, reminders_sent=3)) == {Reason.DOCS_ESCALATE}


def test_closed_leads_ignored():
    assert reasons(lead(status=Status.SIGNED, created_at=NOW - timedelta(days=30))) == set()


def test_sample_file_end_to_end():
    leads = load_csv(Path(__file__).parent.parent / "sample_data" / "leads.csv")
    actions = evaluate_all(leads, NOW)
    assert actions[0].priority == 1
    lists = daily_call_lists(actions)
    assert "Rep A" in lists and all("***" in line for line in lists["Rep A"])
    assert "Needs your attention" in manager_digest(actions)
    msgs = client_messages(actions)
    assert len(msgs) == 1 and msgs[0]["text"].startswith("Hi Eli")


def test_phone_masking():
    assert mask_phone("050-123-4567") == "***-***4567"
