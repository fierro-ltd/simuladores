"""Tests that the SQL migration file exists and has expected structure."""

import pathlib


MIGRATION_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "agent_harness"
    / "memory"
    / "migrations"
    / "001_memory_graph.sql"
)


class TestMigrationSQL:
    def test_migration_file_exists(self):
        assert MIGRATION_PATH.is_file(), f"Migration not found at {MIGRATION_PATH}"

    def test_contains_required_tables(self):
        sql = MIGRATION_PATH.read_text()
        assert "CREATE TABLE IF NOT EXISTS memory_nodes" in sql
        assert "CREATE TABLE IF NOT EXISTS memory_edges" in sql

    def test_contains_pgvector_extension(self):
        sql = MIGRATION_PATH.read_text()
        assert "CREATE EXTENSION IF NOT EXISTS vector" in sql

    def test_contains_pg_trgm_extension(self):
        sql = MIGRATION_PATH.read_text()
        assert "CREATE EXTENSION IF NOT EXISTS pg_trgm" in sql

    def test_contains_hybrid_search_function(self):
        sql = MIGRATION_PATH.read_text()
        assert "hybrid_memory_search" in sql

    def test_contains_hnsw_index(self):
        sql = MIGRATION_PATH.read_text()
        assert "hnsw" in sql.lower()
        assert "vector_cosine_ops" in sql

    def test_contains_rrf_fusion(self):
        sql = MIGRATION_PATH.read_text()
        assert "p_rrf_k" in sql

    def test_wrapped_in_transaction(self):
        sql = MIGRATION_PATH.read_text()
        assert sql.strip().startswith("BEGIN;") or sql.strip().startswith("-- ")
        assert "COMMIT;" in sql
