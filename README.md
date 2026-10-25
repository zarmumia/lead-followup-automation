# Lead Follow-Up Automation

**Make sure no lead falls through the cracks.**

> **About this repo:** a working demo from the [Zarmumia](https://zarmumia.co.il) portfolio. It shows the approach, not a finished product: rules a business owner can read, privacy first, and building on the tools a business already has. In client work it is adapted to the specific CRM and processes.


Small service businesses lose more money to slow follow-up than to bad marketing: a callback is promised and never made, a new inquiry waits a day for a first call, a client is "still missing two documents" for weeks. This tool reads a CRM export and turns it into a clear plan for today.

## What it does

| Rule | Who gets notified |
|---|---|
| New lead with no owner | Manager |
| No first contact within the SLA (default 2 hours) | Rep + manager |
| Promised callback is due today | Rep |
| Promised callback missed by more than 24 hours | Rep + manager |
| Conversation went quiet (default 3 days) | Rep |
| Client missing documents | Client gets a polite reminder |
| Documents still missing after 3 reminders | Rep takes over by phone |

The output:

- **A prioritized call list for each rep** (P1 = do it first).
- **A short digest for the manager** with only what needs escalation.
- **Ready-to-send client reminders**, using templates you can edit.

```
Call list – Rep A (2)
  P1 · Yossi Peretz (***-***5566) · Promised callback was missed
  P1 · Avi Cohen (***-***3344) · No first contact within SLA

Needs your attention today:
  • 2 × No first contact within SLA
  • 1 × Promised callback was missed
```

## Quick start

```bash
python -m lead_followup sample_data/leads.csv --now 2026-10-20T12:00
```

No dependencies beyond Python 3.10+. To send the results to Make, Zapier, n8n or your CRM, add `--webhook https://your-hook-url`. The payload contains the call lists, the manager digest and the client messages.

## Connecting to a real CRM

1. Export leads to CSV, or schedule the export.
2. Map your column names in `lead_followup/crm_io.py` (`COLUMNS`).
3. Adjust the thresholds in `rules.py` (`Config`) to match how your business works.
4. Run it every morning, either from a scheduler or as a step in your automation tool.

## Design principles

- **Use what the client already has.** Many CRMs include automations the team never switched on. This logic can run inside them, or next to them.
- **Privacy by default.** Phone numbers are masked in every report and log. Only the client-message payload carries the full number, because that's needed to send it.
- **Readable rules.** A business owner should be able to read `rules.py` and agree with it.

## Tests

```bash
pip install pytest && pytest
```

---

Built by **Fanny Rabinovitch · Zarmumia**: operations, automation and AI workflows for small and growing businesses.
