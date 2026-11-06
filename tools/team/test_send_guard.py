import fcntl
import itertools
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from send_guard import event_key, session_name, verdict

GUARD = Path(__file__).with_name("send_guard.py")
GO_REQ = "GO-REQ pg-a18q.74 v1\npatch: /tmp/x.patch\nsha256: 1a2b3c4d"
NEW_ID = object()
T0 = datetime(2026, 10, 15, 12, 0, 0, tzinfo=UTC)


def named(record_type, name, session_id="s1"):
    field = {"agent-name": "agentName", "custom-title": "customTitle"}[record_type]
    return {"type": record_type, field: name, "sessionId": session_id}


class SendGuardTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.home = Path(scratch.name)
        self.log = self.home / "beads" / "sent.jsonl"
        self.transcripts = 0
        self.tool_use_ids = itertools.count(1)

    def transcript(self, *records):
        self.transcripts += 1
        path = self.home / f"transcript-{self.transcripts}.jsonl"
        path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
        return str(path)

    def session(self, name, session_id="s1"):
        return self.transcript({"type": "user", "sessionId": session_id}, named("agent-name", name, session_id))

    def hook_input(self, event, transcript, to, message=GO_REQ, tool="SendMessage", tool_input=None, tool_use_id=NEW_ID):
        hook = {
            "tool_name": tool,
            "tool_input": tool_input if tool_input is not None else {"to": to, "message": message},
            "transcript_path": transcript,
            "tool_use_id": f"toolu_{next(self.tool_use_ids)}" if tool_use_id is NEW_ID else tool_use_id,
        }
        if event is not None:
            hook["hook_event_name"] = event
        return {field: value for field, value in hook.items() if value is not None}

    def hook(self, event, transcript, to, message=GO_REQ, log=None, **hook_fields):
        return self.run_guard(json.dumps(self.hook_input(event, transcript, to, message, **hook_fields)), log)

    def at(self, now, event, transcript, to, tool_use_id):
        return verdict(self.hook_input(event, transcript, to, tool_use_id=tool_use_id), self.log, now)

    def deliver(self, transcript, to, message=GO_REQ, **hook_fields):
        # What the harness does for a send that goes out: PostToolUse follows only a PreToolUse that let it through.
        tool_use_id = hook_fields.pop("tool_use_id", f"toolu_{next(self.tool_use_ids)}")
        checked = self.hook("PreToolUse", transcript, to, message, tool_use_id=tool_use_id, **hook_fields)
        if checked.returncode == 0:
            posted = self.hook("PostToolUse", transcript, to, message, tool_use_id=tool_use_id, **hook_fields)
            self.assertEqual(posted.returncode, 0)
        return checked

    def logged(self):
        return [(record["state"], record["to"]) for record in map(json.loads, self.log.read_text(encoding="utf-8").splitlines())]

    def run_guard(self, stdin, log=None):
        env = {**os.environ, "HOME": str(self.home), "AGENT_SENT_LOG": str(log or self.log)}
        return subprocess.run([sys.executable, str(GUARD)], input=stdin, capture_output=True, text=True, env=env, check=False)

    def test_a_result_with_no_count_is_blocked_before_it_is_sent(self):
        author = self.session("agent-ios")
        blocked = self.hook("PreToolUse", author, "agent-coordinator", "RESULT pg-x v1\nall tests pass")
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("no count", blocked.stderr)
        self.assertEqual(self.hook("PostToolUse", author, "agent-coordinator", "all tests pass").returncode, 0)

    def test_second_recipient_for_the_same_key_is_blocked(self):
        author = self.session("agent-ios")
        self.assertEqual(self.deliver(author, "agent-reviewer").returncode, 0)
        blocked = self.deliver(author, "agent-coordinator")
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("agent-reviewer", blocked.stderr)
        self.assertEqual(len(blocked.stderr.strip().splitlines()), 1)

    def test_parallel_sends_to_two_recipients_block_the_second_before_either_post(self):
        author = self.session("agent-ios")
        self.assertEqual(self.hook("PreToolUse", author, "agent-reviewer").returncode, 0)
        blocked = self.hook("PreToolUse", author, "agent-coordinator")
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("'agent-reviewer'", blocked.stderr)
        self.assertIn("at most 120 s", blocked.stderr)
        self.assertEqual(len(blocked.stderr.strip().splitlines()), 1)
        self.assertEqual(self.logged(), [("pending", "agent-reviewer")])

    def test_a_failed_send_leaves_its_corrected_resend_to_another_recipient_passing(self):
        author = self.session("agent-ios")
        self.assertEqual(self.hook("PreToolUse", author, "agent-reviwer", tool_use_id="toolu_typo").returncode, 0)
        self.assertEqual(self.hook("PostToolUseFailure", author, "agent-reviwer", tool_use_id="toolu_typo").returncode, 0)
        self.assertEqual(self.deliver(author, "agent-reviewer").returncode, 0)
        self.assertEqual(
            self.logged(),
            [("pending", "agent-reviwer"), ("failed", "agent-reviwer"), ("pending", "agent-reviewer"), ("sent", "agent-reviewer")],
        )

    def test_a_pending_send_with_no_post_blocks_another_recipient_for_120_seconds_only(self):
        author = self.session("agent-ios")
        self.assertIsNone(self.at(T0, "PreToolUse", author, "agent-reviewer", "toolu_lost"))
        waiting = self.at(T0 + timedelta(seconds=100), "PreToolUse", author, "agent-coordinator", "toolu_early")
        self.assertIsNotNone(waiting)
        self.assertIn("resend in 20 s", waiting)
        self.assertIsNotNone(self.at(T0 + timedelta(seconds=119), "PreToolUse", author, "agent-coordinator", "toolu_almost"))
        self.assertIsNone(self.at(T0 + timedelta(seconds=120), "PreToolUse", author, "agent-coordinator", "toolu_after"))

    def test_a_sent_record_blocks_another_recipient_at_any_age(self):
        author = self.session("agent-ios")
        self.assertIsNone(self.at(T0, "PreToolUse", author, "agent-reviewer", "toolu_1"))
        self.assertIsNone(self.at(T0, "PostToolUse", author, "agent-reviewer", "toolu_1"))
        later = self.at(T0 + timedelta(days=30), "PreToolUse", author, "agent-coordinator", "toolu_2")
        self.assertIsNotNone(later)
        self.assertIn("already sent", later)
        self.assertIn("'agent-reviewer'", later)

    def test_a_post_tool_use_on_its_own_logs_the_send_and_another_recipient_is_blocked(self):
        author = self.session("agent-ios")
        self.assertEqual(self.hook("PostToolUse", author, "agent-reviewer").returncode, 0)
        self.assertEqual(self.logged(), [("sent", "agent-reviewer")])
        blocked = self.hook("PreToolUse", author, "agent-coordinator")
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("agent-reviewer", blocked.stderr)

    def test_the_same_recipient_always_passes(self):
        author = self.session("agent-ios")
        for later_event in (None, "PostToolUse", "PostToolUseFailure"):
            with self.subTest(later_event=later_event):
                self.assertIsNone(self.at(T0, "PreToolUse", author, "agent-reviewer", f"toolu_{later_event}"))
                if later_event:
                    self.assertIsNone(self.at(T0, later_event, author, "agent-reviewer", f"toolu_{later_event}"))
                for age in (timedelta(0), timedelta(seconds=119), timedelta(days=30)):
                    self.assertIsNone(self.at(T0 + age, "PreToolUse", author, "agent-reviewer", "toolu_again"))

    def test_a_restarted_session_with_the_same_name_is_still_blocked(self):
        before_restart = self.session("agent-ios", session_id="s1")
        after_restart = self.transcript(named("custom-title", "agent-ios", "s2"), {"type": "user", "sessionId": "s2"})
        self.assertEqual(self.deliver(before_restart, "agent-reviewer").returncode, 0)
        self.assertEqual(self.deliver(after_restart, "agent-coordinator").returncode, 2)

    def test_the_coordinator_forward_from_another_sender_passes(self):
        land_ready = "LAND-READY pg-a18q.74 v1\npatch: /tmp/x.patch"
        self.assertEqual(self.deliver(self.session("agent-ios"), "agent-coordinator", land_ready).returncode, 0)
        self.assertEqual(self.deliver(self.session("agent-coordinator"), "agent-brain", land_ready).returncode, 0)

    def test_a_new_version_is_a_new_key(self):
        author = self.session("agent-ios")
        self.assertEqual(self.deliver(author, "agent-reviewer", "GO-REQ pg-208g v1").returncode, 0)
        self.assertEqual(self.deliver(author, "agent-coordinator", "GO-REQ pg-208g v2").returncode, 0)

    def test_a_malformed_line_one_passes(self):
        author = self.session("agent-ios")
        for message in ("go-req pg-208g", "GO-REQ", "GO-REQ pg-208g v2 extra", "Hi, GO-REQ pg-208g", "GO-REQ pg-208g 2", ""):
            with self.subTest(message=message):
                self.assertEqual(self.deliver(author, "agent-reviewer", message).returncode, 0)
                self.assertEqual(self.deliver(author, "agent-coordinator", message).returncode, 0)
        self.assertFalse(self.log.exists())

    def test_a_missing_or_non_string_message_passes(self):
        author = self.session("agent-ios")
        for tool_input in ({"to": "agent-reviewer"}, {"to": "agent-reviewer", "message": {"type": "x"}}):
            with self.subTest(tool_input=tool_input):
                self.assertEqual(self.deliver(author, None, tool_input=tool_input).returncode, 0)
        self.assertFalse(self.log.exists())

    def test_a_transcript_with_no_name_passes(self):
        nameless = self.transcript({"type": "user", "sessionId": "s1"}, {"type": "custom-title", "sessionId": "s1"})
        for transcript in (nameless, str(self.home / "missing.jsonl")):
            with self.subTest(transcript=transcript):
                self.assertEqual(self.deliver(transcript, "agent-reviewer").returncode, 0)
                self.assertEqual(self.deliver(transcript, "agent-coordinator").returncode, 0)
        self.assertFalse(self.log.exists())

    def test_a_missing_or_blank_tool_use_id_passes_and_writes_nothing(self):
        author = self.session("agent-ios")
        self.deliver(author, "agent-reviewer")
        events = ("PreToolUse", "PostToolUse", "PostToolUseFailure")
        for event, tool_use_id in itertools.product(events, (None, "", " ", 7)):
            with self.subTest(event=event, tool_use_id=tool_use_id):
                self.assertEqual(self.hook(event, author, "agent-coordinator", tool_use_id=tool_use_id).returncode, 0)
        self.assertEqual(self.logged(), [("pending", "agent-reviewer"), ("sent", "agent-reviewer")])

    def test_an_unwritable_or_unreadable_log_path_passes(self):
        # A dangling link as the log's folder: reading finds no log and writing cannot create one, even as root.
        dangling_folder = self.home / "gone"
        dangling_folder.symlink_to(self.home / "nowhere" / "deeper")
        author = self.session("agent-ios")
        events = ("PreToolUse", "PostToolUse", "PostToolUseFailure")
        for event, log in itertools.product(events, (dangling_folder / "sent.jsonl", self.home)):
            with self.subTest(event=event, log=log):
                self.assertEqual(self.hook(event, author, "agent-reviewer", log=log).returncode, 0)
                self.assertEqual(self.hook(event, author, "agent-coordinator", log=log).returncode, 0)

    def test_check_and_reserve_wait_for_the_log_lock(self):
        # Holding the lock stands in for a parallel send's hook: a PreToolUse that skips the lock finishes at once.
        self.log.parent.mkdir(parents=True)
        hook = json.dumps(self.hook_input("PreToolUse", self.session("agent-ios"), "agent-reviewer"))
        env = {**os.environ, "HOME": str(self.home), "AGENT_SENT_LOG": str(self.log)}
        with self.log.open("a", encoding="utf-8") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            guard = subprocess.Popen([sys.executable, str(GUARD)], stdin=subprocess.PIPE, env=env, text=True)
            guard.stdin.write(hook)
            guard.stdin.close()
            with self.assertRaises(subprocess.TimeoutExpired):
                guard.wait(timeout=1)
        self.assertEqual(guard.wait(timeout=10), 0)
        self.assertEqual(self.logged(), [("pending", "agent-reviewer")])

    def test_input_that_is_not_a_hook_passes(self):
        not_an_input = '{"hook_event_name": "%s", "tool_name": "SendMessage", "tool_use_id": "t", "tool_input": "x"}'
        events = ("PreToolUse", "PostToolUse", "PostToolUseFailure")
        for stdin in ("not json", "[]", *(not_an_input % event for event in events)):
            with self.subTest(stdin=stdin):
                self.assertEqual(self.run_guard(stdin).returncode, 0)

    def test_a_tool_other_than_send_message_passes(self):
        author = self.session("agent-ios")
        self.assertEqual(self.deliver(author, "agent-reviewer").returncode, 0)
        self.assertEqual(self.deliver(author, "agent-coordinator", tool="Bash").returncode, 0)
        self.assertEqual(self.logged(), [("pending", "agent-reviewer"), ("sent", "agent-reviewer")])

    def test_an_unknown_hook_event_passes_and_writes_nothing(self):
        author = self.session("agent-ios")
        self.deliver(author, "agent-reviewer")
        for event in ("Stop", "Notification", "pretooluse", "", None):
            with self.subTest(event=event):
                self.assertEqual(self.hook(event, author, "agent-coordinator").returncode, 0)
        self.assertEqual(self.logged(), [("pending", "agent-reviewer"), ("sent", "agent-reviewer")])

    def test_each_event_logs_its_state_with_sender_key_recipient_tool_use_id_and_time(self):
        author = self.session("agent-ios")
        for event in ("PreToolUse", "PostToolUse", "PostToolUseFailure"):
            self.hook(event, author, "agent-reviewer", tool_use_id="toolu_1")
        records = [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([record.pop("state") for record in records], ["pending", "sent", "failed"])
        for record in records:
            self.assertEqual(datetime.fromisoformat(record.pop("time")).tzinfo, UTC)
            self.assertEqual(
                record,
                {"sender": "agent-ios", "key": "GO-REQ pg-a18q.74 v1", "to": "agent-reviewer", "tool_use_id": "toolu_1"},
            )

    def test_the_last_name_record_names_the_session(self):
        lines = [json.dumps(named("agent-name", "old")), "{torn", json.dumps(named("custom-title", "agent-ios"))]
        self.assertEqual(session_name(lines), "agent-ios")

    def test_line_one_gives_type_bead_and_optional_version(self):
        self.assertEqual(event_key("GO-REQ pg-a18q.74 v3\npatch: x"), "GO-REQ pg-a18q.74 v3")
        self.assertEqual(event_key("LAND-READY pg-208g\r\nmessage: y"), "LAND-READY pg-208g")


if __name__ == "__main__":
    unittest.main()
