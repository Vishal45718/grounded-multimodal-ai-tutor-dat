-- Versioned evidence-corpus schema (M1), with the staleness/deprecation
-- columns M6 needs to invalidate superseded content.

CREATE TABLE IF NOT EXISTS sources (
    source_id           TEXT PRIMARY KEY,
    content_hash        TEXT NOT NULL,
    course_edition      TEXT NOT NULL,
    title               TEXT NOT NULL,
    ingested_at         REAL NOT NULL,
    is_deprecated       INTEGER NOT NULL DEFAULT 0,
    asset_id            TEXT,
    source_url          TEXT,
    original_asset_url  TEXT,
    license             TEXT,
    license_url         TEXT,
    attribution         TEXT,
    modification_notice TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id            TEXT PRIMARY KEY,
    source_id           TEXT NOT NULL REFERENCES sources(source_id),
    content_hash        TEXT NOT NULL,
    modality            TEXT NOT NULL CHECK (modality IN ('audio', 'visual')),
    start_sec           REAL,
    end_sec             REAL,
    text                TEXT NOT NULL,
    image_path          TEXT,
    is_stale            INTEGER NOT NULL DEFAULT 0,
    asset_id            TEXT,
    source_url          TEXT,
    original_asset_url  TEXT,
    edition_id          TEXT,
    status              TEXT NOT NULL DEFAULT 'success',
    error_message       TEXT,
    page_number         INTEGER,
    extraction_method   TEXT,
    license             TEXT,
    license_url         TEXT,
    attribution         TEXT,
    modification_notice TEXT
);

CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_id);
CREATE INDEX IF NOT EXISTS idx_chunks_modality ON chunks(modality);
