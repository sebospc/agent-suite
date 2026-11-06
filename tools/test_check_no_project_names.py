import re
import unittest
from unittest import mock

import check_no_project_names as check


class LeaksTest(unittest.TestCase):
    def test_a_name_in_suite_code_is_found_and_project_data_is_skipped(self):
        files = {"tools/a.py": "x = 1\nACME rocks\n", "board/panel.json": "acme everywhere"}
        with mock.patch.object(check, "suite_files", return_value=[p for p in files if not p.startswith(check.PROJECT_DATA)]), \
                mock.patch.object(check.Path, "read_text", lambda self, **_: files[str(self.relative_to(check.ROOT))]):
            self.assertEqual(check.leaks(["acme"]), ["tools/a.py:2"])

    def test_names_are_matched_literally(self):
        self.assertIsNone(re.compile(re.escape("a.b")).search("axb"))


if __name__ == "__main__":
    unittest.main()
