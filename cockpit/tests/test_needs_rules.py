import unittest

from cockpit.display_time import clock_time
from cockpit.git.gate_state import GateState
from datetime import datetime, timezone

from cockpit.asks.asks_view import waiting_blockers
from cockpit.milestone.criteria import Criteria
from cockpit.milestone.tree import BeadTree
from cockpit.needs import rules
from cockpit.needs.needs_context import NeedsContext
from tests.builders import HOUR, NOW, bead, milestone, team, thresholds

DOD = {"milestones": {"pg-m4": {"dod": ["pg-c1", "pg-own"]}}}


def row(name, **fields):
    base = {"name": name, "state": "idle", "context": 150_000, "spot": 280_000, "over": False, "haiku_over_step": False,
            "can_compact": False, "why": "", "idle_for": "12 m", "notes_saved": True, "kind": "found", "tag": "",
            "model": "Opus 5.5", "spot_kind": "measured", "session_id": "", "account": ""}
    base.update(fields)
    return base


def context(beads=(), rows=(), asks=(), mentions=None, **extra):
    tree = BeadTree([milestone(), milestone("pg-m5", 5)] + list(beads))
    criteria = Criteria(tree, tree.by_id["pg-m4"], DOD, list(asks))
    return NeedsContext(rows=list(rows), tree=tree, criteria=criteria, open_asks=list(asks), mentions=mentions or {},
                        team=team(), thresholds=thresholds(autopilot_on=True), now=NOW, **extra)


def iso_ago(hours):
    return datetime.fromtimestamp(NOW - hours * HOUR, timezone.utc).isoformat()


