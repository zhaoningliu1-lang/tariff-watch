"""
Lightweight SQLite persistence for FX rates and shipping rates.

Separate from db.py (which handles PostgreSQL for tariff snapshots).
Stores daily exchange rates (from ECB or premium APIs) and shipping
rates in a local SQLite database at ~/.tariff-watch/data.db.

Thread-safe: uses threading.local() for connections + WAL mode.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

_DEFAULT_DATA_DIR = os.path.expanduser("~/.tariff-watch")

def _get_data_dir() -> Path:
    return Path(os.environ.get("TARIFF_WATCH_DATA_DIR", _DEFAULT_DATA_DIR))

def _get_db_path() -> Path:
    return _get_data_dir() / "data.db"

# ── Schema ───────────────────────────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS fx_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    currency TEXT NOT NULL,
    rate REAL NOT NULL,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    rate_date TEXT NOT NULL,
    UNIQUE(currency, rate_date)
);

CREATE INDEX IF NOT EXISTS idx_fx_currency_date
    ON fx_rates(currency, rate_date DESC);

CREATE TABLE IF NOT EXISTS shipping_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    route_key TEXT NOT NULL,
    rate_20ft REAL NOT NULL,
    rate_40ft REAL NOT NULL,
    source TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    rate_date TEXT NOT NULL,
    UNIQUE(route_key, rate_date)
);

CREATE INDEX IF NOT EXISTS idx_shipping_key_date
    ON shipping_rates(route_key, rate_date DESC);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

# ── Thread-local connection management ───────────────────────────────────────

_local = threading.local()

def _get_conn() -> sqlite3.Connection:
    """Get a thread-local SQLite connection with WAL mode."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        return conn

    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    _local.conn = conn
    return conn


def init_db() -> None:
    """Create directory and apply schema. Idempotent."""
    conn = _get_conn()
    conn.executescript(_SCHEMA_SQL)
    conn.commit()
    logger.info("SQLite database initialized at %s", _get_db_path())


# ── FX rate operations ───────────────────────────────────────────────────────

def upsert_fx_rate(
    currency: str, rate: float, rate_date: str, source: str,
) -> None:
    """Insert or replace a single FX rate."""
    conn = _get_conn()
    conn.execute(
        """INSERT INTO fx_rates (currency, rate, source, fetched_at, rate_date)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(currency, rate_date) DO UPDATE SET
               rate = excluded.rate,
               source = excluded.source,
               fetched_at = excluded.fetched_at""",
        (currency, rate, source, datetime.utcnow().isoformat(), rate_date),
    )
    conn.commit()


def upsert_fx_rates_bulk(rows: list[dict]) -> int:
    """Batch upsert FX rates. Each dict: {currency, rate, rate_date, source}."""
    conn = _get_conn()
    now = datetime.utcnow().isoformat()
    data = [
        (r["currency"], r["rate"], r["source"], now, r["rate_date"])
        for r in rows
    ]
    conn.executemany(
        """INSERT INTO fx_rates (currency, rate, source, fetched_at, rate_date)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(currency, rate_date) DO UPDATE SET
               rate = excluded.rate,
               source = excluded.source,
               fetched_at = excluded.fetched_at""",
        data,
    )
    conn.commit()
    return len(data)


def query_fx_latest(currency: str) -> dict | None:
    """Latest rate for a currency."""
    conn = _get_conn()
    row = conn.execute(
        """SELECT rate, rate_date, source
           FROM fx_rates WHERE currency = ?
           ORDER BY rate_date DESC LIMIT 1""",
        (currency,),
    ).fetchone()
    if not row:
        return None
    return {"rate": row["rate"], "rate_date": row["rate_date"], "source": row["source"]}


def query_fx_history(currency: str, days: int = 30) -> list[dict]:
    """Last N days of rates, ordered ascending."""
    conn = _get_conn()
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        """SELECT rate_date AS date, rate
           FROM fx_rates WHERE currency = ? AND rate_date >= ?
           ORDER BY rate_date ASC""",
        (currency, cutoff),
    ).fetchall()
    return [{"date": r["date"], "rate": r["rate"]} for r in rows]


