import unittest

from cockpit.asks.asks_view import answered_today, asks_view, owner_beads_without_ask
from cockpit.asks.fake_asks import FakeAsks
from cockpit.grill.fake_grill import FakeGrill
from cockpit.grill.questions import NO_REC, owner_words, question_for
from cockpit.grill.round_keeper import RoundKeeper
from cockpit.milestone.criteria import Criteria
from cockpit.source_unavailable import SourceUnavailable
from cockpit.milestone.tree import BeadTree
from tests.builders import NOW, bead, milestone

ASK = {"id": "696253", "text": "Approve this coverage?", "options": ["Approve this coverage", "Change something (say what)"],
       "kind": "design", "by": "agent-format", "bead": "pg-b8j2", "reply": "reviewer-2 GO",
       "coverage": {"covered": ["who wins"], "fixed": ["ties show every name"]}}


class QuestionsTest(unittest.TestCase):
    def test_an_ask_becomes_a_question_with_lettered_options(self):
        question = question_for(dict(ASK, rec={"option": "A", "why": "covered with defaults"}))
        self.assertEqual("ask-696253", question["id"])
        self.assertEqual([{"k": "A", "text": "Approve this coverage"}, {"k": "B", "text": "Change something (say what)"}], question["options"])
        self.assertEqual({"option": "A", "why": "covered with defaults"}, question["rec"])
        self.assertIn("Covered: who wins", question["body"])

    def test_an_ask_without_a_recommendation_says_so(self):
        self.assertEqual(NO_REC, question_for(ASK)["rec"])

    def test_the_owners_words_are_the_option_text_or_what_they_typed(self):
        self.assertEqual("Change something (say what)", owner_words({"kind": "option", "option": "B"}, ASK))
        self.assertEqual("only the default", owner_words({"kind": "text", "text": " only the default "}, ASK))
        self.assertEqual("Approve this coverage", owner_words({"kind": "accept"}, dict(ASK, rec={"option": "A"})))
        self.assertIsNone(owner_words({"kind": "option", "option": "C"}, ASK))


class RoundKeeperTest(unittest.TestCase):
    def setUp(self):
        self.asks = FakeAsks([ASK], [])
        self.grill = FakeGrill()
        self.keeper = RoundKeeper(self.grill, self.asks, "/tmp/doc.md", lambda line: None)
        self.keeper.start()

    def send(self, seq, *actions):
        self.grill.sends[self.keeper.session].append({"type": "send", "seq": seq, "at": "2026-10-16T00:00:00Z", "actions": list(actions)})
        self.keeper.handle_sends()

    def test_a_picked_option_answers_the_ask_in_the_owners_words(self):
        self.send(1, {"q": "ask-696253", "type": "answer", "kind": "option", "option": "A"})
        self.assertEqual([], self.asks.open_asks)
        self.assertEqual("Approve this coverage", self.asks.answered[-1]["answer"])
        last = self.grill.patches[self.keeper.session][-1]
        self.assertEqual("answered", last["questions"][0]["status"])
        self.assertEqual(1, last["agent"]["handled"])

    def test_a_thread_message_goes_to_the_session_that_asked(self):
        sent = []
        self.keeper.forward = lambda ask, text: sent.append((ask["by"], text)) or "Sent to format; its reply is in its pane."
        self.send(1, {"q": "ask-696253", "type": "thread", "text": "what about golf?"})
        thread = self.grill.patches[self.keeper.session][-1]["questions"][0]["thread"]
        self.assertEqual(("what about golf?", "Sent to format; its reply is in its pane."), (thread[0]["text"], thread[1]["text"]))
        self.assertEqual([("agent-format", "what about golf?")], sent)
        self.assertEqual(1, len(self.asks.open_asks))

    def test_an_ask_is_answered_in_its_row_by_option_or_own_words(self):
        self.assertEqual("Change something (say what)", self.keeper.answer_one("696253", "B", ""))
        self.asks.open_asks.append(ASK)
        self.assertEqual("keep only the default", self.keeper.answer_one("696253", "A", " keep only the default "))  # words win
        with self.assertRaises(SourceUnavailable):
            self.keeper.answer_one("696253", "", "")

    def test_an_answer_to_an_ask_closed_elsewhere_is_kept_not_refused(self):
        self.keeper.answer_one("696253", "A", "")
        self.assertEqual("show me both", self.keeper.answer_one("696253", "", "show me both"))
        self.assertEqual("Approve this coverage", self.asks.answered[-1]["answer"])  # the panel keeps its first answer
        self.assertIn("the owner's new words: show me both", self.keeper.results[-1])
        with self.assertRaises(SourceUnavailable):
            self.keeper.answer_one("000000", "A", "")

    def test_a_round_holds_only_the_ticked_asks(self):
        other = dict(ASK, id="4c9041", text="Show it at once?")
        keeper = RoundKeeper(self.grill, FakeAsks([ASK, other], []), "/tmp/doc.md", lambda line: None)
        keeper.start(["4c9041"])
        questions = self.grill.patches[keeper.session][0]["questions"]
        self.assertEqual(["ask-4c9041"], [q["id"] for q in questions])
        with self.assertRaises(SourceUnavailable):
            keeper.start(["gone"])

    def test_a_send_is_handled_once(self):
        self.send(1, {"q": "ask-696253", "type": "answer", "kind": "option", "option": "A"})
        self.keeper.handle_sends()
        self.assertEqual(1, len(self.asks.answered))


class AsksViewTest(unittest.TestCase):
    def test_the_log_holds_todays_answers_newest_first(self):
        answered = [{"id": "a1", "answer": "yes", "answeredAt": "2026-10-16T01:00:00+00:00"},
                    {"id": "a2", "answer": "no", "answeredAt": "2026-10-16T03:00:00+00:00"},
                    {"id": "old", "answer": "x", "answeredAt": "2026-10-14T03:00:00+00:00"}, {"id": "none"}]
        since = NOW - 6 * 3600  # 2026-10-15 17:05 -05:00, before both
        self.assertEqual([("a2", "no"), ("a1", "yes")], [(a["id"], a["answer"]) for a in answered_today(answered, since)])

    def test_beads_that_wait_on_the_owner_without_an_ask(self):
        tree = BeadTree([milestone(), bead("pg-c1", parent="pg-m4", title="Owner approves the app"),
                         bead("pg-c2", "blocked", parent="pg-m4"), bead("pg-o", assignee="owner")])
        criteria = Criteria(tree, tree.by_id["pg-m4"], {"milestones": {"pg-m4": {"dod": ["pg-c1", "pg-c2"]}}}, [])
        waiting = owner_beads_without_ask(tree, criteria, [{"id": "a", "bead": "pg-c2"}])
        self.assertEqual(["pg-c1", "pg-o"], [b.id for b in waiting])
        view = asks_view([ASK], waiting, NOW, "panel.json")
        self.assertEqual("1 question, 2 tickets", view["summary"])
        self.assertEqual(["a done criterion that waits for your approval", "assigned to you"],
                         [r["meta"].split(" · ")[0] for r in view["rows"][1:]])
        self.assertEqual(1, view["askable"])


if __name__ == "__main__":
    unittest.main()
