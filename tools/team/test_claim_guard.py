# python3 -m unittest discover -s tools -p 'test_claim_guard.py': the Stop hook for unnamed claims (mb-5558).
import json
import subprocess
import sys
import unittest
from pathlib import Path

from claim_guard import verdict


def turn(reply: str) -> list:
    return [{"type": "user", "message": {"content": "status?"}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": reply}]}}]


class ClaimGuardTest(unittest.TestCase):
    def test_a_claim_with_nothing_named_is_held(self):
        self.assertIn("names no sha", verdict(turn("Landed. I saved the rule to memory too.")))
        self.assertIn("names no sha", verdict(turn("Both checks are done: it has landed.")))

    def test_the_word_as_an_adjective_is_no_claim(self):
        self.assertIsNone(verdict(turn("A walk that passes is saved, and I checked the landed commit.")))

    def test_a_claim_that_names_a_sha_a_bead_or_a_file_goes_through(self):
        self.assertIsNone(verdict(turn("Landed in 89300a9a5.")))
        self.assertIsNone(verdict(turn("Saved on bead mb-qhks.5.")))
        self.assertIsNone(verdict(turn("Saved to ~/Documents/project-calibration/PLAN.md.")))

    def test_a_reply_with_no_claim_goes_through(self):
        self.assertIsNone(verdict(turn("The reviewer is still reading phase 2.")))

    def test_only_the_last_turn_counts(self):
        entries = turn("It landed.") + turn("Waiting on the reviewer.")
        self.assertIsNone(verdict(entries))

    def test_a_transcript_it_cannot_read_lets_the_reply_through(self):
        guard = Path(__file__).with_name("claim_guard.py")
        done = subprocess.run([sys.executable, str(guard)], input=json.dumps({"transcript_path": "/no/such/file"}),
                              capture_output=True, text=True, check=False)
        self.assertEqual((done.returncode, done.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
