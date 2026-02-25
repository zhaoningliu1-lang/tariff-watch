````skill
# SKILL: Tariff Watch

> ClawHub Skill · v2.0.0 · Python 3.11+

## Overview

Tariff Watch monitors the US Harmonized Tariff Schedule (HTS) published by the USITC.

**Key capability:** Answer questions about US import tariff rates by HTS code or product category. The skill automatically fetches the latest published rates directly from USITC — no manual URL configuration needed.

**Live data source:** `https://hts.usitc.gov/reststop/releaseList` — always points to the current HTS revision (e.g. 2026 Revision 3, containing 29,000+ rows).

---

## How to Query Tariff Rates (OpenClaw Usage)

To answer a user question like *"What is the tariff rate for children's cotton clothing from China?"*:

1. Identify the HTS chapter/prefix (e.g. `6111` = babies' knitted garments, `6209` = babies' woven garments)
2. Fetch live rates from USITC:

```python
from tariff_watch.sources_usitc import fetch_live_rates
rows = fetch_live_rates("6111")   # returns list of dicts
# Each dict has: hts_code, description, rate_general_raw, additional_duties_raw
```

3. Report `rate_general_raw` (MFN base rate) and `additional_duties_raw` (Section 301 surcharge if any).

### Common HTS Prefixes for Children's Clothing

| HTS Prefix | Description |
|---|---|
| `6111` | Babies' garments, knitted or crocheted |
| `6209` | Babies' garments, not knitted |
| `6103` | Boys' suits/jackets/trousers, knitted |
| `6104` | Girls' suits/dresses, knitted |
| `6203` | Men's/boys' suits/trousers, woven |
| `6204` | Women's/girls' suits/dresses, woven |

---

## Inputs

| Parameter | Where to set | Description |
|---|---|---|
| `tracked_hts` | `config.yaml` | HTS prefixes to monitor weekly (e.g. `6111`, `6209`) |
| `mode` | `config.yaml` | `tracked_only` (default) or `full_table` |
| `sources.usitc_hts_export_url` | `config.yaml` | Fallback URL only — auto-discovery handles this automatically |
| SMTP credentials | Environment variables | `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS`, `FROM_EMAIL` |

---

## Outputs

| Output | Description |
|---|---|
| **stdout** | Telegram-ready summary (<=20 lines): date, top changes |
| `reports/report_YYYYMMDD.md` | Full Markdown weekly report |
| `reports/report_YYYYMMDD.json` | Structured JSON: meta + changes list |
| `snapshots/hts_snapshot_YYYYMMDD.csv` | Normalised HTS snapshot |
| REST API | `/live/tariff/{hts_code}` for real-time queries |

---

## REST API Endpoints (when deployed)

| Endpoint | Description |
|---|---|
| `GET /live/tariff/{code}` | Live rates from USITC, no DB needed |
| `GET /tariff/{code}` | Rates from DB (falls back to live) |
| `GET /changes?since=YYYY-MM-DD` | Rate change history |
| `GET /notices` | Federal Register tariff notices |
| `GET /health` | Service health check |

---

## Weekly Cron (OpenClaw Gateway)

```bash
openclaw cron add \
  --name "Weekly Tariff Watch" \
  --cron "0 9 * * 1" \
  --tz "America/Los_Angeles" \
  --session isolated \
  --message "Run Tariff Watch: execute python -m tariff_watch run --config config.yaml and announce stdout summary." \
  --announce \
  --channel telegram \
  --to "chat:<TELEGRAM_CHAT_ID>"
```

---

## Disclaimer

For informational purposes only. Always verify tariff obligations with CBP binding rulings, a licensed customs broker, or trade counsel. Section 301 / Section 232 additional duties change frequently — confirm with the Federal Register.
````
