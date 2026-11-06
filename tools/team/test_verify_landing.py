import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from verify_landing import problems


def run(*args: str, cwd: Path) -> str:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


class VerifyLandingTest(unittest.TestCase):
    def setUp(self):
        # A caller's GIT_DIR or GIT_INDEX_FILE would point these git commands at another repo.
        self.saved_env = {k: os.environ.pop(k) for k in list(os.environ) if k.startswith("GIT_")}
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.old_cwd = os.getcwd()
        os.chdir(self.repo)
        run("git", "init", "-q", cwd=self.repo)
        run("git", "config", "user.email", "t@example.com", cwd=self.repo)
        run("git", "config", "user.name", "t", cwd=self.repo)
        (self.repo / "a.txt").write_text("one\n")
        run("git", "add", "a.txt", cwd=self.repo)
        run("git", "commit", "-q", "-m", "base", cwd=self.repo)
        (self.repo / "a.txt").write_text("one\ntwo\n")
        self.patch = self.repo.parent / f"{self.repo.name}.patch"
        self.patch.write_text(run("git", "diff", cwd=self.repo) + "\n")
        self.message = self.repo.parent / f"{self.repo.name}.msg"
        self.message.write_text("Add the second line\n")
        run("git", "commit", "-q", "-am", "Add the second line", cwd=self.repo)
        self.sha = run("git", "rev-parse", "HEAD", cwd=self.repo)
        self.tree = run("git", "rev-parse", "HEAD^{tree}", cwd=self.repo)
        run("git", "branch", "develop", cwd=self.repo)

    def tearDown(self):
        os.environ.update(self.saved_env)
        os.chdir(self.old_cwd)
        self.patch.unlink()
        self.message.unlink()
        self.tmp.cleanup()

    def test_the_landed_commit_of_the_frozen_patch_is_verified(self):
        self.assertEqual([], problems(self.sha, self.tree, self.message, self.patch, "develop"))

    def test_a_tree_other_than_the_go_tree_is_named(self):
        self.assertIn("is not the GO tree", " ".join(problems(self.sha, "0" * 40, self.message, self.patch, "develop")))

    def test_a_go_tree_shorter_than_8_hex_characters_is_named(self):
        for short in ("", self.tree[:1]):
            self.assertIn("is not 8 to 40 hex characters", " ".join(problems(self.sha, short, self.message, self.patch, "develop")))

    def test_a_message_other_than_the_frozen_file_is_named(self):
        self.message.write_text("Something else\n")
        self.assertIn("commit message differs", " ".join(problems(self.sha, self.tree, self.message, self.patch, "develop")))

    def test_a_message_with_one_more_trailing_newline_is_named(self):
        self.message.write_text("Add the second line\n\n")
        self.assertIn("commit message differs", " ".join(problems(self.sha, self.tree, self.message, self.patch, "develop")))

    def test_an_empty_frozen_patch_is_named(self):
        self.patch.write_text("")
        self.assertIn("no patch-id", " ".join(problems(self.sha, self.tree, self.message, self.patch, "develop")))

    def test_a_patch_other_than_the_frozen_one_is_named(self):
        self.patch.write_text(self.patch.read_text().replace("+two", "+three"))
        self.assertIn("patch-id", " ".join(problems(self.sha, self.tree, self.message, self.patch, "develop")))

    def test_a_commit_not_on_the_branch_is_named(self):
        run("git", "branch", "-f", "develop", "HEAD~1", cwd=self.repo)
        self.assertIn("is not on develop", " ".join(problems(self.sha, self.tree, self.message, self.patch, "develop")))


if __name__ == "__main__":
    unittest.main()
