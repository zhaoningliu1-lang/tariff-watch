"""
Background data scheduler — refreshes FX rates, shipping rates, and
USITC tariff data on configurable intervals.

Uses APScheduler BackgroundScheduler to run jobs in background threads.
Each job is wrapped in try/except so one failure doesn't affect others.

Schedule:
  - FX rates:       daily at 07:00 UTC (after ECB publishes)
  - Shipping rates:  daily at 07:05 UTC
  - USITC tariffs:   weekly Monday 09:00 UTC
  - Backfill:        once on first startup

Usage::

    from .scheduler import start_scheduler, stop_scheduler

    sched = start_scheduler()   # call in FastAPI startup
    stop_scheduler(sched)       # call in FastAPI shutdown
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


# ── Job functions (each wrapped in try/except) ───────────────────────────────

def _job_refresh_fx() -> None:
    """Refresh FX rates from ECB / premium API."""
    try:
        from .sources_fx import refresh_fx_rates
        rates = refresh_fx_rates()
        logger.info("Scheduler: FX refresh completed — %d currencies", len(rates))
    except Exception as e:
        logger.error("Scheduler: FX refresh failed — %s", e, exc_info=True)


def _job_refresh_shipping() -> None:
    """Refresh shipping rates (simulated or Freightos)."""
    try:
        from .sources_shipping import refresh_shipping_rates
        count = refresh_shipping_rates()
        logger.info("Scheduler: Shipping refresh completed — %d routes", count)
    except Exception as e:
        logger.error("Scheduler: Shipping refresh failed — %s", e, exc_info=True)


def _job_backfill_if_needed() -> None:
    """Run once on first startup: backfill 30 days of FX + shipping history."""
    try:
        from . import data_store
        data_store.init_db()

        # FX backfill
        if data_store.get_meta("fx_backfilled") != "true":
            logger.info("Scheduler: Starting FX history backfill (30 days)...")
            from .sources_fx import refresh_fx_history_backfill
            count = refresh_fx_history_backfill(days=30)
            logger.info("Scheduler: FX backfill complete — %d rows", count)
        else:
            logger.info("Scheduler: FX already backfilled, skipping")

        # Shipping backfill
        if data_store.get_meta("shipping_backfilled") != "true":
            logger.info("Scheduler: Starting shipping history backfill (30 days)...")
            from .sources_shipping import refresh_shipping_history_backfill
            count = refresh_shipping_history_backfill(days=30)
            logger.info("Scheduler: Shipping backfill complete — %d rows", count)
        else:
            logger.info("Scheduler: Shipping already backfilled, skipping")

    except Exception as e:
        logger.error("Scheduler: Backfill failed — %s", e, exc_info=True)


# ── Scheduler lifecycle ──────────────────────────────────────────────────────

def create_scheduler() -> BackgroundScheduler:
    """Create and configure the background scheduler."""
    scheduler = BackgroundScheduler(
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 3600,
        }
    )

    # Daily FX refresh (07:00 UTC = after ECB publishes at ~16:00 CET)
    scheduler.add_job(
        _job_refresh_fx,
        IntervalTrigger(hours=24),
        id="fx_refresh",
        name="Daily FX rate refresh",
        next_run_time=datetime.now() + timedelta(seconds=15),  # run shortly after startup
    )

    # Daily shipping refresh (07:05 UTC, offset to avoid collision)
    scheduler.add_job(
        _job_refresh_shipping,
        IntervalTrigger(hours=24),
        id="shipping_refresh",
        name="Daily shipping rate refresh",
        next_run_time=datetime.now() + timedelta(seconds=20),
    )

    # Weekly USITC tariff refresh (Monday 09:00 UTC)
    # Note: USITC refresh uses existing db.py infrastructure (PostgreSQL)
    # Only enabled if PostgreSQL is configured
    try:
        from .db import get_conn
        scheduler.add_job(
            _job_refresh_usitc,
            CronTrigger(day_of_week="mon", hour=9),
            id="usitc_refresh",
            name="Weekly USITC tariff refresh",
        )
    except Exception:
        logger.info("Scheduler: PostgreSQL not configured, skipping USITC weekly refresh")

    return scheduler


def _job_refresh_usitc() -> None:
    """Refresh USITC tariff data (weekly)."""
    try:
        from .sources_usitc import fetch_hts_dataframe
        from .db import upsert_snapshots
        from datetime import date as dt_date

        df = fetch_hts_dataframe()
        if df is not None and not df.empty:
            rows = df.to_dict("records")
            count = upsert_snapshots(rows, dt_date.today().isoformat())
            logger.info("Scheduler: USITC refresh completed — %d rows", count)
    except Exception as e:
        logger.error("Scheduler: USITC refresh failed — %s", e, exc_info=True)


def start_scheduler() -> BackgroundScheduler:
    """Initialize database, run backfill, and start the scheduler."""
    from . import data_store
    data_store.init_db()

    # Run backfill synchronously (fast — one HTTP call for 30-day ECB data)
    _job_backfill_if_needed()

    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Background data scheduler started")
    return scheduler


def stop_scheduler(scheduler: BackgroundScheduler) -> None:
    """Gracefully shut down the scheduler."""
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Background data scheduler stopped")
