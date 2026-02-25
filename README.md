# Tariff Watch

**US HTS Weekly Tariff Monitor** — automatically fetches the latest USITC Harmonized Tariff Schedule, diffs against the prior week's snapshot, and produces Markdown/JSON reports. Includes a REST API and PostgreSQL storage for historical tracking.

---

## Features

- **Auto-discovers the latest USITC HTS revision** — no manual URL needed
- Detects tariff rate additions, removals, and changes week-over-week
- Filters to specific HTS prefixes (e.g. children's clothing: `6111`, `6209`)
- REST API: `/live/tariff/{code}` returns real-time rates with no database required
- PostgreSQL storage for historical snapshots and change tracking
- Federal Register notices fetched and stored
- Docker one-command deployment
- Weekly cron scheduler (Monday 09:00 UTC)
- Optional email notification via SMTP

---

## Quickstart (Docker — recommended)

```bash
git clone https://github.com/zhaoningliu1-lang/tariff-watch.git
cd tariff-watch
docker compose up --build -d
```

Three containers start automatically:

| Container | Port | Purpose |
|-----------|------|---------|
| `db` | 5432 | PostgreSQL — stores snapshots and change history |
| `api` | 8000 | FastAPI — REST endpoints for tariff queries |
| `scheduler` | — | Runs `tariff-watch run` every Monday 09:00 UTC |

Open **http://localhost:8000/docs** in your browser to see the interactive API.

---

## REST API

### Live tariff lookup (no database needed)

```
GET /live/tariff/{hts_code}
```

Always fetches directly from USITC. Works immediately on first startup.
Data is cached in memory for 1 hour.

```bash
curl http://localhost:8000/live/tariff/6111
curl http://localhost:8000/live/tariff/6111.20
```

### Database-backed endpoints

```
GET /tariff/{hts_code}          Current rates from DB (falls back to live)
GET /changes?since=YYYY-MM-DD   Rate change history
GET /notices                    Federal Register tariff notices
GET /health                     Service health check
```

### Example response: `/live/tariff/6111`

```json
[
  {
    "hts_code": "6111201000",
    "description": "Blouses and shirts, except those imported as parts of sets",
    "rate_general_raw": "19.7%",
    "rate_special_raw": null,
    "rate_column2_raw": null,
    "additional_duties_raw": null
  },
  ...
]
```

Dots and spaces in HTS codes are stripped automatically. A 4- or 6-digit prefix returns all matching rows.

---

## Local Development (without Docker)

### 1. Create virtual environment & install

```bash
cd tariff_watch
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configure

```bash
cp config.example.yaml config.yaml
# No manual URL needed — Tariff Watch auto-discovers the latest USITC CSV.
# Edit tracked_hts to the HTS prefixes you want to monitor.
```

### 3. Run (dry-run — no network or secrets needed)

```bash
python -m tariff_watch run --config config.yaml --dry-run
```

### 4. Run tests

```bash
pytest
```

---

## CLI Reference

### `run` — fetch, diff, report, store

```bash
tariff-watch run [OPTIONS]

Options:
  --config PATH                   Config file (default: config.yaml)
  --dry-run                       Use sample data; skip network and email
  --mode tracked_only|full_table  Override config mode
  --tracked-hts-file PATH         File with one HTS code per line
```

Results are automatically saved to PostgreSQL if the database is reachable.
If PostgreSQL is unavailable, the run completes normally and only CSV snapshots are saved.

### `lookup` — query current tariff rates

```bash
tariff-watch lookup --hts CODE [OPTIONS]

Options:
  --hts CODE     HTS code or prefix (dots optional). Comma-separate multiple:
                 --hts 6111,6209
  --config PATH  Config file (default: config.yaml)
  --json         Output JSON only

Examples:
  tariff-watch lookup --hts 6111.20.6010
  tariff-watch lookup --hts 6111,6209
  tariff-watch lookup --hts 6111 --json
```

---

## Configuration (`config.yaml`)

```yaml
mode: tracked_only          # tracked_only | full_table

tracked_hts:
  - "6111"                  # Babies' garments, knitted
  - "6209"                  # Babies' garments, woven
  - "6103"                  # Boys' suits, knitted
  - "6104"                  # Girls' suits, knitted

sources:
  # Leave as PLACEHOLDER — auto-discovery finds the latest USITC revision.
  usitc_hts_export_url: "PLACEHOLDER"

storage:
  snapshots_dir: snapshots
  reports_dir: reports
  retain_weeks: 12

notify_email:
  enabled: false
  smtp_host: "ENV:SMTP_HOST"
  smtp_port: 587
  smtp_user: "ENV:SMTP_USER"
  smtp_password: "ENV:SMTP_PASS"
  from_email: "ENV:FROM_EMAIL"
  to_emails:
    - "you@example.com"
```

---

## Output Files

| Path | Description |
|------|-------------|
| `snapshots/hts_snapshot_YYYYMMDD.csv` | Normalised HTS snapshot |
| `reports/report_YYYYMMDD.md` | Full Markdown weekly report |
| `reports/report_YYYYMMDD.json` | Structured JSON report |

---

## OpenClaw / Telegram Integration

Tariff Watch prints a Telegram-ready summary to stdout on each run. Use OpenClaw Gateway to post it automatically:

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

## Deploying to Railway (public API)

To make the API accessible from the internet:

1. Go to **https://railway.app** and create a free account
2. Click **New Project → Deploy from GitHub repo**
3. Select `zhaoningliu1-lang/tariff-watch`
4. Railway auto-detects the `Dockerfile` and deploys the API
5. Add a **PostgreSQL** plugin in the Railway dashboard
6. Set environment variables: `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` (Railway provides these automatically with the plugin)
7. Your API is live at `https://your-app.railway.app/live/tariff/6111`

---

## Disclaimer

For informational purposes only. Always verify tariff obligations with CBP binding rulings, a licensed customs broker, or trade counsel.
