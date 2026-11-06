# python3 -m unittest discover -s tools -p 'test_message_rules.py': send_guard's body rules (mb-5558).
import json
import tempfile
import unittest
from pathlib import Path

from message_rules import content_problem, count_problem, relay_problem

ANDROID_SAYS = "LAND-READY mb-qhks.5 v1\ntest: unit 1012 passed, 0 failed, 0 skipped\nnext: the mutant run"


def transcript_with(*received: tuple[str, str]) -> str:
    entries = [{"type": "user", "message": {"content": (
        "Another Claude session sent a message:\n"
        f'<cross-session-message from="uds:/tmp/x.sock" from-name="{sender}" from-mode="bypass">\n{body}\n'
        "</cross-session-message>")}} for sender, body in received]
    path = Path(tempfile.mkdtemp()) / "transcript.jsonl"
    path.write_text("".join(json.dumps(entry) + "\n" for entry in [{"type": "start"}, *entries]))
    return str(path)


class CountRuleTest(unittest.TestCase):
    def test_a_result_with_no_number_is_refused(self):
        self.assertIn("no count", count_problem("RESULT mb-x\nall tests pass on the tree"))
        self.assertIn("no count", count_problem("android unit suite green"))

    def test_a_send_body_gets_the_count_rule(self):
        self.assertIn("no count", content_problem("RESULT mb-x\nall tests pass", None))

    def test_a_result_with_its_numbers_goes_through(self):
        self.assertIsNone(count_problem("RESULT mb-x\nunit tests passed: 1012 passed, 0 failed, 0 skipped"))

    def test_handing_something_over_is_not_a_result(self):
        self.assertIsNone(count_problem("The coordinator passed my request to the reviewer"))
        self.assertIsNone(count_problem("make the gate pass before you freeze it"))
        self.assertIsNone(count_problem("start the runs only if it passes"))
        self.assertIsNone(count_problem("both shot tests pass toApps now"))
        self.assertIsNone(count_problem("- check_security: all green"))


class RelayRuleTest(unittest.TestCase):
    def test_a_word_for_word_relay_goes_through(self):
        transcript = transcript_with(("agent-android", ANDROID_SAYS))
        self.assertIsNone(relay_problem(f"coordinator relay from agent-android:\n{ANDROID_SAYS}", transcript))

    def test_a_retold_line_is_refused_and_named(self):
        transcript = transcript_with(("agent-android", ANDROID_SAYS))
        problem = relay_problem("coordinator relay from agent-android:\nandroid says its 1010 tests are fine", transcript)
        self.assertIn("not in any message from agent-android", problem)

    def test_a_label_before_a_quoted_line_goes_through(self):
        transcript = transcript_with(("agent-android", ANDROID_SAYS))
        labelled = "coordinator relay from agent-android:\npart for brain: test: unit 1012 passed, 0 failed, 0 skipped"
        self.assertIsNone(relay_problem(labelled, transcript))

    def test_each_section_is_checked_against_its_own_author(self):
        transcript = transcript_with(("agent-android", ANDROID_SAYS), ("agent-ios", "SLOT-FREE brain-p1i2"))
        mixed = f"coordinator relay from agent-ios:\n{ANDROID_SAYS.splitlines()[1]}"
        self.assertIsNotNone(relay_problem(mixed, transcript))
        both = f"coordinator relay from agent-android:\n{ANDROID_SAYS}\n\ncoordinator relay from agent-ios:\nSLOT-FREE brain-p1i2"
        self.assertIsNone(relay_problem(both, transcript))

    def test_an_author_with_no_message_in_the_tail_is_not_checked(self):
        self.assertIsNone(relay_problem("coordinator relay from agent-design:\nanything", transcript_with()))

    def test_the_relayed_lines_skip_the_count_rule(self):
        transcript = transcript_with(("agent-ai", "checks green on the tree"))
        self.assertIsNone(content_problem("coordinator relay from agent-ai:\nchecks green on the tree", transcript))


if __name__ == "__main__":
    unittest.main()
