import unittest

from cockpit.board.bead import Bead
from cockpit.milestone.tree import BeadTree, short_name
from tests.builders import bead, fixture_beads, milestone


class BeadTreeTest(unittest.TestCase):
    def test_a_grandchild_is_under_the_milestone(self):
        tree = BeadTree([milestone(), bead("pg-a", parent="pg-m4"), bead("pg-a.1", parent="pg-a")])
        self.assertTrue(tree.is_under(tree.by_id["pg-a.1"], "pg-m4"))
        self.assertEqual(["pg-a", "pg-a.1"], sorted(b.id for b in tree.descendants("pg-m4")))

    def test_the_current_milestone_is_the_open_one_with_the_lowest_number(self):
        tree = BeadTree([milestone("pg-m3", 3, "closed"), milestone("pg-m5", 5), milestone("pg-m4", 4)])
        self.assertEqual("pg-m4", tree.current_milestone().id)
        self.assertEqual("M4", short_name(tree.current_milestone()))

    def test_parent_comes_from_the_parent_child_dependency_of_an_export(self):
        exported = Bead.from_export({"id": "pg-x", "dependencies": [
            {"type": "parent-child", "depends_on_id": "pg-m4"}, {"type": "related", "depends_on_id": "pg-c"}]})
        self.assertEqual(("pg-m4", ["pg-c"]), (exported.parent, exported.related))

    def test_fixture_board_finds_m4_and_puts_m5_work_under_m5(self):
        tree = BeadTree(fixture_beads())
        self.assertEqual("pg-a18q", tree.current_milestone().id)
        self.assertEqual("M5", short_name(tree.milestone_of(tree.by_id["pg-67gb.3"])))


if __name__ == "__main__":
    unittest.main()
