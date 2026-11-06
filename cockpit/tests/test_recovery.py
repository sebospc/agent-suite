import json
import os
import shutil
import tempfile
import unittest
from dataclasses import replace

from cockpit.board.bead import Bead
from cockpit.compaction.recovery_book import RecoveryBook, recovery_by_kind, recovery_for
from cockpit.compaction.recovery_mix import RecoveryMix
from cockpit.compaction.sweet_spot import recovery_cost, sweet_spot
from cockpit.compaction.task_kind import bead_at, jev_category, kind_from_labels
from cockpit.transcripts.jsonl_transcripts import JsonlTranscripts
from cockpit.transcripts.recovery_span import RecoverySpan
from tests.builders import NOW, prices
from tests.test_sweet_spot import E1
from tests.test_transcripts import T0, assistant, iso

IDLE_GAP = 600


def bash(message_id, stamp, context, command):
    entry = assistant(message_id, stamp, context)
    entry["message"]["content"] = [{"type": "tool_use", "name": "Bash", "input": {"command": command}}]
    return entry


def boundary(stamp, pre=300_000):
    return {"type": "system", "subtype": "compact_boundary", "timestamp": iso(stamp),
            "compactMetadata": {"trigger": "auto", "preTokens": pre, "postTokens": 60_000}}


def span(tokens=10_000, requests=2):
    return RecoverySpan(fresh=0, write=0, read=tokens, out=0, requests=requests, ended_by="edit")


def mix(read, out=0, kind="docs", provisional=False):
    return RecoveryMix(fresh=0, write=0, read=read, out=out, compactions=5, kind=kind, provisional=provisional)


def held(id, labels=(), started=NOW - 1000, closed=None, assignee="agent-ios", issue_type="task"):
    return Bead(id=id, title=id, status="in_progress", priority=1, issue_type=issue_type, assignee=assignee, labels=list(labels),
                parent=None, related=[], updated_at=None, started_at=started, closed_at=closed)


class SpanBoundsTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "proj"))
        self.addCleanup(shutil.rmtree, self.root)

    def recovered(self, *after, before=(assistant("m0", T0, 250_000),)):
        with open(os.path.join(self.root, "proj", "s1.jsonl"), "w") as handle:
            handle.writelines(json.dumps(e) + "\n" for e in list(before) + [boundary(T0 + 60)] + list(after))
        return JsonlTranscripts(self.root, 100_000, IDLE_GAP).stats(["s1"], T0 + 9000)["s1"].compactions[0].recovery

    def test_it_stops_at_the_first_edit_or_new_file_and_leaves_that_request_out(self):
        for tool in ("Edit", "Write"):
            found = self.recovered(assistant("a", T0 + 90, 60_000, [("Read", "x.py")]), assistant("b", T0 + 120, 70_000),
                                   assistant("c", T0 + 150, 80_000, [(tool, "x.py")]))
            self.assertEqual((2, "edit", 60_000 + 70_000 + 600), (found.requests, found.ended_by, found.fresh + found.write + found.read + found.out))

    def test_it_stops_after_10_requests(self):
        found = self.recovered(*[assistant(f"r{i}", T0 + 90 + 30 * i, 60_000 + i) for i in range(14)])
        self.assertEqual((10, "10 requests"), (found.requests, found.ended_by))

    def test_it_stops_at_the_task_end(self):
        found = self.recovered(assistant("a", T0 + 90, 60_000), bash("b", T0 + 120, 61_000, "bd close pg-a1 --reason done"),
                               assistant("c", T0 + 150, 62_000))
        self.assertEqual((2, "task end"), (found.requests, found.ended_by))

    def test_it_stops_at_the_next_compaction(self):
        found = self.recovered(assistant("a", T0 + 90, 60_000), boundary(T0 + 100, pre=61_000), assistant("b", T0 + 130, 40_000))
        self.assertEqual((1, "next compaction"), (found.requests, found.ended_by))

    def test_an_idle_gap_ends_the_span_so_the_next_tasks_reads_are_not_recovery(self):
        found = self.recovered(assistant("a", T0 + 90, 60_000), assistant("b", T0 + 90 + IDLE_GAP + 60, 61_000),
                               assistant("c", T0 + IDLE_GAP + 200, 62_000), assistant("d", T0 + IDLE_GAP + 230, 63_000, [("Edit", "x")]))
        self.assertEqual((1, "idle gap"), (found.requests, found.ended_by))  # only a; b came after 11 idle minutes

    def test_the_first_gap_counts_from_the_compaction_not_the_last_turn_before_it(self):
        found = self.recovered(assistant("a", T0 + 90, 60_000), assistant("b", T0 + 120, 61_000, [("Edit", "x")]),
                               before=(assistant("m0", T0 - 3 * IDLE_GAP, 250_000),))
        self.assertEqual(1, found.requests)

    def test_a_span_the_transcript_has_not_finished_is_not_counted(self):
        self.assertIsNone(self.recovered(assistant("a", T0 + 90, 60_000), assistant("b", T0 + 120, 61_000)))


