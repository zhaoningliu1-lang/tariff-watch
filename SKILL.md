# SKILL: Tariff Watch

> ClawHub Skill · v0.1.0 · Python 3.11+

## Overview

Tariff Watch monitors the US Harmonized Tariff Schedule (HTS) published by the USITC. Each run downloads the configured HTS export, compares it to the previous snapshot, and produces structured reports. A Telegram-ready summary is printed to stdout for OpenClaw Gateway to forward to channels.

---

## Inputs

| Parameter | Where to set | Description |
|---|---|---|
| `tracked_hts` | `config.yaml` | List of 10-digit HTS codes to watch (`mode: tracked_only`) |
| `mode` | `config.yaml` or `--mode` flag | `tracked_only` (default) or `full_table` |
| `sources.usitc_hts_export_url` | `config.yaml` | Direct URL to USITC HTS CSV export (see README for how to obtain) |
| SMTP credentials | Environment variables | `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, `FROM_EMAIL` |
| `notify_email.enabled` | `config.yaml` | `true` to send email report |
| `notify_email.to_emails` | `config.yaml` | List of recipient email addresses |

---

## Outputs

| Output | Description |
|---|---|
| **stdout** | Telegram-ready text summary (≤20 lines): date, top 3 changes, report paths |
| `reports/report_YYYYMMDD.md` | Full Markdown weekly report |
| `reports/report_YYYYMMDD.json` | Structured JSON: meta + changes list |
| `snapshots/hts_snapshot_YYYYMMDD.csv` | Normalised HTS snapshot |
| Email (optional) | Markdown report as plain-text + HTML email via SMTP |

---

## How Telegram Delivery Works

This skill does **not** run a Telegram Bot. Instead:

1. The skill prints a concise summary to **stdout**.
2. **OpenClaw Gateway** captures stdout and posts it to your Telegram channel via the `--announce` flag.

Recommended cron command:

```bash
openclaw cron add \
  --name "Weekly Tariff Watch" \
  --cron "0 9 * * 1" \
  --tz "America/Los_Angeles" \
  --session isolated \
  --message "Run Tariff Watch skill in repo: execute \`python -m tariff_watch run --config config.yaml\` and announce stdout summary." \
  --announce \
  --channel telegram \
  --to "chat:<TELEGRAM_CHAT_ID_OR_TARGET>"
```

---

## Limitations & Disclaimer (V1 Scope)

- **Data source:** Relies on the user-supplied USITC HTS CSV export URL. If USITC changes its export format, column mapping may need updating.
- **Not included in V1:**
  - Section 301 (China) additional tariffs
  - Section 232 (Steel/Aluminium) additional tariffs
  - AD/CVD (Anti-Dumping / Countervailing Duty) orders
  - Complex GSP/FTA special rate parsing
  - HTS classification disputes
  - CBP binding rulings
- **For informational purposes only.** Always verify tariff obligations with CBP binding rulings, a licensed customs broker, or trade counsel.

---

## Planned Extensions (Future Versions)

- **V2:** Federal Register monitoring for Section 301/232 USTR notices.
- **V2:** AD/CVD lookup via CBP ADCVD database.
- **V3:** FTA special rate structured parsing (USMCA, KORUS, etc.).
- **V3:** Multi-source reconciliation (USITC + CBP ACE).
- **V4:** Web dashboard / API endpoint for real-time queries.

---

## Running Dry-Run (No Secrets Required)

```bash
python -m tariff_watch run --config config.yaml --dry-run
```

Uses bundled sample data. Safe to run in CI and for initial setup verification.
