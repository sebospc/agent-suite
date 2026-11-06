import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pause_guard


def bash(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}, "session_id": "s1"}


class PauseGuardTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.mkdtemp()
        self.pause_file = os.path.join(folder, "paused")
        self.log = os.path.join(folder, "denials.jsonl")
        with open(self.pause_file, "w") as pause:
            pause.write("1792180434")
        patches = [mock.patch.object(pause_guard, "PAUSE_FILE", self.pause_file),
                   mock.patch.object(pause_guard, "DENIAL_LOG", self.log)]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def run_hook(self, hook) -> int:
        stdin = hook if isinstance(hook, str) else json.dumps(hook)
        with mock.patch("sys.stdin", io.StringIO(stdin)), mock.patch("sys.stderr", new_callable=io.StringIO):
            return pause_guard.main()

    def logged_rules(self) -> list:
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as log:
            return [json.loads(line)["rule"] for line in log]

    def test_commit_and_push_are_denied_and_logged(self):
        for command in ("git commit -m x", "rtk proxy git push origin main", "git commit-tree abc -p def",
                        "cd repo && git update-ref refs/heads/stack-brain abc def"):
            with self.subTest(command=command):
                self.assertEqual(self.run_hook(bash(command)), 2)
        self.assertEqual(self.logged_rules(), ["commit or push"] * 4)

    def test_bead_claims_are_denied(self):
        for command in ("bd update pg-x --claim", "BEADS_ACTOR=a bd update pg-x --status in_progress",
                        "bd update pg-x -s in_progress", "bd claim pg-x"):
            with self.subTest(command=command):
                self.assertEqual(self.run_hook(bash(command)), 2)

    def test_cross_session_messages_are_denied(self):
        self.assertEqual(self.run_hook({"tool_name": "SendMessage", "tool_input": {"to": "x", "message": "hi"}}), 2)
        self.assertEqual(self.logged_rules(), ["cross-session message"])

    def test_device_runs_are_denied(self):
        for command in ("xcodebuild test -scheme the project", "./gradlew connectedDebugAndroidTest",
                        "adb -s emulator-5554 shell ls", "xcrun simctl boot X", "emulator -avd a35",
                        "bash tools/verify_commit.sh abc", "VERIFY_STEPS=\"ios style\" bash tools/verify_commit.sh abc"):
            with self.subTest(command=command):
                self.assertEqual(self.run_hook(bash(command)), 2)

    def test_model_runs_are_denied(self):
        for command in ("claude -p 'hi'", "kiro-cli chat", "cursor-agent run",
                        "cd ai && python3 -m evals.needs.run --llm claude-code", "python3 evals/generate_run.py"):
            with self.subTest(command=command):
                self.assertEqual(self.run_hook(bash(command)), 2)

    def test_reading_and_local_checks_pass(self):
        for command in ("git log --oneline -3", "git status", "bd show pg-x", "bd list --status in_progress",
                        "cd ai && python3 -m unittest discover -s tests/evals -t .",
                        "VERIFY_STEPS=\"ai backend style\" bash tools/verify_commit.sh abc",
                        "python3 tools/check_style.py", "git log; echo push"):
            with self.subTest(command=command):
                self.assertEqual(self.run_hook(bash(command)), 0)
        self.assertEqual(self.logged_rules(), [])

    def test_other_tools_pass(self):
        self.assertEqual(self.run_hook({"tool_name": "Read", "tool_input": {"file_path": "/x"}}), 0)

    def test_nothing_is_denied_without_the_pause_file(self):
        os.remove(self.pause_file)
        self.assertEqual(self.run_hook(bash("git push origin main")), 0)
        self.assertEqual(self.run_hook({"tool_name": "SendMessage", "tool_input": {}}), 0)

    def test_broken_input_fails_open(self):
        self.assertEqual(self.run_hook("not json"), 0)
        self.assertEqual(self.run_hook({"tool_name": "Bash", "tool_input": None}), 0)

    def test_an_unwritable_log_still_denies(self):
        with mock.patch.object(pause_guard, "DENIAL_LOG", "/nonexistent/dir/denials.jsonl"):
            self.assertEqual(self.run_hook(bash("git push")), 2)


if __name__ == "__main__":
    unittest.main()
