import unittest
from dataclasses import replace

from cockpit.milestone.tree import BeadTree
from cockpit.snapshot.comparison_light import comparison_light, finished_tasks
from cockpit.transcripts.history import History, Request
from tests.builders import NOW, bead

HOUR = 3600


def task(id, assignee, start_h, close_h, issue_type="task"):
    return replace(bead(id, status="closed", assignee=assignee, issue_type=issue_type), started_at=NOW - start_h * HOUR,
                   closed_at=NOW - close_h * HOUR)


def request(session, hours_ago, tokens, model="claude-opus-5-5", effort="medium"):
    return Request(t=NOW - hours_ago * HOUR, session=session, tokens=tokens, context=0, origin="peer", turn="t", model=model, effort=effort)


class ComparisonTest(unittest.TestCase):
    """pg-45v5 measure 4: tokens per finished task by role, bead type, model and effort, with sample sizes."""

    def test_requests_count_for_the_bead_their_session_started_last_and_groups_say_their_size(self):
        tree = BeadTree([task("pg-aa01", "agent-ios", 10, 6), task("pg-aa02", "agent-ios", 8, 5, "bug"),
                         task("pg-aa03", "agent-ai", 4, 1)])
        history = History(requests=[request("agent-ios", 9, 1000), request("agent-ios", 7, 500),  # 7 h: pg-aa02 started later
                                    request("agent-ios", 5.5, 200, effort="xhigh"), request("agent-ai", 2, 300, model="claude-sonnet-5-5"),
                                    request("agent-ai", 12, 9999)])  # before its bead started: counts for none
        tasks = {t["bead"]: t for t in finished_tasks(tree, history, NOW)}
        self.assertEqual({"pg-aa01": 1000, "pg-aa02": 700, "pg-aa03": 300}, {b: t["tokens"] for b, t in tasks.items()})
        self.assertEqual(("sonnet-5-5", "medium"), (tasks["pg-aa03"]["model"], tasks["pg-aa03"]["effort"]))
        rows = {r["id"]: r for r in comparison_light(list(tasks.values()))["table"]["rows"]}
        self.assertEqual((2, 850, "small"), (rows["role:ios"]["tasks"], rows["role:ios"]["median"], rows["role:ios"]["sample"]))
        self.assertEqual(1, rows["type:bug"]["tasks"])
        self.assertEqual(2, rows["model:opus-5-5"]["tasks"])


if __name__ == "__main__":
    unittest.main()