class NeedsRulesTest(unittest.TestCase):
    def test_haiku_over_100k_is_a_warning_with_compact_when_allowed(self):
        found = rules.haiku_over_step(context(rows=[row("coordinator", haiku_over_step=True, context=118_000, can_compact=True)]))
        self.assertEqual(("warning", "control", "compact", "coordinator"), (found[0].level, found[0].action_kind, found[0].action_payload, found[0].target))

    def test_owner_criteria_without_an_ask_are_one_row(self):
        own = [bead(i, parent="pg-m4", assignee="agent-brain", title="Owner approves the finance app") for i in ("pg-c1", "pg-own")]
        found = rules.owner_criterion_without_ask(context(own))
        self.assertEqual(1, len(found))
        self.assertIn("pg-c1, pg-own wait on you", found[0].text)

    def test_off_milestone_work_tells_the_coordinator(self):
        found = rules.off_milestone(context([bead("pg-x", "in_progress", parent="pg-m5", assignee="agent-ai")]))
        self.assertEqual("warning", found[0].level)
        self.assertTrue(found[0].action_payload.startswith("coordinator: agent-ai holds pg-x (M5, P1)"))

    def test_an_owner_criterion_without_an_ask(self):
        own = bead("pg-own", parent="pg-m4", assignee="agent-brain", title="Owner approves the finance app")
        self.assertEqual(1, len(rules.owner_criterion_without_ask(context([own]))))
        self.assertEqual([], rules.owner_criterion_without_ask(context([own], asks=[{"id": "a1", "bead": "pg-own"}])))

    def test_a_stuck_bead_an_idle_session_or_one_over_its_sweet_spot_is_no_needs_you_row(self):
        # The nudger prompts idle sessions and the autopilot compacts (panel 7671bc), so neither asks the owner.
        stuck = bead("pg-s", "in_progress", parent="pg-m4", assignee="agent-ai", updated=NOW - 30 * HOUR)
        self.assertEqual([], [n for n in rules.needs_for(context([stuck])) if "pg-s" in n.text])
        quiet = [row("format", kind="idle"), row("ios", over=True, context=330_000, can_compact=True)]
        self.assertEqual([], rules.needs_for(context(rows=quiet)))

    def test_a_bead_named_in_a_reply_that_does_not_exist(self):
        named = {"beads": {"pg-ok", "pg-gone"}, "asks": {"696253", "abc123"}, "commits": {"deadbee", "c0ffee1"}, "saved": 2}
        found = rules.missing_id(context([bead("pg-ok")], mentions={"ios": named}, known_asks={"696253"}, known_commits={"c0ffee1"}))
        self.assertIn("named pg-gone, ask abc123, commit deadbee in a reply today", found[0].text)
        self.assertEqual(["missing-ios", "unsaved-ios"], [n.id for n in found])  # a saved claim with no id is not a missing id
        self.assertIn("said saved or recorded 2 times with no id", found[1].text)
        self.assertNotIn("pg-ok", found[0].text)
        unchecked = rules.missing_id(context([bead("pg-ok")], mentions={"ios": dict(named, saved=0)}, known_asks={"696253", "abc123"}))
        self.assertNotIn("commit", unchecked[0].text)  # git could not be asked: no sha is called missing

    def test_a_pg_name_is_its_mb_bead_from_the_patch_file_name(self):
        named = {"beads": {"pg-qhks.2", "pg-nope"}, "asks": set(), "commits": set(), "saved": 0}
        found = rules.missing_id(context([bead("mb-qhks.2")], mentions={"ios": named}))
        self.assertIn("named pg-nope in a reply", found[0].text)
        self.assertNotIn("qhks", found[0].text)

    def test_each_row_quotes_the_reply_line_and_time_of_the_id_it_names(self):
        line = "closed pg-gone and moved on"
        named = {"beads": {"pg-gone"}, "asks": set(), "commits": set(), "saved": 1,
                 "evidence": [(NOW - 60, "bead", "pg-gone", "older line pg-gone"), (NOW, "bead", "pg-gone", line), (NOW, "saved", "", "Saved the plan as team.json")]}
        found = rules.missing_id(context([bead("pg-ok")], mentions={"ios": named}))
        self.assertIn(f'pg-gone ("{line}", {clock_time(NOW)})', found[0].text)
        self.assertIn(f'with no id ("Saved the plan as team.json", {clock_time(NOW)})', found[1].text)

    def test_a_red_gate_names_its_commit_and_failing_count(self):
        found = rules.main_red(context(gate=GateState("abc1234", False, False, 3, 0, "gate_abc1234.log")))
        self.assertEqual(("warning", "Main is red: the gate on abc1234 failed with 3 failing tests."), (found[0].level, found[0].text))
        self.assertEqual([], rules.main_red(context(gate=GateState("abc1234", True, False, 0, 0, ""))))

    def test_a_stuck_bead_held_outside_the_team_is_named_in_team_rules(self):
        held = [bead("pg-x1", status="in_progress", parent="pg-m4", assignee="someone-else")]
        found = rules.team_rules_broken(context(held, stuck={"pg-x1": 14.2}))
        self.assertIn("someone-else, not a team session, holds 1 open (pg-x1), pg-x1 stuck 14 h", found[0].text)

    def test_a_blocker_ask_is_shown_only_in_your_asks(self):
        asks = [{"id": "b1", "kind": "blocker", "asked": iso_ago(0.01), "text": "x"}, {"id": "d1", "kind": "design", "asked": iso_ago(5)}]
        self.assertEqual([], [n for n in rules.needs_for(context(asks=asks)) if "b1" in n.text or "b1" in n.id])
        self.assertEqual(["b1"], [a["id"] for a in waiting_blockers(asks, 0, NOW)])  # it lights the Asks light at once

    def test_broken_team_rules_are_one_row_for_brain_and_none_when_they_hold(self):
        beads = [bead("pg-c1", parent="pg-m4"), bead("pg-f", "in_progress", parent="pg-m4", labels=["nice"]),
                 bead("pg-z", assignee="brain")]
        found = rules.team_rules_broken(context(beads))
        self.assertEqual(["team-rules"], [n.id for n in found])
        self.assertTrue(found[0].text.startswith("Team rules broken: found work pg-f links no done criterion; brain, not a team session"))
        self.assertEqual(("Tell brain", "copy", "brain"), (found[0].action_label, found[0].action_kind, found[0].target))
        self.assertEqual([], rules.team_rules_broken(context([bead("pg-c1", parent="pg-m4")])))

    def test_warnings_come_first(self):
        own = bead("pg-own", parent="pg-m4", assignee="agent-brain", title="Owner approves the finance app")
        ctx = context([own, bead("pg-x", "in_progress", parent="pg-m5", assignee="agent-ai")])
        self.assertEqual(["warning", "caution"], [n.level for n in rules.needs_for(ctx)][:2])


if __name__ == "__main__":
    unittest.main()
