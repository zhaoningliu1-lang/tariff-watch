-- Tariff Watch V2 — PostgreSQL schema
-- Run once to initialise the database.

-- ── HTS rate snapshots ──────────────────────────────────────────────────────
-- One row per (snapshot_date, hts_code) — fully idempotent via ON CONFLICT.
CREATE TABLE IF NOT EXISTS hts_snapshots (
    id                   BIGSERIAL PRIMARY KEY,
    snapshot_date        DATE        NOT NULL,
    hts_code             TEXT        NOT NULL,
    description          TEXT,
    rate_general_raw     TEXT,
    rate_general_value   NUMERIC,
    rate_special_raw     TEXT,
    rate_special_value   NUMERIC,
    rate_column2_raw     TEXT,
    rate_column2_value   NUMERIC,
    additional_duties_raw TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (snapshot_date, hts_code)
);

CREATE INDEX IF NOT EXISTS idx_hts_snapshots_code ON hts_snapshots (hts_code);
CREATE INDEX IF NOT EXISTS idx_hts_snapshots_date ON hts_snapshots (snapshot_date);
CREATE INDEX IF NOT EXISTS idx_hts_snapshots_code_date ON hts_snapshots (hts_code, snapshot_date DESC);

-- ── Detected rate changes ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rate_changes (
    id           BIGSERIAL PRIMARY KEY,
    detected_at  DATE        NOT NULL,
    hts_code     TEXT        NOT NULL,
    description  TEXT,
    change_type  TEXT        NOT NULL,  -- 'rate_changed' | 'added' | 'removed'
    field_changed TEXT,                 -- e.g. 'rate_general_raw'
    old_value    TEXT,
    new_value    TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rate_changes_code ON rate_changes (hts_code);
CREATE INDEX IF NOT EXISTS idx_rate_changes_date ON rate_changes (detected_at DESC);

-- ── Federal Register notices ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS federal_register_notices (
    id              BIGSERIAL   PRIMARY KEY,
    document_number TEXT        UNIQUE NOT NULL,
    published_date  DATE        NOT NULL,
    title           TEXT        NOT NULL,
    url             TEXT,
    agency          TEXT,
    abstract        TEXT,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fr_notices_date ON federal_register_notices (published_date DESC);
CREATE INDEX IF NOT EXISTS idx_fr_notices_agency ON federal_register_notices (agency);
