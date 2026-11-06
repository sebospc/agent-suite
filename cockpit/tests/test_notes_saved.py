import json
import os
import tempfile
import unittest
from dataclasses import replace

from cockpit.asks.fake_asks import FakeAsks
from cockpit.autopilot.rules import SPOT, decide, skipped
from cockpit.git.fake_git import FakeGit
from cockpit.git.gate_state import GateState
from cockpit.live_sessions.fake_live_sessions import FakeLiveSessions
from cockpit.live_sessions.live_session import LiveSession
from cockpit.role_memory.claude_memory_files import ClaudeMemoryFiles
from cockpit.role_memory.fake_role_memory import FakeRoleMemory
from cockpit.sessions.session_row import notes_saved, session_row
from cockpit.transcripts.fake_transcripts import FakeTranscripts
from cockpit.transcripts.transcript_file import TranscriptFile
from cockpit.transcripts.transcript_stats import turn_started_at
from tests.builders import NOW, bead, prices, thresholds
from tests.test_autopilot import row as autopilot_row
from tests.test_sessions import row, stats
from tests.test_snapshot import builder

TURN_START, TURN_END = NOW - 700, NOW - 600


def role_row(state_file_at, state="idle"):
    live = LiveSession("agent-coordinator", "s1", 1, "w1:p2", "15", state)
    w = {"bead": "no bead", "tag": "", "kind": "role", "line": "", "held": []}
    return session_row("coordinator", live, stats(400_000), w, [], None, [], thresholds(), prices(), NOW,
                       "project_coordinator_state.md", state_file_at)


class BeadNotesTest(unittest.TestCase):
    def test_a_bead_updated_during_the_last_turn_counts_as_saved_though_the_turn_ended_later(self):
        saved = row(400_000, held=[bead("pg-c1", "in_progress", updated=TURN_START + 50)])  # before TURN_END
        self.assertTrue(saved["notes_saved"])
        self.assertTrue(saved["can_compact"])

    def test_a_bead_last_updated_before_the_last_turn_started_is_not_saved(self):
        unsaved = row(400_000, held=[bead("pg-c1", "in_progress", updated=TURN_START - 100)])
        self.assertFalse(unsaved["notes_saved"])
        self.assertFalse(unsaved["can_compact"])

    def test_without_a_turn_start_nothing_is_claimed(self):
        self.assertIsNone(notes_saved([bead("pg-c1", "in_progress")], stats(400_000, turn_started=None)))


class RoleNotesTest(unittest.TestCase):
    def test_a_role_session_is_saved_when_its_state_file_changed_during_the_last_turn(self):
        self.assertTrue(role_row(TURN_START + 50)["notes_saved"])
        self.assertTrue(role_row(TURN_START + 50)["can_compact"])

    def test_a_role_session_with_an_old_or_missing_state_file_is_not_saved(self):
        self.assertFalse(role_row(TURN_START - 100)["notes_saved"])
        self.assertFalse(role_row(None)["notes_saved"])
        self.assertFalse(role_row(None)["can_compact"])


