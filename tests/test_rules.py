import io
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lead_followup import notify
from lead_followup.crm_io import DEFAULT_TZ, load_csv, load_csv_with_issues, mask_phone, parse_dt
from lead_followup.notify import client_messages, daily_call_lists, manager_digest, post_webhook
from lead_followup.rules import Config, Lead, Reason, Status, evaluate, evaluate_all

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=DEFAULT_TZ)


def lead(**kw):
    base = dict(id="x", name="Test Person", phone="050-0000000", source="web",
                owner="Rep A", status=Status.NEW, created_at=NOW - timedelta(hours=1))
    base.update(kw)
    return Lead(**base)


def reasons(item):
    return {a.reason for a in evaluate(item, NOW)}


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
    waiting = dict(status=Status.WAITING_DOCS, last_contact_at=old)
    assert reasons(lead(**waiting, reminders_sent=1)) == {Reason.DOCS_REMINDER}
    assert reasons(lead(**waiting, reminders_sent=3)) == {Reason.DOCS_ESCALATE}


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


def test_naive_datetimes_are_rejected():
    with pytest.raises(ValueError):
        evaluate(lead(), datetime(2026, 10, 20, 12, 0))


def test_csv_times_get_business_timezone():
    assert parse_dt("2026-10-20T08:15:00").tzinfo == DEFAULT_TZ
    assert parse_dt("2026-10-20T08:15:00+00:00").tzinfo == timezone.utc


def test_timezones_compare_correctly():
    # 08:30 UTC is 11:30 in Israel (IDT, UTC+3): 30 minutes before NOW, so no action is due yet.
    created = datetime(2026, 10, 20, 8, 30, tzinfo=timezone.utc)
    assert reasons(lead(created_at=created)) == set()


def test_default_config_is_not_shared():
    a = evaluate(lead(created_at=NOW - timedelta(hours=3)), NOW)
    b = evaluate(lead(created_at=NOW - timedelta(hours=3)), NOW, Config(first_contact_sla=timedelta(hours=5)))
    assert a and not b
    assert Config().first_contact_sla == timedelta(hours=2)


def test_bad_rows_are_reported_not_swallowed(tmp_path):
    f = tmp_path / "leads.csv"
    f.write_text(
        "id,name,phone,source,owner,status,created_at,last_contact_at,callback_at,reminders_sent\n"
        "A,Ok Lead,050-1,web,Rep A,new,2026-10-20T08:00:00,,,0\n"
        "B,Bad Status,050-2,web,Rep A,maybe,2026-10-20T08:00:00,,,0\n"
        "C,No Date,050-3,web,Rep A,new,,,,0\n"
        "D,Bad Date,050-4,web,Rep A,new,20/10/2026,,,0\n",
        encoding="utf-8",
    )
    leads, issues = load_csv_with_issues(f)
    assert [x.id for x in leads] == ["A"]
    assert [i.lead_id for i in issues] == ["B", "C", "D"]
    assert "missing created_at" in issues[1].problem


class _Resp(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_webhook_retries_transient_errors(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout):
        calls.append(1)
        if len(calls) < 3:
            raise urllib.error.HTTPError(req.full_url, 503, "busy", {}, None)
        return _Resp(b"ok")

    monkeypatch.setattr(notify.urllib.request, "urlopen", fake_urlopen)
    assert post_webhook("https://example.test/hook", {"a": 1}, sleep=lambda s: None) == 200
    assert len(calls) == 3


def test_webhook_does_not_retry_client_errors(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout):
        calls.append(1)
        raise urllib.error.HTTPError(req.full_url, 400, "bad", {}, None)

    monkeypatch.setattr(notify.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(urllib.error.HTTPError):
        post_webhook("https://example.test/hook", {}, sleep=lambda s: None)
    assert len(calls) == 1
