# Tariff Watch

**US HTS Weekly Tariff Monitor** — downloads USITC HTS export data, diffs against prior snapshots, and produces Markdown/JSON reports with a Telegram-ready stdout summary.

---

## Quickstart

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
# Edit config.yaml — at minimum set sources.usitc_hts_export_url
```

### 3. Run (dry-run — no secrets needed)

```bash
python -m tariff_watch run --config config.yaml --dry-run
```

Dry-run loads `sample_data/hts_small_current.csv` and `sample_data/hts_small_prev.csv` instead of fetching from the network. Reports are written to `reports/`.

### 4. Run tests

```bash
pytest
```

---

## Obtaining the USITC HTS Export URL

Tariff Watch does **not** hardcode any USITC URL because export URLs change over time.

**Steps to get a valid CSV export link:**

1. Go to **https://hts.usitc.gov/**
2. Look for an **"Export"**, **"Download"**, or **"Open Data"** button/link, typically in the page header or footer.
3. Choose **CSV** format and start the download. Copy the direct download URL from your browser (check the network tab or the link href).
4. Paste it into `config.yaml` under `sources.usitc_hts_export_url`.

> The USITC also publishes structured data via **https://www.usitc.gov/tata/hts/** and there may be an API at **https://hts.usitc.gov/api**. Check the site for current export options.

> **Performance note:** Full-table mode downloads and processes the entire HTS schedule (~10,000+ rows). Set `mode: tracked_only` with a focused `tracked_hts` list for faster, cheaper runs.

> **HTS code format:** Supply **10-digit** numeric codes (e.g. `8471300000`). The normaliser strips dots and spaces but does not zero-pad codes of unexpected length.

---

## Email Configuration

Set `notify_email.enabled: true` in `config.yaml` and export these environment variables before running:

```bash
export SMTP_HOST="smtp.example.com"
export SMTP_USER="you@example.com"
export SMTP_PASS="yourpassword"
export FROM_EMAIL="tariffwatch@example.com"
```

Email uses **STARTTLS on port 587**. HTML rendering wraps the Markdown in `<pre>` for broad compatibility. To get richer HTML, install the `markdown` package and update `email_notify._markdown_to_html()`.

Email failures are logged as warnings and **do not affect the exit code** (exit 0 is still returned, but `[WARNING] email failed` is printed to stdout).

---

## Output Files

| Path | Description |
|---|---|
| `snapshots/hts_snapshot_YYYYMMDD.csv` | Raw normalised snapshot (retained for `retain_weeks * 2` runs) |
| `reports/report_YYYYMMDD.md` | Markdown weekly report |
| `reports/report_YYYYMMDD.json` | Structured JSON report |

---

## CLI Reference

### `run` — fetch, diff, report

```bash
python -m tariff_watch run [OPTIONS]
# or, after pip install -e .:
tariff-watch run [OPTIONS]

Options:
  --config PATH                   Config file path (default: config.yaml)
  --dry-run                       Use sample data; skip network and email
  --mode tracked_only|full_table  Override config mode
  --tracked-hts-file PATH         File with one HTS code per line
```

### `lookup` — query current tariff rates for any HTS code

```bash
python -m tariff_watch lookup --hts CODE [OPTIONS]

Options:
  --hts CODE       HTS code to look up. Dots optional, 6/8/10-digit prefix
                   supported. Comma-separate multiple codes:
                   --hts 0101210010,0102290000
  --config PATH    Config file path (default: config.yaml)
  --json           Output machine-readable JSON only (suppresses table)

Examples:
  tariff-watch lookup --hts 6111.20.6010
  tariff-watch lookup --hts 6111,6209
  tariff-watch lookup --hts 8471.30.0100 --json
```

**Exit codes:**

| Code | Meaning |
|---|---|
| 0 | Success |
| 2 | Configuration error |
| 3 | Network / data error |
| 4 | Runtime exception |

---

## OpenClaw Cron Integration (Telegram channel)

Tariff Watch does **not** implement a Telegram Bot internally. Telegram delivery is handled by **OpenClaw Gateway's `--announce` flag**, which captures stdout and posts it to your connected Telegram channel.

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

Replace `<TELEGRAM_CHAT_ID_OR_TARGET>` with your OpenClaw Telegram target (channel ID, username, etc.). The skill only prints the summary to stdout — OpenClaw handles the rest.