def query_all_fx_latest() -> dict[str, dict]:
    """Latest rate for every currency in DB."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT currency, rate, rate_date, source
           FROM fx_rates f1
           WHERE rate_date = (
               SELECT MAX(rate_date) FROM fx_rates f2 WHERE f2.currency = f1.currency
           )""",
    ).fetchall()
    return {
        r["currency"]: {
            "rate": r["rate"],
            "rate_date": r["rate_date"],
            "source": r["source"],
        }
        for r in rows
    }


# ── Shipping rate operations ─────────────────────────────────────────────────

def upsert_shipping_rate(
    route_key: str, rate_20ft: float, rate_40ft: float,
    rate_date: str, source: str,
) -> None:
    """Insert or replace a single shipping rate."""
    conn = _get_conn()
    conn.execute(
        """INSERT INTO shipping_rates (route_key, rate_20ft, rate_40ft, source, fetched_at, rate_date)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(route_key, rate_date) DO UPDATE SET
               rate_20ft = excluded.rate_20ft,
               rate_40ft = excluded.rate_40ft,
               source = excluded.source,
               fetched_at = excluded.fetched_at""",
        (route_key, rate_20ft, rate_40ft, source,
         datetime.utcnow().isoformat(), rate_date),
    )
    conn.commit()


def upsert_shipping_rates_bulk(rows: list[dict]) -> int:
    """Batch upsert shipping rates."""
    conn = _get_conn()
    now = datetime.utcnow().isoformat()
    data = [
        (r["route_key"], r["rate_20ft"], r["rate_40ft"], r["source"], now, r["rate_date"])
        for r in rows
    ]
    conn.executemany(
        """INSERT INTO shipping_rates (route_key, rate_20ft, rate_40ft, source, fetched_at, rate_date)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(route_key, rate_date) DO UPDATE SET
               rate_20ft = excluded.rate_20ft,
               rate_40ft = excluded.rate_40ft,
               source = excluded.source,
               fetched_at = excluded.fetched_at""",
        data,
    )
    conn.commit()
    return len(data)


def query_shipping_latest(route_key: str) -> dict | None:
    """Latest shipping rate for a route."""
    conn = _get_conn()
    row = conn.execute(
        """SELECT rate_20ft, rate_40ft, rate_date, source
           FROM shipping_rates WHERE route_key = ?
           ORDER BY rate_date DESC LIMIT 1""",
        (route_key,),
    ).fetchone()
    if not row:
        return None
    return {
        "rate_20ft": row["rate_20ft"],
        "rate_40ft": row["rate_40ft"],
        "rate_date": row["rate_date"],
        "source": row["source"],
    }


def query_shipping_history(route_key: str, days: int = 30) -> list[dict]:
    """Last N days of shipping rates, ordered ascending."""
    conn = _get_conn()
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        """SELECT rate_date AS date, rate_20ft AS rate_20ft_usd, rate_40ft AS rate_40ft_usd
           FROM shipping_rates WHERE route_key = ? AND rate_date >= ?
           ORDER BY rate_date ASC""",
        (route_key, cutoff),
    ).fetchall()
    return [
        {"date": r["date"], "rate_20ft_usd": r["rate_20ft_usd"], "rate_40ft_usd": r["rate_40ft_usd"]}
        for r in rows
    ]


# ── Metadata operations ─────────────────────────────────────────────────────

def set_meta(key: str, value: str) -> None:
    conn = _get_conn()
    conn.execute(
        """INSERT INTO meta (key, value, updated_at)
           VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET
               value = excluded.value,
               updated_at = excluded.updated_at""",
        (key, value, datetime.utcnow().isoformat()),
    )
    conn.commit()


def get_meta(key: str) -> str | None:
    conn = _get_conn()
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None
