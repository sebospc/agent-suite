import os
import subprocess
import tempfile
import unittest

from cockpit.git.git_cli import GitCli
from cockpit.snapshot.docs_age import docs_light, stale_docs
from tests.builders import NOW

DAY = 86400


class StaleDocsTest(unittest.TestCase):
    def test_a_doc_whose_named_code_moved_on_after_it_is_listed(self):
        texts = {"cockpit": {"docs/A.md": "See `cockpit/a.py`, cockpit/b.py and docs/B.md, not ghost/none.py.", "docs/B.md": "cockpit/a.py"}}
        changes = {"cockpit": {"docs/A.md": NOW - 30 * DAY, "cockpit/a.py": NOW - 2 * DAY, "cockpit/b.py": NOW - 28 * DAY,
                               "docs/B.md": NOW - 3 * DAY}}
        found = stale_docs(texts, changes, NOW - 90 * DAY, 7 * DAY)
        self.assertEqual([("docs/A.md", ["cockpit/a.py"])], [(d["doc"], [p for p, _ in d["newer"]]) for d in found])
        self.assertEqual(("watch", "1 behind"), tuple(docs_light(found, 7)[k] for k in ("level", "value")))
        unchanged = stale_docs({"cockpit": {"docs/C.md": "cockpit/a.py"}}, changes, NOW - 90 * DAY, 7 * DAY)
        self.assertEqual(1, len(unchanged))  # not changed in 90 days: counted from the window's start
        self.assertEqual("ok", docs_light([], 7)["level"])


class GitDocsTest(unittest.TestCase):
    def test_the_real_git_gives_each_paths_last_change_and_the_docs_but_the_skipped(self):
        with tempfile.TemporaryDirectory() as repo:
            def commit(path, text, days_ago):
                os.makedirs(os.path.dirname(os.path.join(repo, path)) or repo, exist_ok=True)
                with open(os.path.join(repo, path), "w") as handle:
                    handle.write(text)
                stamp = f"@{int(NOW - days_ago * DAY)} +0000"
                env = dict(os.environ, GIT_AUTHOR_DATE=stamp, GIT_COMMITTER_DATE=stamp, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                           GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
                subprocess.run(["git", "add", path], cwd=repo, check=True, env=env)
                subprocess.run(["git", "commit", "-qm", path], cwd=repo, check=True, env=env)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            commit("docs/A.md", "x/a.py", 20)
            commit("x/a.py", "1", 10)
            commit("x/a.py", "2", 5)
            commit("docs/DECISIONS.md", "x/a.py", 4)
            commit("docs/adr/0001-x.md", "x/a.py", 4)
            git = GitCli(repo, "HEAD", lambda: "", 10)
            name = os.path.basename(repo)
            changes = git.path_changes(3650)[name]
            self.assertEqual(round(NOW - 5 * DAY), round(changes["x/a.py"]))
            self.assertEqual({"docs/A.md"}, set(git.doc_texts(["docs/DECISIONS.md", "docs/adr/"])[name]))


if __name__ == "__main__":
    unittest.main()