class TurnStartTest(unittest.TestCase):
    def test_a_slash_command_starts_no_turn_so_the_last_real_prompt_counts(self):
        prompts = [{"t": 100.0, "origin": "person"}, {"t": 150.0, "origin": "peer"}, {"t": 200.0, "origin": "command"}]
        self.assertEqual(150.0, turn_started_at(prompts))
        self.assertIsNone(turn_started_at([]))

    def test_a_tool_result_is_not_a_prompt(self):
        path = os.path.join(tempfile.mkdtemp(), "s.jsonl")
        lines = [{"type": "user", "timestamp": "2026-10-15T10:00:00Z", "message": {"content": "do the thing"}},
                 {"type": "user", "timestamp": "2026-10-15T10:05:00Z",
                  "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]}}]
        with open(path, "w") as handle:
            handle.write("\n".join(json.dumps(l) for l in lines) + "\n")
        file = TranscriptFile(path)
        file.update()
        self.assertEqual([file.prompts[0]["t"]], [p["t"] for p in file.prompts])
        self.assertEqual(file.prompts[0]["t"], turn_started_at(file.prompts))


class StateFileAdapterTest(unittest.TestCase):
    def test_it_reads_the_modified_time_of_the_roles_state_file_and_nothing_else(self):
        root = tempfile.mkdtemp()
        memory = os.path.join(root, "-work-project", "memory")
        os.makedirs(memory)
        path = os.path.join(memory, "project_brain_state.md")
        open(path, "w").close()
        os.utime(path, (5000, 5000))
        files = ClaudeMemoryFiles(root)
        self.assertEqual(5000, files.modified_at("/work/project", "brain"))
        self.assertIsNone(files.modified_at("/work/project", "reviewer"))
        self.assertIsNone(files.modified_at("", "brain"))

    def test_a_hyphenated_role_finds_the_state_file_its_session_spelled(self):
        root = tempfile.mkdtemp()
        memory = os.path.join(root, "-work-project", "memory")
        os.makedirs(memory)
        for name, at in (("project_reviewer2_state.md", 6000), ("project_shaping_lead_state.md", 7000)):
            open(os.path.join(memory, name), "w").close()
            os.utime(os.path.join(memory, name), (at, at))
        files = ClaudeMemoryFiles(root)
        self.assertEqual((6000, "project_reviewer2_state.md"),
                         (files.modified_at("/work/project", "reviewer-2"), files.state_file("reviewer-2", "/work/project")))
        self.assertEqual(7000, files.modified_at("/work/project", "shaping-lead"))
        self.assertEqual("project_design-x_state.md", files.state_file("design-x", "/work/project"))


class AutopilotGuardTest(unittest.TestCase):
    def test_a_role_session_whose_state_file_did_not_change_still_compacts(self):
        coordinator = autopilot_row(name="coordinator", notes_saved=False, notes_file="project_coordinator_state.md", holds=0)
        # A compaction's summary keeps unsaved work (brain, pg-o1sq finding 3 answer); only a clear waits for the file.
        self.assertEqual([SPOT], [c["rule"] for c in decide([coordinator], set(), thresholds(), NOW)])
        # Under its sweet spot a Haiku session is left to Claude Code's own window: the guard rule is gone (panels f68cd6 to b31e2b).
        haiku = dict(coordinator, haiku_guarded=True, context=95_000, over=False)
        self.assertEqual([], decide([haiku], set(), thresholds(), NOW))

    def test_an_owner_answer_missing_from_decisions_does_not_hold_brains_compaction(self):
        # panel.json keeps the owner's exact words, so a summary loses nothing of them (panels f68cd6 to b31e2b).
        brain = autopilot_row(name="brain", notes_saved=True, unsaved_answers=["4c9041", "696253"], holds=0)
        self.assertEqual(["compact"], [c["kind"] for c in decide([brain], set(), thresholds(), NOW)])
        self.assertEqual([], [s for s in skipped([brain], set(), thresholds(), NOW) if "DECISIONS" in s["why"]])


class SnapshotWiringTest(unittest.TestCase):
    def snapshot(self, decisions, state_file_at):
        b = builder()
        answered = [{"id": "4c9041", "answer": "yes", "text": "q", "answeredAt": "2026-10-15T23:00:00-05:00"}]
        live = [LiveSession("agent-brain", "s1", 1, "w1:p1", "15", "idle")]
        b.ports = replace(b.ports, live_sessions=FakeLiveSessions(live), asks=FakeAsks([], answered, NOW),
                          transcripts=FakeTranscripts({"s1": replace(stats(400_000), cwd="/work")}),
                          git=FakeGit(GateState("C120", True, False, 0, 0, "t"), {}, files={"docs/DECISIONS.md": decisions}),
                          role_memory=FakeRoleMemory({"brain": state_file_at}))
        return next(r for r in b.build()["sessions"] if r["name"] == "brain")

    def test_brain_carries_the_answers_missing_from_decisions_and_its_state_file_check(self):
        missing = self.snapshot("nothing recorded", TURN_START + 50)
        self.assertEqual(["4c9041"], missing["unsaved_answers"])
        self.assertEqual("project_brain_state.md", missing["notes_file"])
        self.assertTrue(missing["notes_saved"])
        self.assertEqual([], self.snapshot("panel 4c9041: yes", TURN_START - 100)["unsaved_answers"])
        self.assertFalse(self.snapshot("panel 4c9041: yes", TURN_START - 100)["notes_saved"])


if __name__ == "__main__":
    unittest.main()
