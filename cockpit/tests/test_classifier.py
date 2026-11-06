import os
import tempfile
import unittest

from cockpit.classifier.cached_classifier import CachedClassifier
from cockpit.classifier.fake_classifier import FakeClassifier
from cockpit.classifier.shadow import suggestions
from cockpit.milestone.tree import BeadTree
from cockpit.source_unavailable import SourceUnavailable
from cockpit.classifier.verdict_state import World
from tests.builders import NOW, bead, milestone


def session(deep=0.1, mechanical=0.1, wide=0.1, costly=0.1):
    return {"deep_reasoning": deep, "mechanical": mechanical, "wide_reading": wide, "mistake_costly": costly}


def next_bead(history=0.1, related=0.1, long=0.1):
    return {"needs_history": history, "related": related, "long": long}


def row(name, bead_id, **fields):
    base = {"name": name, "state": "idle", "bead": bead_id, "holds": 1, "model": "Opus 5.5", "effort": "high", "account": "3",
            "context": 120_000, "spot": 150_000, "cache_ttl": 3600, "last_turn_at": NOW - 600, "task_files": ["/repo/core/a.py"]}
    base.update(fields)
    return base


class ShadowTest(unittest.TestCase):
    def test_the_session_verdict_sets_the_model_from_its_role_and_all_its_work(self):
        tree = BeadTree([milestone(), bead("pg-a", "in_progress", parent="pg-m4", assignee="agent-ios"),
                         bead("pg-b", "in_progress", parent="pg-m4", assignee="agent-ai")])
        fake = FakeClassifier({"session ios": session(), "session ai": session(deep=0.7, wide=0.8)})
        found = suggestions([row("ios", "pg-a +1"), row("ai", "pg-b"), row("off", "pg-a", state="off"),
                             row("android", "pg-a", last_turn_at=None)], tree, fake)  # its transcript is not read yet
        self.assertEqual({"ios", "ai"}, set(found))
        self.assertEqual(("Sonnet 5.5", "medium", False, "pg-a"), (found["ios"]["model"], found["ios"]["effort"], found["ios"]["agrees"], found["ios"]["bead"]))
        self.assertEqual(("Opus 5.5", "high", True, "large", "Jev"),
                         (found["ai"]["model"], found["ai"]["effort"], found["ai"]["agrees"], found["ai"]["window"], found["ai"]["by"]))
        self.assertNotIn("start", found["ai"])  # it holds a bead: no bead verdict until its next one

    def test_a_mechanical_bead_held_by_brain_no_longer_puts_brain_on_haiku(self):
        # jev_record.jsonl, pg-z061: Jev's bead answer (mechanical 0.90) was applied to the whole session.
        tree = BeadTree([milestone(), bead("pg-z061", "in_progress", parent="pg-m4", assignee="agent-brain", labels=["mechanical"])])
        fake = FakeClassifier({"session brain": session(mechanical=0.9, costly=0.95)})
        world = World(roles={"brain": "lands commits, quotes the owner verbatim, coordinates"}, coordinating=frozenset({"brain"}))
        found = suggestions([row("brain", "pg-z061")], tree, fake, world=world, now=NOW)
        self.assertEqual("Opus 5.5", found["brain"]["model"])  # a costly mistake never runs on Haiku
        sent = fake.states["session brain"]["session"]
        self.assertEqual(("lands commits, quotes the owner verbatim, coordinates", True, ["pg-z061"]),
                         (sent["role"], sent["coordinates_the_team"], [b["id"] for b in sent["open_beads"]]))

    def test_a_role_session_with_no_bead_still_gets_its_session_verdict(self):
        found = suggestions([row("brain", "no bead", holds=0)], BeadTree([milestone()]), FakeClassifier({"session brain": session(deep=0.9)}))
        self.assertEqual(("Opus 5.5", "xhigh", "", False), (found["brain"]["model"], found["brain"]["effort"], found["brain"]["bead"], found["brain"]["next"]))

    def test_a_security_label_on_any_of_its_beads_floors_deep_reasoning(self):
        tree = BeadTree([milestone(), bead("pg-c", "in_progress", assignee="agent-ai"), bead("pg-d", assignee="agent-ai", labels=["security"])])
        found = suggestions([row("ai", "pg-c")], tree, FakeClassifier({"session ai": session(mechanical=0.9)}))
        self.assertEqual(("Opus 5.5", "xhigh"), (found["ai"]["model"], found["ai"]["effort"]))

    def test_between_tasks_the_bead_verdict_says_whether_its_next_bead_carries_the_context(self):
        done = bead("pg-old", "closed", assignee="agent-ios", title="Date parser")
        tree = BeadTree([milestone(), done, bead("pg-e", assignee="agent-ios", priority=2), bead("pg-f", assignee="agent-ios", priority=3)])
        fake = FakeClassifier({"session ios": session(), "bead ios pg-e": next_bead(related=0.8, long=0.7)})
        found = suggestions([row("ios", "no bead", holds=0)], tree, fake, world=World(turns={"ios": ((NOW, "asked", "TASK pg-old"),)}))
        s = found["ios"]
        self.assertEqual(("pg-e", True, False, True, True, "carry its context", "pg-old"),
                         (s["bead"], s["next"], s["needs_history"], s["related"], s["long"], s["start"], s["done_bead"]))
        sent = fake.states["bead ios pg-e"]
        self.assertEqual(("pg-e", "pg-old", [{"who": "asked", "text": "TASK pg-old"}]),
                         (sent["next_task"]["id"], sent["session"]["last_task"]["id"], sent["session"]["last_turns"]))
        unrelated = suggestions([row("ios", "no bead", holds=0)], tree, FakeClassifier({"session ios": session(), "bead ios pg-e": next_bead()}))
        self.assertEqual("fresh, after a clear", unrelated["ios"]["start"])

    def test_the_bead_of_an_arriving_task_is_the_one_judged(self):
        tree = BeadTree([milestone(), bead("pg-e", assignee="agent-ios", priority=2), bead("pg-g", assignee="agent-ios", priority=3)])
        fake = FakeClassifier({"session ios": session(), "bead ios pg-g": next_bead(history=0.9)})
        found = suggestions([row("ios", "no bead", holds=0)], tree, fake, arriving={"ios": "pg-g"})
        self.assertEqual(("pg-g", True), (found["ios"]["bead"], found["ios"]["needs_history"]))
        self.assertNotIn("bead ios pg-e", fake.asked)

    def test_a_parked_bead_is_never_the_next_bead(self):
        parked = bead("pg-28it", assignee="agent-format", priority=4, title="Parked: later idea")
        ready = bead("pg-e", assignee="agent-ios", priority=4)
        found = suggestions([row("format", "no bead", holds=0), row("ios", "no bead", holds=0)], BeadTree([milestone(), parked, ready]),
                            FakeClassifier({"session format": session(), "session ios": session(), "bead ios pg-e": next_bead()}))
        self.assertEqual({"format": "", "ios": "pg-e"}, {name: s["bead"] for name, s in found.items()})

    def test_jev_is_asked_again_only_when_its_role_beads_or_milestone_change(self):
        fake = FakeClassifier({"session ios": session()})
        cached = CachedClassifier(fake)
        tree = BeadTree([milestone(), bead("pg-a", "in_progress", assignee="agent-ios")])
        suggestions([row("ios", "pg-a")], tree, cached)
        suggestions([row("ios", "pg-a", context=180_000, last_turn_at=NOW)], tree, cached)  # cache and turns move every read
        self.assertEqual(1, len(fake.asked))
        suggestions([row("ios", "pg-a")], BeadTree([milestone(), bead("pg-a", "in_progress", assignee="agent-ios"),
                                                    bead("pg-b", assignee="agent-ios")]), cached)
        self.assertEqual(2, len(fake.asked))

    def test_a_bead_is_classified_once_per_version_of_its_text(self):
        fake = FakeClassifier({"pg-a": {"model": "m", "effort": "low"}})
        cached = CachedClassifier(fake)
        cached.classify("pg-a", "title", "text")
        cached.classify("pg-a", "title", "text")
        cached.classify("pg-a", "title", "text, edited")
        self.assertEqual(2, len(fake.asked))

    def test_a_restarted_cockpit_reads_the_stored_answers_instead_of_asking_jev_again(self):
        with tempfile.TemporaryDirectory() as folder:
            store = os.path.join(folder, "jev_answers.json")
            first = FakeClassifier({"pg-a": {"model": "m"}, "session ios": session()})
            CachedClassifier(first, store).classify("pg-a", "title", "text")
            CachedClassifier(first, store).judge("session ios", "v1", {"deep_reasoning": "?"}, {})
            restarted = FakeClassifier({"pg-a": {"model": "m"}, "session ios": session()})
            cached = CachedClassifier(restarted, store)
            self.assertEqual({"model": "m"}, cached.classify("pg-a", "title", "text"))
            cached.judge("session ios", "v1", {"deep_reasoning": "?"}, {})
            self.assertEqual(0, len(restarted.asked))
            cached.judge("session ios", "v2", {"deep_reasoning": "?"}, {})
            self.assertEqual(1, len(restarted.asked))


class OneRefusedBeadTest(unittest.TestCase):
    def test_a_bead_jev_refuses_hides_only_its_own_suggestion(self):
        class Refusing(FakeClassifier):
            def judge(self, key, version, questions, state):
                if key == "session ios":
                    raise SourceUnavailable("Jev answered 422")
                return super().judge(key, version, questions, state)
        tree = BeadTree([milestone(), bead("pg-a", "in_progress", parent="pg-m4"), bead("pg-b", "in_progress", parent="pg-m4")])
        found = suggestions([row("ios", "pg-a"), row("ai", "pg-b")], tree, Refusing({"session ai": session()}))
        self.assertEqual({"ai"}, set(found))
        with self.assertRaises(SourceUnavailable):
            suggestions([row("ios", "pg-a")], tree, Refusing({}))


if __name__ == "__main__":
    unittest.main()
