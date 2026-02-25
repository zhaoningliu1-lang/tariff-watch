"""PostgreSQL connection pool and data-access helpers."""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

logger = logging.getLogger(__name__)

_pool: ThreadedConnectionPool | None = None

# ── Connection pool ──────────────────────────────────────────────────────────

def _dsn() -> str:
    """Build DSN from environment variables (Docker-friendly)."""
    return (
        f"host={os.environ.get('PGHOST', 'localhost')} "
        f"port={os.environ.get('PGPORT', '5432')} "
        f"dbname={os.environ.get('PGDATABASE', 'tariff_watch')} "
        f"user={os.environ.get('PGUSER', 'tariff')} "
        f"password={os.environ.get('PGPASSWORD', 'tariff')}"
    )


def init_pool(minconn: int = 1, maxconn: int = 10) -> None:
    """Initialise the global connection pool. Call once at application startup."""
    global _pool
    if _pool is not None:
        return
    _pool = ThreadedConnectionPool(minconn, maxconn, dsn=_dsn())
    logger.info("PostgreSQL pool initialised (min=%d max=%d)", minconn, maxconn)


def close_pool() -> None:
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None


@contextmanager
def get_conn() -> Generator[psycopg2.extensions.connection, None, None]:
    """Yield a connection from the pool, auto-commit or rollback on exit."""
    if _pool is None:
        init_pool()
    assert _pool is not None
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


# ── Schema bootstrap ─────────────────────────────────────────────────────────

def apply_schema() -> None:
    """Create tables if they don't exist (idempotent)."""
    sql = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
    logger.info("Schema applied.")


# ── Write helpers ────────────────────────────────────────────────────────────

def upsert_snapshots(rows: list[dict], snapshot_date: str) -> int:
    """
    Bulk-upsert HTS snapshot rows for *snapshot_date* (YYYY-MM-DD).
    Returns number of rows inserted/updated.
    """
    if not rows:
        return 0

    sql = """
        INSERT INTO hts_snapshots (
            snapshot_date, hts_code, description,
            rate_general_raw, rate_general_value,
            rate_special_raw, rate_special_value,
            rate_column2_raw, rate_column2_value,
            additional_duties_raw
        ) VALUES (
            %(snapshot_date)s, %(hts_code)s, %(description)s,
            %(rate_general_raw)s, %(rate_general_value)s,
            %(rate_special_raw)s, %(rate_special_value)s,
            %(rate_column2_raw)s, %(rate_column2_value)s,
            %(additional_duties_raw)s
        )
        ON CONFLICT (snapshot_date, hts_code) DO UPDATE SET
            description          = EXCLUDED.description,
            rate_general_raw     = EXCLUDED.rate_general_raw,
            rate_general_value   = EXCLUDED.rate_general_value,
            rate_special_raw     = EXCLUDED.rate_special_raw,
            rate_special_value   = EXCLUDED.rate_special_value,
            rate_column2_raw     = EXCLUDED.rate_column2_raw,
            rate_column2_value   = EXCLUDED.rate_column2_value,
            additional_duties_raw = EXCLUDED.additional_duties_raw
    """
    payload = [{**r, "snapshot_date": snapshot_date} for r in rows]
    with get_conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, payload, page_size=500)
    return len(rows)


def insert_changes(changes: list[dict], detected_at: str) -> int:
    """Persist detected rate changes for *detected_at* (YYYY-MM-DD)."""
    if not changes:
        return 0
    sql = """
        INSERT INTO rate_changes
            (detected_at, hts_code, description, change_type, field_changed, old_value, new_value)
        VALUES
            (%(detected_at)s, %(hts_code)s, %(description)s, %(change_type)s,
             %(field_changed)s, %(old_value)s, %(new_value)s)
    """
    payload = [{**c, "detected_at": detected_at} for c in changes]
    with get_conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, payload, page_size=500)
    return len(changes)


def upsert_notices(notices: list[dict]) -> int:
    """Upsert Federal Register notices (idempotent by document_number)."""
    if not notices:
        return 0
    sql = """
        INSERT INTO federal_register_notices
            (document_number, published_date, title, url, agency, abstract)
        VALUES
            (%(document_number)s, %(published_date)s, %(title)s,
             %(url)s, %(agency)s, %(abstract)s)
        ON CONFLICT (document_number) DO UPDATE SET
            title          = EXCLUDED.title,
            url            = EXCLUDED.url,
            agency         = EXCLUDED.agency,
            abstract       = EXCLUDED.abstract
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, notices, page_size=200)
    return len(notices)


# ── Read helpers ─────────────────────────────────────────────────────────────

def query_current_rates(hts_prefix: str) -> list[dict]:
    """
    Return the most-recent snapshot row(s) whose hts_code starts with *hts_prefix*.
    """
    sql = """
        SELECT DISTINCT ON (hts_code)
            snapshot_date, hts_code, description,
            rate_general_raw, rate_general_value,
            rate_special_raw, rate_special_value,
            rate_column2_raw, rate_column2_value,
            additional_duties_raw
        FROM hts_snapshots
        WHERE hts_code LIKE %(prefix)s
        ORDER BY hts_code, snapshot_date DESC
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, {"prefix": f"{hts_prefix}%"})
            return [dict(r) for r in cur.fetchall()]


def query_rate_history(hts_code: str, limit: int = 52) -> list[dict]:
    """Return per-snapshot rate history for an exact *hts_code*."""
    sql = """
        SELECT snapshot_date, rate_general_raw, rate_general_value,
               rate_special_raw, additional_duties_raw
        FROM hts_snapshots
        WHERE hts_code = %(code)s
        ORDER BY snapshot_date DESC
        LIMIT %(limit)s
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, {"code": hts_code, "limit": limit})
            return [dict(r) for r in cur.fetchall()]


def query_recent_changes(since: str, hts_prefix: str | None = None, limit: int = 200) -> list[dict]:
    """Return rate changes since *since* (YYYY-MM-DD), optionally filtered by prefix."""
    conditions = ["detected_at >= %(since)s"]
    params: dict = {"since": since, "limit": limit}
    if hts_prefix:
        conditions.append("hts_code LIKE %(prefix)s")
        params["prefix"] = f"{hts_prefix}%"
    where = " AND ".join(conditions)
    sql = f"""
        SELECT detected_at, hts_code, description, change_type, field_changed, old_value, new_value
        FROM rate_changes
        WHERE {where}
        ORDER BY detected_at DESC, hts_code
        LIMIT %(limit)s
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]


def query_recent_notices(limit: int = 20, agency: str | None = None) -> list[dict]:
    """Return recent Federal Register notices, optionally filtered by agency."""
    conditions = []
    params: dict = {"limit": limit}
    if agency:
        conditions.append("agency ILIKE %(agency)s")
        params["agency"] = f"%{agency}%"
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"""
        SELECT document_number, published_date, title, url, agency, abstract
        FROM federal_register_notices
        {where}
        ORDER BY published_date DESC
        LIMIT %(limit)s
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
