import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import doctor
import install_team

PROJECT_SETTINGS = b'{\n    "permissions": {"allow": ["Bash(ls)"]},\n    "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "mine.sh"}]}]}\n}\n'


def project(parts, settings=PROJECT_SETTINGS, extra=None):
    folder = Path(tempfile.mkdtemp())
    (folder / ".agent-suite.json").write_text(json.dumps({"parts": parts, **(extra or {})}))
    if settings is not None:
        (folder / ".claude").mkdir()
        (folder / ".claude" / "settings.json").write_bytes(settings)
    return folder


def settings_of(folder):
    return json.loads((folder / ".claude" / "settings.json").read_text())


class InstallTeamTest(unittest.TestCase):
    def test_install_wraps_the_chosen_hooks_and_a_second_run_changes_nothing(self):
        folder = project({"panel": "as-is", "messages": "skip", "saved-guard": "adapted"})
        self.assertIn("installed 3 hooks", install_team.install(folder))
        first = (folder / ".claude" / "settings.json").read_bytes()
        self.assertIn("nothing changed", install_team.install(folder))
        self.assertEqual(first, (folder / ".claude" / "settings.json").read_bytes())
        stop = settings_of(folder)["hooks"]["Stop"]
        self.assertEqual("mine.sh", stop[0]["hooks"][0]["command"])
        self.assertEqual(3, len(stop))
        self.assertNotIn("SendMessage", json.dumps(settings_of(folder)))

    def test_uninstall_restores_the_original_byte_for_byte(self):
        folder = project({"panel": "as-is", "queue": "as-is", "launcher": "as-is"})
        install_team.install(folder)
        self.assertIn("back to its original", install_team.uninstall(folder))
        self.assertEqual(PROJECT_SETTINGS, (folder / ".claude" / "settings.json").read_bytes())
        self.assertFalse((folder / ".claude" / ("settings.json" + install_team.BACKUP_SUFFIX)).exists())

    def test_a_changed_choice_swaps_only_the_suite_entries_and_uninstall_still_restores(self):
        folder = project({"panel": "as-is"})
        install_team.install(folder)
        (folder / ".agent-suite.json").write_text(json.dumps({"parts": {"panel": "skip", "pause": "as-is"}}))
        install_team.install(folder)
        commands = json.dumps(settings_of(folder))
        self.assertIn("pause_guard.py", commands)
        self.assertNotIn("owner_ask_guard.py", commands)
        install_team.uninstall(folder)
        self.assertEqual(PROJECT_SETTINGS, (folder / ".claude" / "settings.json").read_bytes())

    def test_with_no_settings_before_uninstall_removes_the_file_again(self):
        folder = project({"saved-guard": "as-is"}, settings=None)
        install_team.install(folder)
        self.assertIn("gone again", install_team.uninstall(folder))
        self.assertFalse((folder / ".claude" / "settings.json").exists())

    def test_the_pause_hook_is_left_to_the_cockpit_when_both_are_chosen(self):
        hooks = install_team.wanted_hooks({"pause": "as-is", "cockpit": "as-is"})
        self.assertEqual([], hooks)

    def test_unknown_parts_or_choices_stop_before_anything_is_written(self):
        with self.assertRaisesRegex(install_team.InstallError, "unknown parts quue"):
            install_team.install(project({"quue": "as-is"}))
        with self.assertRaisesRegex(install_team.InstallError, "not: panel"):
            install_team.install(project({"panel": "yes"}))


class DoctorTest(unittest.TestCase):
    def test_missing_bins_needed_parts_config_and_hooks_are_problems_and_optional_ones_warn(self):
        folder = project({"team-check": "as-is", "snapshot": "as-is", "panel": "as-is"})
        lines = doctor.check(folder, which=lambda name: name in ("python3", "git", "rsync"), environ={})
        self.assertIn("team-check: bd is not on PATH", lines)
        self.assertIn("team-check: needs the queue part", lines)
        self.assertIn("snapshot: gitleaks is not on PATH", lines)
        self.assertIn("snapshot: snapshot.remote is not set", lines)
        self.assertIn("warn snapshot: bd is not on PATH (optional)", lines)
        self.assertTrue(any(line.startswith("missing: Stop") for line in lines))

    def test_a_complete_adoption_has_no_problems(self):
        folder = project({"slots": "as-is", "saved-guard": "as-is"}, extra={"slots": {"test-db": {}}})
        install_team.install(folder)
        self.assertEqual([], doctor.check(folder, which=lambda name: True, environ={}))


if __name__ == "__main__":
    unittest.main()
