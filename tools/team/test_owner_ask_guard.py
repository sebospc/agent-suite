import json
import tempfile
import unittest

from owner_ask_guard import panel_ids, verdict

ON_PANEL = {"ea59fb"}


def owner(text):
    return {"type": "user", "message": {"content": text}}


def reply(text, *commands):
    content = [{"type": "tool_use", "name": "Bash", "input": {"command": command}} for command in commands]
    return {"type": "assistant", "message": {"content": content + [{"type": "text", "text": text}]}}


class OwnerAskGuardTest(unittest.TestCase):
    def test_question_to_the_owner_off_the_panel_is_blocked(self):
        self.assertIsNotNone(verdict([owner("how is it going"), reply("Should workers move to 200k?")], ON_PANEL))

    def test_owner_decision_phrase_without_question_mark_is_blocked(self):
        self.assertIsNotNone(verdict([owner("status"), reply("Moving workers is your call.")], ON_PANEL))

    def test_question_in_an_earlier_text_of_the_turn_is_blocked(self):
        turn = [owner("status"), reply("Should workers move to standard Opus?"), reply("Gate is running.")]
        self.assertIsNotNone(verdict(turn, ON_PANEL))

    def test_question_added_to_the_panel_in_the_turn_passes(self):
        turn = [owner("status"), reply("Should workers move?", "python3 ~/.agent-board/ask_owner.py add 'x'")]
        self.assertIsNone(verdict(turn, ON_PANEL))

    def test_a_grep_for_the_ask_tool_is_not_an_ask(self):
        turn = [owner("status"), reply("Should workers move?", "grep -n 'ask_owner.py add' notes.md")]
        self.assertIsNotNone(verdict(turn, ON_PANEL))

    def test_reply_naming_an_ask_on_the_panel_passes(self):
        self.assertIsNone(verdict([owner("status"), reply("Should workers move? On the panel as ask ea59fb.")], ON_PANEL))

    def test_reply_naming_an_ask_that_does_not_exist_is_blocked(self):
        self.assertIsNotNone(verdict([owner("status"), reply("Should workers move? See ask abcdef.")], ON_PANEL))

    def test_question_inside_code_is_not_an_ask(self):
        self.assertIsNone(verdict([owner("status"), reply("Run `ready?` to check.")], ON_PANEL))

    def test_turns_started_by_peers_or_notices_are_not_checked(self):
        for start in ("Another Claude session sent a message:\n<cross-session-message from=x>GO?",
                      "[Cross-session idle notice] agent-ai is idle"):
            self.assertIsNone(verdict([owner(start), reply("Which one should I land?")], ON_PANEL))

    def test_saying_a_step_needs_the_owners_yes_later_is_not_an_ask(self):
        # A plain statement blocked here made the session send its reply twice (owner, 2026-10-31).
        self.assertIsNone(verdict([owner("status"), reply("The repo comes after the store build and needs your yes then.")], ON_PANEL))

    def test_a_request_worded_as_a_command_is_blocked(self):
        for text in ("Next: reply yes if I should write the rule.", "Next: run `sudo kill 554` in a Terminal.",
                     "Reply \"crea el ticket\" if you want it filed.", "Tell me whether to restart it."):
            self.assertIsNotNone(verdict([owner("status"), reply(text)], ON_PANEL), text)

    def test_a_command_request_naming_its_panel_ask_passes(self):
        self.assertIsNone(verdict([owner("status"), reply("Next: answer panel ea59fb, A or B.")], ON_PANEL))

    def test_reply_with_no_question_passes(self):
        self.assertIsNone(verdict([owner("status"), reply("Pushed 4e55977f.")], ON_PANEL))

    def test_panel_ids_reads_open_and_answered_asks(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as panel:
            json.dump({"asks": [{"id": "aaaaaa"}], "answered": [{"id": "bbbbbb"}, {"text": "before ids"}]}, panel)
        self.assertEqual(panel_ids(panel.name), {"aaaaaa", "bbbbbb"})


if __name__ == "__main__":
    unittest.main()
