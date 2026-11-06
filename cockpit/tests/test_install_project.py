import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.builders import FIRST_PROJECT

from tests.builders import ROOT

INSTALLER = os.path.join(ROOT, "tools", "install_project.py")
# Odd spacing, tabs and no final newline: a JSON rewrite could never give these bytes back, only the backup can.
ORIGINAL = (b'{\n\t"statusLine": {"type": "command", "command": "echo project line", "padding": 1},\n'
            b'\t"hooks": {"PreToolUse": [{"matcher": "Edit", "hooks": [{"type": "command", "command": "true"}]}]},\n'
            b'\t"permissions":   {"deny": []}\n}')


class InstallProjectTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home)
        self.project = os.path.join(self.home, "project")
        os.makedirs(os.path.join(self.project, ".claude"))
        self.settings = os.path.join(self.project, ".claude", "settings.json")
        self.backup = self.settings + ".cockpit-backup"
        with open(os.path.join(FIRST_PROJECT, ".cockpit.json"), encoding="utf-8") as handle:
            config = json.load(handle)
        config["paths"].update(usage=os.path.join(self.home, "usage.json"), pause_file=os.path.join(self.home, "paused"))
        self.write(os.path.join(self.project, ".cockpit.json"), json.dumps(config).encode())

    def write(self, path: str, content: bytes) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(content)

    def read(self, path: str) -> bytes:
        with open(path, "rb") as handle:
            return handle.read()

    def run_installer(self, action: str) -> str:
        done = subprocess.run([sys.executable, INSTALLER, action, self.project], capture_output=True, text=True,
                              env=dict(os.environ, HOME=self.home))
        self.assertEqual(0, done.returncode, done.stderr)
        return done.stdout

    def test_install_backs_up_wraps_and_a_second_install_changes_nothing(self):
        self.write(self.settings, ORIGINAL)
        self.run_installer("install")
        self.assertEqual(ORIGINAL, self.read(self.backup))
        installed = json.loads(self.read(self.settings))
        self.assertIn("bin/statusline.py", installed["statusLine"]["command"])
        self.assertTrue(installed["statusLine"]["command"].endswith("'echo project line'"))
        self.assertEqual(1, installed["statusLine"]["padding"])
        self.assertEqual(["Edit", "Bash"], [group["matcher"] for group in installed["hooks"]["PreToolUse"]])
        first = self.read(self.settings)
        self.assertIn("already installed", self.run_installer("install"))
        self.assertEqual((first, ORIGINAL), (self.read(self.settings), self.read(self.backup)))

    def test_uninstall_gives_back_the_byte_identical_original_and_drops_the_backup(self):
        self.write(self.settings, ORIGINAL)
        self.run_installer("install")
        self.run_installer("uninstall")
        self.assertEqual(ORIGINAL, self.read(self.settings))
        self.assertFalse(os.path.exists(self.backup))
        self.assertIn("not installed", self.run_installer("uninstall"))

    def test_without_project_settings_it_wraps_the_users_line_and_uninstall_removes_the_file(self):
        self.write(os.path.join(self.home, ".claude", "settings.json"), b'{"statusLine": {"type": "command", "command": "user line"}}')
        self.run_installer("install")
        self.assertTrue(json.loads(self.read(self.settings))["statusLine"]["command"].endswith("'user line'"))
        self.assertFalse(os.path.exists(self.backup))
        self.run_installer("uninstall")
        self.assertFalse(os.path.exists(self.settings))

    def test_a_change_made_after_the_install_survives_the_uninstall_and_the_backup_stays(self):
        self.write(self.settings, ORIGINAL)
        self.run_installer("install")
        changed = json.loads(self.read(self.settings))
        changed["model"] = "sonnet"
        self.write(self.settings, json.dumps(changed).encode())
        self.run_installer("uninstall")
        after = json.loads(self.read(self.settings))
        self.assertEqual(dict(json.loads(ORIGINAL), model="sonnet"), after)
        self.assertEqual(ORIGINAL, self.read(self.backup))


class CockpitHooksTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder)

    def run_bin(self, script: str, args, stdin: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, os.path.join(ROOT, "bin", script)] + args, input=stdin, capture_output=True, text=True)

    def test_the_status_line_saves_the_limits_and_prints_the_wrapped_line(self):
        usage = os.path.join(self.folder, "usage.json")
        shown = self.run_bin("statusline.py", [usage, "cat >/dev/null; echo my line"], json.dumps({"rate_limits": {"five_hour": {"used_percentage": 7}}}))
        self.assertEqual("my line\n", shown.stdout)
        with open(usage, encoding="utf-8") as handle:
            self.assertEqual(7, json.load(handle)["rate_limits"]["five_hour"]["used_percentage"])

    def test_the_pause_guard_blocks_a_push_only_while_paused(self):
        pause = os.path.join(self.folder, "paused")
        push = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git status && git push origin main"}})
        log = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git log; echo push"}})
        self.assertEqual(0, self.run_bin("pause_guard.py", [pause], push).returncode)
        open(pause, "w").close()
        self.assertEqual(2, self.run_bin("pause_guard.py", [pause], push).returncode)
        self.assertEqual(0, self.run_bin("pause_guard.py", [pause], log).returncode)


if __name__ == "__main__":
    unittest.main()
