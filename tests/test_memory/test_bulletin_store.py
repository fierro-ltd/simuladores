"""Tests for InMemoryBulletinStore."""

from __future__ import annotations

import pytest

from agent_harness.memory.bulletin import Bulletin
from agent_harness.memory.bulletin_store import InMemoryBulletinStore


class TestInMemoryBulletinStore:
    def test_save_and_get(self):
        store = InMemoryBulletinStore()
        b = Bulletin(
            domain="dce",
            summary="Toys need testing.",
            pattern_count=3,
            generated_at="2026-02-22T10:00:00+00:00",
        )
        store.save(b)
        assert store.get_latest("dce") == b

    def test_latest_returns_most_recent(self):
        store = InMemoryBulletinStore()
        old = Bulletin(
            domain="dce",
            summary="Old summary.",
            pattern_count=2,
            generated_at="2026-02-22T09:00:00+00:00",
        )
        new = Bulletin(
            domain="dce",
            summary="New summary.",
            pattern_count=5,
            generated_at="2026-02-22T11:00:00+00:00",
        )
        store.save(old)
        store.save(new)
        assert store.get_latest("dce") == new

    def test_does_not_replace_with_older(self):
        store = InMemoryBulletinStore()
        new = Bulletin(
            domain="dce",
            summary="Newer.",
            pattern_count=5,
            generated_at="2026-02-22T11:00:00+00:00",
        )
        old = Bulletin(
            domain="dce",
            summary="Older.",
            pattern_count=2,
            generated_at="2026-02-22T09:00:00+00:00",
        )
        store.save(new)
        store.save(old)
        assert store.get_latest("dce") == new

    def test_missing_domain_returns_none(self):
        store = InMemoryBulletinStore()
        assert store.get_latest("dce") is None

    def test_domain_isolation(self):
        store = InMemoryBulletinStore()
        dce = Bulletin(
            domain="dce",
            summary="DCE stuff.",
            pattern_count=1,
            generated_at="2026-02-22T10:00:00+00:00",
        )
        has = Bulletin(
            domain="has",
            summary="HAS stuff.",
            pattern_count=2,
            generated_at="2026-02-22T10:00:00+00:00",
        )
        store.save(dce)
        store.save(has)
        assert store.get_latest("dce") == dce
        assert store.get_latest("has") == has

    def test_get_pattern_strings(self):
        store = InMemoryBulletinStore()
        b = Bulletin(
            domain="dce",
            summary="Key insight.",
            pattern_count=3,
            generated_at="2026-02-22T10:00:00+00:00",
        )
        store.save(b)
        assert store.get_pattern_strings("dce") == ["[bulletin] Key insight."]

    def test_get_pattern_strings_empty_summary(self):
        store = InMemoryBulletinStore()
        b = Bulletin(
            domain="dce",
            summary="",
            pattern_count=0,
            generated_at="2026-02-22T10:00:00+00:00",
        )
        store.save(b)
        assert store.get_pattern_strings("dce") == []

    def test_get_pattern_strings_missing_domain(self):
        store = InMemoryBulletinStore()
        assert store.get_pattern_strings("dce") == []
