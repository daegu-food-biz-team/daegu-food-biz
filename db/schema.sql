-- DAEGU FOOD BIZ: raw version archive, current 2025 v2 data marts and policy stub.
-- Run with PostgreSQL 14+; all schemas are namespaced to avoid interfering with other work.
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS mart;

CREATE TABLE IF NOT EXISTS raw.ingestion_runs (
    run_id TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    source_description TEXT NOT NULL,
    inserted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    officer_count INTEGER NOT NULL,
    founder_count INTEGER NOT NULL,
    mapping_count INTEGER NOT NULL,
    model_version TEXT NOT NULL,
    as_of INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS raw.ingest_rows (
    run_id TEXT NOT NULL REFERENCES raw.ingestion_runs(run_id),
    dataset TEXT NOT NULL,
    row_number INTEGER NOT NULL,
    unit TEXT NOT NULL,
    payload JSONB NOT NULL,
    PRIMARY KEY (run_id,dataset,row_number)
);
CREATE INDEX IF NOT EXISTS ix_raw_ingest_unit ON raw.ingest_rows(dataset,unit);

CREATE TABLE IF NOT EXISTS mart.officer_latest (
    unit TEXT PRIMARY KEY,
    gu TEXT NOT NULL,
    dong TEXT NOT NULL,
    diagnosis_scope TEXT NOT NULL,
    is_stagnant BOOLEAN,
    bottleneck TEXT,
    confidence TEXT,
    val_accuracy DOUBLE PRECISION,
    rule_agree BOOLEAN,
    entry_pct DOUBLE PRECISION,
    surv_pct DOUBLE PRECISION,
    gap DOUBLE PRECISION,
    reasons TEXT,
    n_active INTEGER NOT NULL,
    growth_past3 DOUBLE PRECISION,
    open_rate DOUBLE PRECISION,
    close_rate DOUBLE PRECISION,
    pop3 DOUBLE PRECISION,
    hjd_main_code TEXT,
    hjd_main_name TEXT,
    hjd_main_share DOUBLE PRECISION,
    t0 INTEGER NOT NULL,
    model_version TEXT NOT NULL,
    CHECK (bottleneck IS NULL OR bottleneck IN ('진입 병목','생존 병목')),
    CHECK (confidence IS NULL OR confidence IN ('높음','보통','낮음'))
);
-- Existing v0.6 installations: add the new classification and allow NULL for rural out-of-scope areas.
ALTER TABLE mart.officer_latest ADD COLUMN IF NOT EXISTS diagnosis_scope TEXT;
ALTER TABLE mart.officer_latest ALTER COLUMN is_stagnant DROP NOT NULL;
CREATE INDEX IF NOT EXISTS ix_officer_gu ON mart.officer_latest(gu);

CREATE TABLE IF NOT EXISTS mart.founder_cafe_latest (
    unit TEXT PRIMARY KEY REFERENCES mart.officer_latest(unit),
    gu TEXT NOT NULL,
    dong TEXT NOT NULL,
    industry TEXT NOT NULL,
    surv2_adj DOUBLE PRECISION,
    surv2_raw DOUBLE PRECISION,
    cohort_n INTEGER NOT NULL,
    small_sample BOOLEAN NOT NULL,
    active_2022 INTEGER,
    active_2025 INTEGER,
    open_2016 INTEGER,close_2016 INTEGER,
    open_2017 INTEGER,close_2017 INTEGER,
    open_2018 INTEGER,close_2018 INTEGER,
    open_2019 INTEGER,close_2019 INTEGER,
    open_2020 INTEGER,close_2020 INTEGER,
    open_2021 INTEGER,close_2021 INTEGER,
    open_2022 INTEGER,close_2022 INTEGER,
    open_2023 INTEGER,close_2023 INTEGER,
    open_2024 INTEGER,close_2024 INTEGER,
    open_2025 INTEGER,close_2025 INTEGER
);
CREATE TABLE IF NOT EXISTS mart.unit_hjd_latest (
    unit TEXT NOT NULL REFERENCES mart.officer_latest(unit),
    hjd_code TEXT NOT NULL,
    stores INTEGER,
    share DOUBLE PRECISION,
    hjd_name TEXT,
    PRIMARY KEY(unit,hjd_code)
);
-- Empty until the team provides verified support program records.
CREATE TABLE IF NOT EXISTS mart.support_programs (
    program_id TEXT PRIMARY KEY,
    program_name TEXT NOT NULL,
    policy_type TEXT,
    operating_agency TEXT,
    scope TEXT,
    application_url TEXT,
    evidence_url TEXT,
    source_updated_at DATE,
    checked_at TIMESTAMPTZ
);
