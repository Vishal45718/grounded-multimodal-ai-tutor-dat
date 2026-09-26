-- Versioned evidence-corpus schema (M1), with the staleness/deprecation
-- columns M6 needs to invalidate superseded content.

CREATE TABLE IF NOT EXISTS sources (
    source_id       TEXT PRIMARY KEY,
    content_hash    TEXT NOT NULL,
    course_edition  TEXT NOT NULL,
    title           TEXT NOT NULL,
    ingested_at     REAL NOT NULL,
    is_deprecated   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id        TEXT PRIMARY KEY,
    source_id       TEXT NOT NULL REFERENCES sources(source_id),
    content_hash    TEXT NOT NULL,
    modality        TEXT NOT NULL CHECK (modality IN ('audio', 'visual')),
    start_sec       REAL NOT NULL,
    end_sec         REAL NOT NULL,
    text            TEXT NOT NULL,
    image_path      TEXT,
    -- denormalized for M6: a chunk from an edited or deprecated source must
    -- never be served, even if a downstream embedding cache still has it.
    is_stale        INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_id);
CREATE INDEX IF NOT EXISTS idx_chunks_modality ON chunks(modality);
