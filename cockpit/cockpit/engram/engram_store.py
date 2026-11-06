import json
import os
import re
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Dict

from cockpit.engram.engram_health import EngramHealth

TAIL_BYTES = 3_000_000  # a start lists the deferred tools near the end of a live transcript; the whole file can be GBs
# The migration wrote 278 rows by 20:03:37 UTC; Engram then files most later MCP saves under that same session id,
# so a save is told from the migration by its time, not its session. Today counts updates too: a role state is one
# note rewritten at each pause.
MIGRATION_ENDED_UTC = "2026-11-05 20:03:37"
# The tool list a start writes, as a JSON array item or a plain list line; the name quoted inside a message is escaped, so it never matches
TOOL_LISTED = re.compile(r'(?<!\\)"mcp__engram__mem_search"|(?<!\\)\\nmcp__engram__mem_search\\n')


class EngramStore(EngramHealth):
    """Engram's health for the team: its own doctor, what sessions saved, and which session transcripts load its tools."""

    def __init__(self, binary: str, db: str, transcripts: str, project: str):
        self.binary, self.db, self.project = os.path.expanduser(binary), os.path.expanduser(db), project
        self.transcripts = Path(os.path.expanduser(transcripts))

    def read(self) -> dict:
        return {"doctor": self._doctor(), "memories": self._memories(), "sessions": self._sessions()}

    def _doctor(self) -> dict:
        done = subprocess.run([self.binary, "doctor", "--json", "--project", self.project], capture_output=True, text=True,
                              timeout=20, env={**os.environ, "ENGRAM_NO_UPDATE_CHECK": "1"})
        report = json.loads(done.stdout)
        issues = [c.get("message", "") for c in report.get("checks", []) if c.get("severity") not in ("info", None)]
        return {"status": report.get("status", "unknown"), "issues": issues}

    def _memories(self) -> dict:
        with sqlite3.connect(f"file:{self.db}?mode=ro", uri=True) as db:
            total, saved, today = db.execute(
                "select count(*), sum(created_at > ?), sum(updated_at > ? and updated_at >= datetime('now', 'localtime', 'start of day', 'utc')) "
                "from observations where project = ? and deleted_at is null", (MIGRATION_ENDED_UTC, MIGRATION_ENDED_UTC, self.project)).fetchone()
        return {"total": total or 0, "saved_by_sessions": saved or 0, "saved_today": today or 0}

    def _sessions(self) -> Dict[str, dict]:
        since = time.time() - 86400
        found = {}
        for path in self.transcripts.glob("*/*.jsonl"):
            if path.stat().st_mtime < since:
                continue
            with path.open("rb") as f:
                f.seek(max(0, path.stat().st_size - TAIL_BYTES))
                tail = f.read().decode("utf-8", "ignore")
            found[path.stem] = {"loaded": bool(TOOL_LISTED.search(tail)),
                                "searches": tail.count('"name":"mcp__engram__mem_search"'),
                                "saves": tail.count('"name":"mcp__engram__mem_save"')}
        return found
