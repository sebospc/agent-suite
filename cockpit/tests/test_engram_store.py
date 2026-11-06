import sqlite3
import tempfile
import unittest
from pathlib import Path

from cockpit.engram.engram_store import EngramStore

LISTED = '{"type":"attachment","tools":["mcp__engram__mem_save","mcp__engram__mem_search","mcp__engram__mem_pin"]}\n'
QUOTED = '{"type":"assistant","text":"grep for \\"mcp__engram__mem_search\\" in the tail"}\n'


class EngramStoreSessionsTest(unittest.TestCase):
    def sessions(self, lines: str) -> dict:
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "project"
            folder.mkdir()
            (folder / "s1.jsonl").write_text(lines)
            return EngramStore("engram", "unused.db", root, "acme")._sessions()

    def test_a_listed_tool_counts_as_loaded(self):
        self.assertTrue(self.sessions(LISTED)["s1"]["loaded"])

    def test_the_name_quoted_in_a_message_does_not(self):
        self.assertFalse(self.sessions(QUOTED)["s1"]["loaded"])


if __name__ == "__main__":
    unittest.main()


class EngramStoreMemoriesTest(unittest.TestCase):
    def test_a_save_after_the_migration_counts_even_under_the_migration_session(self):
        with tempfile.TemporaryDirectory() as root:
            db = str(Path(root) / "engram.db")
            with sqlite3.connect(db) as conn:
                conn.execute("create table observations (project text, session_id text, created_at text, updated_at text, deleted_at text)")
                rows = [("acme", "memory-migration-2026-11-05", "2026-11-05 20:01:00", "2026-11-05 20:01:00"),
                        ("acme", "memory-migration-2026-11-05", "2026-11-05 22:00:00", "2026-11-05 22:00:00"),
                        ("acme", "manual-save-acme", "2026-11-05 23:00:00", "2026-11-05 23:00:00")]
                conn.executemany("insert into observations values (?, ?, ?, ?, null)", rows)
            got = EngramStore("engram", db, root, "acme")._memories()
            self.assertEqual((3, 2), (got["total"], got["saved_by_sessions"]))
