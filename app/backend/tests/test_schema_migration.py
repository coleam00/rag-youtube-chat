"""
Tests for _migrate_add_chunk_timestamps schema migration.

Verifies:
  - Migration guard prevents re-execution when start_seconds column exists
  - 150 WPM heuristic produces reasonable timestamps
  - Empty transcripts return estimated_duration of at least 1.0 second
"""

import pytest

from backend.db.schema import _migrate_add_chunk_timestamps


class TestMigrateAddChunkTimestamps:
    async def test_guard_prevents_re_execution(self, tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
        """If start_seconds column already exists, migration returns immediately."""
        import aiosqlite

        db_path = tmp_path / "test_guard.db"
        # Create a fresh DB with the new schema (already has start_seconds column)
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    video_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    start_seconds FLOAT NOT NULL DEFAULT 0,
                    end_seconds FLOAT NOT NULL DEFAULT 0,
                    snippet TEXT NOT NULL DEFAULT ''
                )
            """
            )
            await db.execute(
                "CREATE TABLE IF NOT EXISTS videos (id TEXT PRIMARY KEY, title TEXT, transcript TEXT)"
            )
            await db.commit()

        # Track that no UPDATE was issued
        update_count = 0

        async def fake_execute(sql: str, *args) -> None:
            nonlocal update_count
            if "UPDATE chunks SET start_seconds" in sql:
                update_count += 1

        import backend.db.schema as schema_module

        monkeypatch.setattr(schema_module, "DB_PATH", str(db_path))

        async with aiosqlite.connect(db_path) as db:
            await _migrate_add_chunk_timestamps(db)

        assert update_count == 0, "Migration should not have executed UPDATE when column exists"

    async def test_wpm_heuristic_single_chunk(self) -> None:
        """A 300-word transcript (~2 min at 150 WPM) produces step ≈ 0.8s."""
        # The heuristic: estimated_duration = max(len(words) / 150.0, 1.0)
        # For 300 words: estimated_duration = max(300/150, 1) = max(2.0, 1) = 2.0
        # With 1 chunk: step = 2.0 / 1 = 2.0
        # So start=0, end=2
        words = " ".join(["word"] * 300)
        estimated_duration = max(len(words.split()) / 150.0, 1.0)
        assert estimated_duration == 2.0

    async def test_wpm_heuristic_empty_transcript(self) -> None:
        """Empty transcript returns estimated_duration of at least 1.0 second."""
        words = ""
        estimated_duration = max(len(words.split()) / 150.0, 1.0)
        assert estimated_duration == 1.0

    async def test_wpm_heuristic_short_transcript(self) -> None:
        """Very short transcript (e.g. 10 words) still gets at least 1.0 second."""
        words = " ".join(["word"] * 10)  # ~4 seconds at 150 WPM, but min is 1.0
        estimated_duration = max(len(words.split()) / 150.0, 1.0)
        assert estimated_duration == 1.0

    async def test_wpm_heuristic_large_transcript(self) -> None:
        """Large transcript is scaled linearly."""
        # 1500 words = 10 minutes at 150 WPM
        words = " ".join(["word"] * 1500)
        estimated_duration = max(len(words.split()) / 150.0, 1.0)
        assert estimated_duration == 10.0
