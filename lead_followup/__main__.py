"""CLI: python -m lead_followup sample_data/leads.csv [--now ISO] [--webhook URL]"""
from __future__ import annotations

import argparse
from datetime import datetime

from .crm_io import DEFAULT_TZ, load_csv_with_issues, parse_dt
from .notify import client_messages, daily_call_lists, manager_digest, post_webhook
from .rules import evaluate_all


def main() -> None:
    p = argparse.ArgumentParser(description="Find leads that need follow-up today.")
    p.add_argument("csv", help="CRM export (CSV)")
    p.add_argument("--now", help="Evaluate as of this time (ISO). Default: now.")
    p.add_argument("--webhook", help="POST the results to this URL instead of only printing")
    args = p.parse_args()

    now = parse_dt(args.now) if args.now else None
    now = now or datetime.now(DEFAULT_TZ)
    leads, issues = load_csv_with_issues(args.csv)
    actions = evaluate_all(leads, now)

    lists = daily_call_lists(actions)
    digest = manager_digest(actions)
    clients = client_messages(actions)

    print(f"Follow-up report · {now:%Y-%m-%d %H:%M}\n")
    for rep, items in lists.items():
        print(f"Call list – {rep} ({len(items)})")
        for line in items:
            print(f"  {line}")
        print()
    print(digest, "\n")
    print(f"{len(clients)} client reminder(s) ready to send.")
    if issues:
        print(f"\n{len(issues)} row(s) skipped – fix these in the CRM:")
        for i in issues:
            print(f"  line {i.line} · {i.lead_id}: {i.problem}")

    if args.webhook:
        status = post_webhook(args.webhook, {
            "generated_at": now.isoformat(),
            "call_lists": lists,
            "manager_digest": digest,
            "client_messages": clients,
            "skipped_rows": [i.__dict__ for i in issues],
        })
        print(f"Webhook responded {status}")


if __name__ == "__main__":
    main()
