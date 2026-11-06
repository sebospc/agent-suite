import unittest

from cockpit.transcripts.own_words import excerpt, own_words
from cockpit.transcripts.transcript_file import TranscriptFile


def claims(text):
    """What the transcript reader takes from one reply."""
    file = TranscriptFile("/nonexistent")
    file.take({"type": "assistant", "timestamp": "2026-10-15T10:00:00Z",
               "message": {"id": "m", "model": "claude-opus-5-5", "usage": {"output_tokens": 1}, "content": [{"type": "text", "text": text}]}})
    return {"beads": [b for _, b in file.mentions], "ids": [(k, i) for _, k, i in file.ids], "saved_no_id": len(file.saved_without_id),
            "evidence": [(k, i, line) for _, k, i, line in file.evidence]}


class FalsePositiveTest(unittest.TestCase):
    def test_a_saved_claim_that_names_a_file_has_an_id(self):
        for text in ("Saved the plan as team.json and verified.json.", "I recorded the proposal in verified.json", "Saved to MEMORY.md"):
            self.assertEqual(0, claims(text)["saved_no_id"], text)
        self.assertEqual(1, claims("Done, saved.")["saved_no_id"])

    def test_saving_a_pid_or_a_backup_is_no_decision_claim(self):
        for text in ("248 tests pass. Restarting cockpit, saved pid only.", "Saved a backup first.", "Recorded the screenshot."):
            self.assertEqual(0, claims(text)["saved_no_id"], text)
        self.assertEqual(1, claims("Saved pidgin notes.")["saved_no_id"])

    def test_a_quoted_saved_is_not_the_sessions_claim(self):
        for text in ('The old message said "saved" with nothing else.', "> ios: saved the notes\nAll fine.", "```\nsaved the notes\n```\nAll fine.",
                     "The note says “recorded” and nothing more."):
            self.assertEqual(0, claims(text)["saved_no_id"], text)

    def test_an_id_in_quoted_text_is_not_named_by_the_session(self):
        for text in ("```\nbd show pg-xxxx\n```\nDone.", 'The log quotes "pg-zzzz closed" which is not ours.', "> pg-zzzz was closed\nOk."):
            self.assertEqual([], claims(text)["beads"], text)
        self.assertEqual(["pg-a18q.3"], claims("Closed pg-a18q.3 just now.")["beads"])
        self.assertEqual(["pg-a18q.3"], claims('He said "ok", then I closed `pg-a18q.3`.')["beads"])

    def test_words_made_of_hex_letters_are_not_ask_or_commit_ids(self):
        self.assertEqual([], claims("Compared ask decade and commit defaced with the old ones.")["ids"])
        self.assertEqual([("ask", "696253"), ("commit", "fc292bb")], claims("Answered ask 696253 and landed fc292bb.")["ids"])

    def test_saved_as_an_adjective_claims_no_save(self):
        for text in ("0 of 5,806 saved apps lost now.", "Checking 6152 saved engine apps.", "The real recorded mockup gets refused.",
                     "Now the saved-app test runs."):
            self.assertEqual(0, claims(text)["saved_no_id"], text)
        self.assertEqual(1, claims("Owner's words are saved. Next I send ai its task.")["saved_no_id"])
        self.assertEqual(1, claims("I saved the picks for the panel.")["saved_no_id"])

    def test_a_patch_sha_receipt_is_no_commit(self):
        self.assertEqual([], claims("Patch sha c26c4e65, receipt read-only (sha 3d8db354).")["ids"])
        self.assertEqual([("commit", "fc292bb")], claims("Landed fc292bb.")["ids"])

    def test_the_evidence_keeps_the_line_of_the_reply(self):
        got = claims("First line.\nI closed pg-gone and moved on.\nLast line.")
        self.assertEqual([("bead", "pg-gone", "I closed pg-gone and moved on.")], got["evidence"])
        self.assertEqual([("saved", "", "Saved it.")], claims("Intro.\nSaved it.")["evidence"])


class OwnWordsTest(unittest.TestCase):
    def test_quotes_are_blanked_without_moving_the_text(self):
        text = 'a "quoted pg-x" b\n> whole line\nlast ```code``` end'
        mine = own_words(text)
        self.assertEqual(len(text), len(mine))
        self.assertEqual("a", mine.splitlines()[0].strip()[0])
        self.assertNotIn("quoted", mine)
        self.assertNotIn("whole", mine)
        self.assertNotIn("code", mine)

    def test_a_long_line_is_cut_around_the_match(self):
        line = "x" * 300 + " pg-here " + "y" * 300
        cut = excerpt(line, line.index("pg-here"))
        self.assertIn("pg-here", cut)
        self.assertLess(len(cut), 150)


if __name__ == "__main__":
    unittest.main()
