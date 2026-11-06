import json
import os
import tempfile
import unittest

from cockpit.source_unavailable import SourceUnavailable
from cockpit.window_settings.account_settings_files import AccountSettingsFiles


class AccountSettingsFilesTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.profiles = os.path.join(self.home, "sessions")
        self.default = os.path.join(self.home, "claude", "settings.json")

    def write(self, path, settings):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(settings if isinstance(settings, str) else json.dumps(settings))

    def test_each_account_reads_its_own_settings_folder(self):
        self.write(os.path.join(self.profiles, "1-a@x.com", "settings.json"),
                   {"modelSettings": {"claude-opus-5-5": {"autoCompactWindow": 1_000_000}}})
        self.write(os.path.join(self.profiles, "12-b@x.com", "settings.json"),
                   {"modelSettings": {"claude-opus-5-5": {"autoCompactWindow": 200_000}}})
        self.write(self.default, {"modelSettings": {"claude-sonnet-5-5": {"autoCompactWindow": 500_000}}})
        files = AccountSettingsFiles(self.profiles, self.default)
        self.assertEqual(1_000_000, files.window("1", "claude-opus-5-5"))
        self.assertEqual(200_000, files.window("12", "claude-opus-5-5"))
        self.assertEqual(500_000, files.window("default", "claude-sonnet-5-5"))
        self.assertIsNone(files.window("1", "claude-sonnet-5-5"))
        self.assertIsNone(files.window("3", "claude-opus-5-5"))

    def test_an_unreadable_file_is_named(self):
        self.write(os.path.join(self.profiles, "1-a@x.com", "settings.json"), "{not json")
        with self.assertRaises(SourceUnavailable):
            AccountSettingsFiles(self.profiles, self.default).window("1", "claude-opus-5-5")


if __name__ == "__main__":
    unittest.main()
