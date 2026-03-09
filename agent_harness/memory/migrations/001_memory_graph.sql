-- agent_harness/memory/migrations/001_memory_graph.sql
-- Memory graph schema: typed nodes with pgvector embeddings + hybrid search.
-- Run against PostgreSQL 16+ with pgvector and pg_trgm extensions.

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Enum types
DO $$ BEGIN
    CREATE TYPE memory_type AS ENUM ('fact', 'decision', 'pattern', 'preference', 'error');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE relation_type AS ENUM ('updates', 'contradicts', 'caused_by', 'related_to');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Memory nodes
CREATE TABLE IF NOT EXISTS memory_nodes (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain        TEXT NOT NULL,
    content       TEXT NOT NULL,
    memory_type   memory_type NOT NULL,
    importance    REAL NOT NULL DEFAULT 0.5 CHECK (importance BETWEEN 0.0 AND 1.0),
    embedding     vector(1024) NOT NULL,
    source        TEXT,
    metadata      JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_accessed TIMESTAMPTZ NOT NULL DEFAULT now(),
    access_count  INTEGER NOT NULL DEFAULT 0,
    forgotten     BOOLEAN NOT NULL DEFAULT FALSE,
    fts           tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);

-- Memory edges
CREATE TABLE IF NOT EXISTS memory_edges (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id   UUID NOT NULL REFERENCES memory_nodes(id) ON DELETE CASCADE,
    target_id   UUID NOT NULL REFERENCES memory_nodes(id) ON DELETE CASCADE,
    relation    relation_type NOT NULL,
    weight      REAL NOT NULL DEFAULT 1.0 CHECK (weight BETWEEN 0.0 AND 1.0),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_id, target_id, relation)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_mn_embedding ON memory_nodes
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 256);
CREATE INDEX IF NOT EXISTS idx_mn_content_trgm ON memory_nodes
    USING gin (content gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_mn_fts ON memory_nodes USING gin (fts);
CREATE INDEX IF NOT EXISTS idx_mn_domain_type ON memory_nodes (domain, memory_type)
    WHERE NOT forgotten;
CREATE INDEX IF NOT EXISTS idx_mn_created ON memory_nodes (created_at DESC)
    WHERE NOT forgotten;
CREATE INDEX IF NOT EXISTS idx_me_source ON memory_edges (source_id);
CREATE INDEX IF NOT EXISTS idx_me_target ON memory_edges (target_id);

-- Hybrid search function: pgvector cosine + tsvector FTS + pg_trgm, fused via RRF
CREATE OR REPLACE FUNCTION hybrid_memory_search(
    p_domain       TEXT,
    p_query_text   TEXT,
    p_embedding    vector(1024),
    p_match_count  INT DEFAULT 10,
    p_memory_types memory_type[] DEFAULT NULL,
    p_semantic_w   REAL DEFAULT 1.0,
    p_keyword_w    REAL DEFAULT 0.5,
    p_trigram_w    REAL DEFAULT 0.3,
    p_rrf_k        INT DEFAULT 60
)
RETURNS TABLE (
    id           UUID,
    content      TEXT,
    memory_type  memory_type,
    importance   REAL,
    domain       TEXT,
    metadata     JSONB,
    rrf_score    REAL,
    created_at   TIMESTAMPTZ
)
LANGUAGE sql STABLE
AS $$
WITH
semantic AS (
    SELECT mn.id,
           row_number() OVER (ORDER BY mn.embedding <=> p_embedding) AS rank_ix
    FROM memory_nodes mn
    WHERE mn.domain = p_domain AND NOT mn.forgotten
      AND (p_memory_types IS NULL OR mn.memory_type = ANY(p_memory_types))
    ORDER BY mn.embedding <=> p_embedding
    LIMIT p_match_count * 4
),
keyword AS (
    SELECT mn.id,
           row_number() OVER (
               ORDER BY ts_rank_cd(mn.fts, websearch_to_tsquery('english', p_query_text)) DESC
           ) AS rank_ix
    FROM memory_nodes mn
    WHERE mn.domain = p_domain AND NOT mn.forgotten
      AND (p_memory_types IS NULL OR mn.memory_type = ANY(p_memory_types))
      AND mn.fts @@ websearch_to_tsquery('english', p_query_text)
    ORDER BY rank_ix
    LIMIT p_match_count * 4
),
trigram AS (
    SELECT mn.id,
           row_number() OVER (ORDER BY mn.content <-> p_query_text) AS rank_ix
    FROM memory_nodes mn
    WHERE mn.domain = p_domain AND NOT mn.forgotten
      AND (p_memory_types IS NULL OR mn.memory_type = ANY(p_memory_types))
      AND similarity(mn.content, p_query_text) > 0.1
    ORDER BY mn.content <-> p_query_text
    LIMIT p_match_count * 4
),
fused AS (
    SELECT COALESCE(s.id, k.id, t.id) AS id,
           (COALESCE(1.0 / (p_rrf_k + s.rank_ix), 0.0) * p_semantic_w +
            COALESCE(1.0 / (p_rrf_k + k.rank_ix), 0.0) * p_keyword_w +
            COALESCE(1.0 / (p_rrf_k + t.rank_ix), 0.0) * p_trigram_w
           ) AS score
    FROM semantic s
    FULL OUTER JOIN keyword k ON s.id = k.id
    FULL OUTER JOIN trigram t ON COALESCE(s.id, k.id) = t.id
)
SELECT mn.id, mn.content, mn.memory_type, mn.importance,
       mn.domain, mn.metadata, f.score::REAL AS rrf_score, mn.created_at
FROM fused f
JOIN memory_nodes mn ON f.id = mn.id
ORDER BY f.score DESC
LIMIT p_match_count;
$$;

COMMIT;
