import unittest

from cockpit.milestone.criteria import Criteria
from cockpit.milestone.stuck import stuck_beads
from cockpit.milestone.team_rules import broken_team_rules
from cockpit.milestone.tree import BeadTree
from tests.builders import HOUR, NOW, bead, fixture_beads, fixture_json, milestone, team, thresholds

DOD = {"milestones": {"pg-m4": {"dod": ["pg-c1", "pg-c2"], "bar": "pg-c1"}}}


def broken(beads, **limits):
    tree = BeadTree([milestone(), milestone("pg-m5", 5)] + beads)
    return broken_team_rules(tree, Criteria(tree, tree.by_id["pg-m4"], DOD, []), team(), thresholds(**limits))


class TeamRulesTest(unittest.TestCase):
    def test_found_work_without_a_related_criterion_breaks_a_rule(self):
        beads = [bead("pg-c1", parent="pg-m4"), bead("pg-c2", parent="pg-m4"),
                 bead("pg-f1", "in_progress", parent="pg-m4", labels=["nice"]),
                 bead("pg-f2", "in_progress", parent="pg-m4", related=["pg-c2"])]
        self.assertEqual(["found work pg-f1 links no done criterion"], broken(beads))

    def test_a_worker_with_two_breaks_one_bead_while_brain_and_claude_cloud_are_exempt(self):
        beads = [bead(f"pg-{i}", "in_progress", parent="pg-m4", assignee=who)
                 for i, who in enumerate(["agent-ios", "agent-ios", "agent-brain", "agent-brain",
                                          "claude-cloud", "claude-cloud"])]
        self.assertEqual(["agent-ios holds 2 beads in progress (limit 1)"], broken(beads))  # the owner set this limit on Oct 16
        self.assertEqual([], broken(beads, beads_per_task_session=2))

    def test_a_holder_outside_the_team_list_breaks_a_rule_with_its_beads(self):
        self.assertEqual(["brain, not a team session, holds 1 open (pg-z)"],
                         broken([bead("pg-z", assignee="brain"), bead("pg-ok", assignee="claude-cloud")]))

    def test_the_oct_15_board_breaks_the_found_work_rule(self):
        tree = BeadTree(fixture_beads())
        criteria = Criteria(tree, tree.current_milestone(), fixture_json("dod.json"), fixture_json("panel.json")["asks"])
        self.assertTrue(any(line.startswith("found work") for line in broken_team_rules(tree, criteria, team(), thresholds())))


class StuckTest(unittest.TestCase):
    def test_a_bead_with_no_update_and_no_turn_by_its_holder_is_stuck(self):
        silent = [bead("pg-s", "in_progress", parent="pg-m4", assignee="agent-ai", updated=NOW - 13 * HOUR)]
        self.assertEqual(["pg-s"], list(stuck_beads(silent, {}, NOW, 12)))
        self.assertEqual({}, stuck_beads(silent, {}, NOW, 14))

    def test_a_comment_or_a_turn_by_the_holder_counts_as_work(self):
        commented = [bead("pg-s", "in_progress", parent="pg-m4", updated=NOW - 20 * HOUR, activity=[NOW - HOUR])]
        self.assertEqual({}, stuck_beads(commented, {}, NOW, 12))
        worked = [bead("pg-s", "in_progress", parent="pg-m4", assignee="agent-ai", updated=NOW - 20 * HOUR)]
        self.assertEqual({}, stuck_beads(worked, {"agent-ai": NOW - 2 * HOUR}, NOW, 12))


if __name__ == "__main__":
    unittest.main()
