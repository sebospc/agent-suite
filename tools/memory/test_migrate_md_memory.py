import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import migrate_md_memory as migrate


def memory_folder():
    folder = Path(tempfile.mkdtemp())
    (folder / "MEMORY.md").write_text("## Start here\n- [Rule](feedback_one_rule.md)\n## Later\n- [Ref](reference_tool.md)\n")
    (folder / "feedback_one_rule.md").write_text('---\nname: one-rule\ndescription: "Always do X"\ntype: feedback\n---\nBody.\n')
    (folder / "reference_tool.md").write_text("---\ndescription: Tool notes\ntype: reference\n---\nNotes.\n")
    (folder / "project_ios_state.md").write_text("---\ndescription: ios state\ntype: project\n---\nHolds t-1.\n")
    (folder / "project_old_state.md").write_text("---\ndescription: old state\ntype: project\n---\nPaused.\n")
    (folder / "feedback_dup.md").write_text("---\ndescription: dup\ntype: feedback\n---\nSecond copy.\n")
    return folder


class MigrateTest(unittest.TestCase):
    def test_kinds_keys_pins_archives_and_merges(self):
        found = {item["topic_key"]: item for item in migrate.observations(
            memory_folder(), "p", ("Start here",), ("old",), {"feedback_dup.md": "feedback_one_rule.md"}, "now")}
        self.assertEqual(["archive/role/old/state", "ref/tool", "role/ios/state", "rule/one-rule"], sorted(found))
        rule = found["rule/one-rule"]
        self.assertEqual(("learning", "Always do X", True), (rule["type"], rule["title"], rule["pinned"]))
        self.assertIn("Second copy.", rule["content"])
        self.assertFalse(found["ref/tool"]["pinned"])
        self.assertEqual("config", found["ref/tool"]["type"])


if __name__ == "__main__":
    unittest.main()
