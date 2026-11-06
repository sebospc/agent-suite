import json
import os
import shutil
import tempfile
import unittest

from cockpit.hooks.hooks_view import hooks_view
from cockpit.hooks.settings_files import SettingsFiles
from tests.builders import HOUR, NOW


class HooksTest(unittest.TestCase):
    def test_every_hook_is_listed_with_what_its_log_says(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        settings = os.path.join(folder, "settings.json")
        with open(settings, "w") as handle:
            json.dump({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "python3 ~/tools/commit_guard.py"}]}],
                                 "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "python3 pick_account.py prompt-submit"}]}],
                                 "SessionStart": [{"hooks": [{"type": "command", "command": "python3 pick_account.py session-start"}]}]}}, handle)
        log = os.path.join(folder, "guard.jsonl")
        with open(log, "w") as handle:
            handle.write(json.dumps({"t": NOW - 60}) + "\n" + json.dumps({"t": NOW - 30 * HOUR}) + "\n"
                         + json.dumps({"time": "2026-10-15T23:00:00-0500"}) + "\n")
        shown = hooks_view(SettingsFiles([settings, os.path.join(folder, "missing.json")]), {"commit_guard": log}, NOW - HOUR, NOW)
        self.assertEqual([("commit_guard.py", ["PreToolUse (Bash)"]), ("pick_account.py", ["UserPromptSubmit", "SessionStart"])],
                         [(x["script"], x["events"]) for x in shown])
        self.assertEqual(2, len(shown[1]["commands"]))
        self.assertTrue(shown[0]["did"].startswith("2 today"), shown[0]["did"])
        self.assertEqual("writes no log the cockpit reads", shown[1]["did"])


class ScriptNameTest(unittest.TestCase):
    def test_the_script_is_named_not_the_last_shell_word(self):
        from cockpit.hooks.hooks_view import script_name
        self.assertEqual("session_state.py", script_name('python3 "$HOME/.agent-board/session_state.py"'))
        self.assertEqual("remote-settings-watch.sh", script_name('if [ -x ~/bin/remote-settings-watch.sh ]; then ~/bin/remote-settings-watch.sh "$1"; fi'))
        self.assertEqual("pick_account.py", script_name('python3 "$HOME/.claude/handoff/pick_account.py" session-start'))
        self.assertEqual("claude", script_name("claude --version"))