class KindTest(unittest.TestCase):
    def test_the_kind_is_the_task_labels_without_process_labels(self):
        self.assertEqual("ios+ui", kind_from_labels(held("pg-a", ["ui", "dod", "ios", "from:M4", "nice"])))
        self.assertIsNone(kind_from_labels(held("pg-a", ["dod"])))

    def test_jevs_category_is_its_surest_judgment_over_the_cut_off(self):
        self.assertEqual("wide reading", jev_category({"mechanical": 0.1, "wide_reading": 0.8, "deep_reasoning": 0.7}, 0.6))
        self.assertEqual("plain", jev_category({"mechanical": 0.3, "wide_reading": 0.5}, 0.6))

    def test_the_bead_held_at_the_compaction_decides_its_kind(self):
        beads = [held("pg-old", started=NOW - 5000, closed=NOW - 3000), held("pg-new", started=NOW - 2000),
                 held("pg-other", started=NOW - 1500, assignee="agent-android")]
        self.assertEqual("pg-old", bead_at(beads, "agent-ios", NOW - 4000).id)
        self.assertEqual("pg-new", bead_at(beads, "agent-ios", NOW).id)
        self.assertIsNone(bead_at(beads, "agent-ios", NOW - 2500))

    def test_jev_is_asked_only_for_unlabeled_beads_and_at_most_5_per_read(self):
        asked = []

        class Counting:
            def classify(self, bead_id, title, description):
                asked.append(bead_id)
                return {"probabilities": {"mechanical": 0.9, "deep_reasoning": 0.1, "needs_history": 0.1, "wide_reading": 0.1}}

        book = RecoveryBook()
        beads = [held("pg-l", ["docs"]), held("pg-e", issue_type="epic")] + [held(f"pg-{i}") for i in range(7)]
        self.assertEqual(5, book.learn(beads, Counting(), 0.6))
        self.assertEqual(["pg-0", "pg-1", "pg-2", "pg-3", "pg-4"], asked)
        self.assertEqual(("docs", "mechanical", "epic", None), tuple(book.kind_of(b) for b in (beads[0], beads[2], beads[1], beads[-1])))
        self.assertEqual("no bead", book.kind_of(None))


class KindMeanTest(unittest.TestCase):
    def test_each_kind_uses_its_last_20_compactions_only(self):
        entries = [(float(i), "docs", span(1_000_000 if i < 5 else 10_000)) for i in range(25)]
        by_kind, fleet = recovery_by_kind(entries)
        self.assertEqual((20, 10_000), (len(by_kind["docs"]), recovery_for("docs", by_kind, fleet, 3).read))

    def test_a_kind_with_too_few_uses_the_fleet_value_marked_provisional(self):
        entries = [(1.0, "docs", span(10_000)), (2.0, "ios", span(30_000)), (3.0, None, span(50_000))]
        by_kind, fleet = recovery_by_kind(entries)
        found = recovery_for("docs", by_kind, fleet, 3)
        self.assertEqual((True, "fleet", 3, 30_000), (found.provisional, found.kind, found.compactions, found.read))
        self.assertFalse(recovery_for("docs", by_kind, fleet, 1).provisional)
        self.assertIsNone(recovery_for("docs", {}, [], 3))


class RecoveryCostTest(unittest.TestCase):
    card = prices().card_for("claude-opus-5-5", 100_000)

    def test_r_is_the_span_at_list_price_minus_one_normal_turn_never_below_0(self):
        normal = E1.P + E1.g + E1.y
        self.assertEqual(0.0, recovery_cost(replace(E1, recovery=mix(read=E1.P)), self.card))
        heavy = recovery_cost(replace(E1, recovery=mix(read=4 * E1.P, out=E1.y)), self.card)
        self.assertAlmostEqual(self.card.at(0).cache_read * (4 * E1.P - E1.P) - self.card.at(0).write_1h * E1.g, heavy, places=6)
        self.assertGreater(normal, 0)

    def test_a_higher_recovery_cost_raises_the_sweet_spot(self):
        cheap = sweet_spot(replace(E1, recovery=mix(read=4 * E1.P)), self.card, None)
        dear = sweet_spot(replace(E1, recovery=mix(read=16 * E1.P)), self.card, None)
        self.assertGreater(cheap.trigger, sweet_spot(E1, self.card, None).trigger)
        self.assertGreater(dear.trigger, cheap.trigger)

    def test_haikus_grid_can_choose_over_100k_when_recovery_is_expensive(self):
        haiku = replace(E1, model="claude-haiku-5-5", P=50_000, F_s=30_000, S=10_000, g=2_000, g_p90=2_000, y=300)
        card = prices().card_for("claude-haiku-5-5", 100_000)
        self.assertLessEqual(sweet_spot(haiku, card, None).trigger, 100_000)
        # It takes a recovery far past the 10-request bound: the 5x step outweighs any realistic one.
        self.assertEqual(100_000, sweet_spot(replace(haiku, recovery=mix(read=10 * haiku.P)), card, None).trigger)
        self.assertGreater(sweet_spot(replace(haiku, recovery=mix(read=1000 * haiku.P, out=1_000_000)), card, None).trigger, 100_000)


if __name__ == "__main__":
    unittest.main()
