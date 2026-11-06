import json
import os
import tempfile
import unittest
from datetime import UTC, datetime

NUDGED_DIR = tempfile.mkdtemp()
os.environ["AGENT_ENGRAM_NUDGED"] = NUDGED_DIR

import engram_save_nudge as nudge

NOW = datetime(2026, 11, 5, 20, 0, tzinfo=UTC).timestamp()


def stamp(minutes_ago: float) -> str:
    return datetime.fromtimestamp(NOW - minutes_ago * 60, UTC).isoformat().replace("+00:00", "Z")


def line(minutes_ago: float, tool: str | None = None) -> str:
    content = [{"type": "tool_use", "name": tool, "input": {}}] if tool else [{"type": "text", "text": "hi"}]
    return json.dumps({"type": "assistant", "timestamp": stamp(minutes_ago), "message": {"content": content}})


class EngramSaveNudgeTest(unittest.TestCase):
    def prompt(self, lines: list[str], session: str) -> str | None:
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as transcript:
            transcript.write("\n".join(lines) + "\n")
        event = {"hook_event_name": "UserPromptSubmit", "transcript_path": transcript.name, "session_id": session}
        return nudge.context_for(event, NOW)

    def test_a_session_twenty_minutes_past_its_last_save_is_reminded(self):
        self.assertEqual(nudge.NUDGE, self.prompt([line(60), line(20, "mcp__engram__mem_save"), line(1)], "s1"))

    def test_a_recent_save_keeps_it_quiet(self):
        self.assertIsNone(self.prompt([line(60), line(5, "mcp__engram__mem_update"), line(1)], "s2"))

    def test_a_session_younger_than_fifteen_minutes_is_quiet(self):
        self.assertIsNone(self.prompt([line(10), line(1)], "s3"))

    def test_the_reminder_fires_once_per_fifteen_minutes(self):
        lines = [line(90), line(1)]
        self.assertEqual(nudge.NUDGE, self.prompt(lines, "s4"))
        self.assertIsNone(self.prompt(lines, "s4"))

    def test_after_a_compaction_the_summary_is_saved_first(self):
        self.assertEqual(nudge.AFTER_COMPACTION,
                         nudge.context_for({"hook_event_name": "SessionStart", "source": "compact"}, NOW))
        self.assertIsNone(nudge.context_for({"hook_event_name": "SessionStart", "source": "startup"}, NOW))


if __name__ == "__main__":
    unittest.main()
