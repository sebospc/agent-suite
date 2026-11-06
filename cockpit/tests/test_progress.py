import unittest
from dataclasses import replace

from cockpit.milestone.criteria import Criteria
from cockpit.milestone.progress import closed_lately, pace, roadmap, workers
from cockpit.milestone.tree import BeadTree
from tests.builders import HOUR, NOW, bead, milestone, team

DOD = {"milestones": {"pg-m4": {"dod": ["pg-c1", "pg-c2"]}}}


def board(*beads):
    tree = BeadTree([milestone(), milestone("pg-m5", 5)] + list(beads))
    return tree, Criteria(tree, tree.by_id["pg-m4"], DOD, [])


class ProgressTest(unittest.TestCase):
    def test_workers_are_the_holders_moving_a_criterion_with_their_live_state(self):
        c1 = bead("pg-c1", "in_progress", parent="pg-m4", assignee="agent-ios")
        step = bead("pg-s", "in_progress", parent="pg-c1", assignee="agent-ai")
        tree, criteria = board(c1, step, bead("pg-c2", parent="pg-m4"))
        found = workers(c1, criteria, [c1, step], team(), {"ai": "busy"})
        self.assertEqual([{"name": "ai", "state": "busy"}, {"name": "ios", "state": "off"}], found)
        self.assertEqual([], workers(tree.by_id["pg-c2"], criteria, [c1, step], team(), {}))

    def test_pace_counts_closures_per_day_oldest_first(self):
        closed = [replace(bead(f"pg-{i}", "closed"), closed_at=NOW - days * 24 * HOUR) for i, days in enumerate([0, 0, 2, 20])]
        days = pace(closed, NOW)
        self.assertEqual(14, len(days))
        self.assertEqual((2, 1, 3), (days[-1], days[-3], sum(days)))  # the one 20 days ago is outside

    def test_the_roadmap_lists_every_milestone_in_order_with_its_criteria(self):
        tree, _ = board(bead("pg-c1", "closed", parent="pg-m4"), bead("pg-c2", parent="pg-m4"), bead("pg-x", parent="pg-m5"))
        stops = roadmap(tree, DOD, tree.by_id["pg-m4"])
        self.assertEqual([("M4", True, 1, 2), ("M5", False, 0, 1)], [(s["name"], s["current"], s["closed"], s["total"]) for s in stops])

    def test_a_milestone_title_keeps_its_words_after_an_aside(self):
        from cockpit.milestone.tree import without_asides
        self.assertEqual("M6: REA and improvements", without_asides("M6: REA (https://github.com/morluto/rea) and improvements"))
        self.assertEqual("M4: app iteration", without_asides("M4: app iteration (owner 04430d)"))

    def test_the_roadmap_leaves_out_closed_milestones(self):
        tree = BeadTree([milestone("pg-m3", 3, status="closed"), milestone(), milestone("pg-m5", 5)])
        self.assertEqual(["M4", "M5"], [s["name"] for s in roadmap(tree, DOD, tree.by_id["pg-m4"])])

    def test_the_log_lists_the_last_7_days_closures_newest_first(self):
        closed = [replace(bead(f"pg-{days}", "closed", assignee="agent-ai"), closed_at=NOW - days * 24 * HOUR) for days in (3, 0, 9)]
        log = closed_lately(closed + [bead("pg-open")], NOW)
        self.assertEqual(["pg-0", "pg-3"], [b["id"] for b in log])
        self.assertEqual("agent-ai", log[0]["who"])


if __name__ == "__main__":
    unittest.main()
