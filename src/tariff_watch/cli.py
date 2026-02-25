"""Command-line entry point for Tariff Watch."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tariff-watch",
        description="Fetch USITC HTS data, diff with previous snapshot, generate weekly report.",
    )
    sub = parser.add_subparsers(dest="command")

    # ── run ────────────────────────────────────────────────────────────────
    run_cmd = sub.add_parser("run", help="Execute the full fetch → diff → report pipeline.")
    run_cmd.add_argument("--config", default="config.yaml", help="Path to config.yaml (default: config.yaml)")
    run_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip network fetch and email; use sample data if available.",
    )
    run_cmd.add_argument(
        "--mode",
        choices=["tracked_only", "full_table"],
        default=None,
        help="Override config mode.",
    )
    run_cmd.add_argument(
        "--tracked-hts-file",
        default=None,
        help="Path to a file with one HTS code per line (overrides config tracked_hts).",
    )

    # ── lookup ─────────────────────────────────────────────────────────────
    lookup_cmd = sub.add_parser(
        "lookup",
        help="Look up current tariff rates for one or more HTS codes.",
    )
    lookup_cmd.add_argument(
        "--hts",
        required=True,
        metavar="CODE",
        help=(
            "HTS code to look up (dots optional, 6/8/10-digit prefix supported). "
            "Comma-separate multiple codes: --hts 0101210010,0102290000"
        ),
    )
    lookup_cmd.add_argument("--config", default="config.yaml", help="Path to config.yaml (default: config.yaml)")
    lookup_cmd.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        help="Output only machine-readable JSON (suppresses plain-text table).",
    )

    return parser


def _load_hts_file(path: str) -> list[str]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()]


# ---------------------------------------------------------------------------
# Sub-command implementations
# ---------------------------------------------------------------------------

def _cmd_run(args: argparse.Namespace) -> None:
    """Execute the full fetch → diff → report pipeline."""
    try:
        from .config import load_config, ConfigError
        cfg = load_config(args.config)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Configuration error: {exc}", file=sys.stderr)
        sys.exit(2)

    if args.mode:
        cfg.mode = args.mode
    if args.tracked_hts_file:
        try:
            cfg.tracked_hts = _load_hts_file(args.tracked_hts_file)
        except OSError as exc:
            print(f"[ERROR] Cannot read --tracked-hts-file: {exc}", file=sys.stderr)
            sys.exit(2)

    from .config import ConfigError
    from .http import NetworkError, ParseError
    from .normalize import normalize_dataframe
    from .snapshot import save_snapshot, find_previous_snapshot, load_snapshot, apply_retention
    from .diff import compute_diff
    from .report import write_reports
    from .email_notify import send_report_email

    import pandas as pd

    today = date.today()

    if args.dry_run:
        logger.info("Dry-run mode: loading sample data instead of fetching from network.")
        sample_dir = Path(__file__).parents[3] / "sample_data"
        current_csv = sample_dir / "hts_small_current.csv"
        prev_csv = sample_dir / "hts_small_prev.csv"

        if not current_csv.exists():
            print(
                "[ERROR] Dry-run requires sample_data/hts_small_current.csv — not found.",
                file=sys.stderr,
            )
            sys.exit(3)

        current_df = normalize_dataframe(pd.read_csv(current_csv, dtype=str))
        prev_df = normalize_dataframe(pd.read_csv(prev_csv, dtype=str)) if prev_csv.exists() else pd.DataFrame()
        source_url = cfg.sources.usitc_hts_export_url or "dry-run (sample data)"
    else:
        try:
            from .sources_usitc import fetch_hts_dataframe
            current_df = fetch_hts_dataframe(cfg)
        except ConfigError as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            sys.exit(2)
        except (NetworkError, ParseError) as exc:
            print(f"[ERROR] Data fetch failed: {exc}", file=sys.stderr)
            sys.exit(3)
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] Unexpected error during fetch: {exc}", file=sys.stderr)
            sys.exit(4)

        source_url = cfg.sources.usitc_hts_export_url

        try:
            save_snapshot(current_df, cfg.storage.snapshots_dir, today)
            apply_retention(cfg.storage.snapshots_dir, cfg.storage.retain_weeks)
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] Snapshot save failed: {exc}", file=sys.stderr)
            sys.exit(4)

        prev_path = find_previous_snapshot(cfg.storage.snapshots_dir, today)
        prev_df = load_snapshot(prev_path) if prev_path else pd.DataFrame()
        if prev_path:
            prev_df = normalize_dataframe(prev_df)

    try:
        changes = compute_diff(prev_df, current_df) if not prev_df.empty else []
        if prev_df.empty:
            logger.info("No previous snapshot found — skipping diff (first run).")
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Diff computation failed: {exc}", file=sys.stderr)
        sys.exit(4)

    try:
        md_path, json_path, telegram_summary = write_reports(
            changes=changes,
            reports_dir=cfg.storage.reports_dir,
            source_url=source_url,
            mode=cfg.mode,
            tracked_hts=cfg.tracked_hts,
            timezone_str=cfg.runtime.timezone,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Report generation failed: {exc}", file=sys.stderr)
        sys.exit(4)

    print(telegram_summary)

    # ── Persist to PostgreSQL (optional — skips gracefully if DB not available) ──
    if not args.dry_run:
        try:
            from .db import init_pool, apply_schema, upsert_snapshots, insert_changes
            init_pool()
            apply_schema()
            rows = current_df.to_dict(orient="records")
            saved = upsert_snapshots(rows, today.isoformat())
            logger.info("DB: upserted %d snapshot rows for %s", saved, today)
            if changes:
                change_rows = [
                    {
                        "hts_code": c.get("hts_code", ""),
                        "description": c.get("description"),
                        "change_type": c.get("change_type", "rate_changed"),
                        "field_changed": c.get("field", None),
                        "old_value": str(c.get("old_value", "")) if c.get("old_value") is not None else None,
                        "new_value": str(c.get("new_value", "")) if c.get("new_value") is not None else None,
                    }
                    for c in changes
                ]
                insert_changes(change_rows, today.isoformat())
                logger.info("DB: inserted %d change records", len(change_rows))
        except Exception as db_exc:  # noqa: BLE001
            logger.warning("DB sync skipped (PostgreSQL not available): %s", db_exc)

    # ── Fetch Federal Register notices (optional) ──────────────────────────────
    if not args.dry_run:
        try:
            from .sources_fedregister import fetch_notices
            from .db import upsert_notices
            notices = fetch_notices()
            if notices:
                upsert_notices(notices)
                logger.info("Federal Register: stored %d notice(s)", len(notices))
        except Exception as fr_exc:  # noqa: BLE001
            logger.warning("Federal Register fetch skipped: %s", fr_exc)

    if cfg.notify_email.enabled and not args.dry_run:
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        ok = send_report_email(
            cfg=cfg.notify_email,
            subject_suffix=f"Weekly Update {date_str}",
            md_path=md_path,
            dry_run=False,
        )
        if not ok:
            print("[WARNING] email failed — see logs for details.")


def _cmd_lookup(args: argparse.Namespace) -> None:
    """Look up current tariff rates for one or more HTS codes."""
    from .config import load_config, ConfigError
    from .http import NetworkError, ParseError
    from .normalize import normalize_hts_code
    from .sources_usitc import fetch_hts_dataframe, filter_tracked_hts

    # Parse comma-separated codes
    raw_codes = [c.strip() for c in args.hts.split(",") if c.strip()]
    if not raw_codes:
        print("[ERROR] --hts requires at least one HTS code.", file=sys.stderr)
        sys.exit(2)

    norm_codes = [normalize_hts_code(c) for c in raw_codes]
    invalid = [raw_codes[i] for i, n in enumerate(norm_codes) if not n]
    if invalid:
        print(f"[ERROR] Invalid HTS code(s): {', '.join(invalid)}", file=sys.stderr)
        sys.exit(2)

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"[ERROR] Configuration error: {exc}", file=sys.stderr)
        sys.exit(2)

    # Always fetch full table for lookup — ignore config mode
    cfg.mode = "full_table"

    try:
        df = fetch_hts_dataframe(cfg)
    except ConfigError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(2)
    except (NetworkError, ParseError) as exc:
        print(f"[ERROR] Data fetch failed: {exc}", file=sys.stderr)
        sys.exit(3)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Unexpected error during fetch: {exc}", file=sys.stderr)
        sys.exit(4)

    # Filter to requested codes using prefix matching
    results = filter_tracked_hts(df, raw_codes)

    if results.empty:
        print(f"No HTS rows found matching: {', '.join(raw_codes)}", file=sys.stderr)
        sys.exit(1)

    # ── Build output payload ────────────────────────────────────────────────
    rate_cols = ["rate_general_raw", "rate_special_raw", "rate_column2_raw"]
    # Include parsed value columns if present
    value_cols = [c.replace("_raw", "_value") for c in rate_cols if c.replace("_raw", "_value") in results.columns]
    display_cols = ["hts_code", "description"] + rate_cols + value_cols

    records = results[[c for c in display_cols if c in results.columns]].to_dict(orient="records")

    if args.output_json:
        print(json.dumps(records, indent=2, ensure_ascii=False))
        return

    # ── Plain-text table ────────────────────────────────────────────────────
    SEP = "-" * 80
    print(SEP)
    print(f"  HTS Lookup  •  {len(records)} result(s) for: {', '.join(raw_codes)}")
    print(SEP)
    for rec in records:
        print(f"  HTS Code    : {rec.get('hts_code', 'N/A')}")
        print(f"  Description : {rec.get('description', 'N/A')}")
        print(f"  General Rate: {rec.get('rate_general_raw', 'N/A')}"
              + (f"  ({rec['rate_general_value']}%)" if 'rate_general_value' in rec and rec['rate_general_value'] is not None else ""))
        print(f"  Special Rate: {rec.get('rate_special_raw', 'N/A')}")
        print(f"  Column 2    : {rec.get('rate_column2_raw', 'N/A')}")
        print(SEP)

    # Machine-readable JSON always appended after the table for piping
    print()
    print("JSON:")
    print(json.dumps(records, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        _cmd_run(args)
    elif args.command == "lookup":
        _cmd_lookup(args)
    else:
        parser.print_help()
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
