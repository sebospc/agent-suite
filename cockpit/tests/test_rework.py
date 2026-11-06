import unittest
from dataclasses import replace

from cockpit.action_log.fake_action_log import FakeActionLog
from cockpit.board.bead_watch import BeadWatch
from cockpit.milestone.tree import BeadTree
from cockpit.snapshot.rework_light import rework_light, rework_rows
from cockpit.transcripts.history import History, PeerMessage
from cockpit.transcripts.prompt import prompt_of
from tests.builders import NOW, bead

DAY = 86400


def closed(id, days_ago, **fields):
    return replace(bead(id, status="closed", assignee="agent-ios", **fields), closed_at=NOW - days_ago * DAY)


def review(kind, bead_id, t):
    return PeerMessage(t=t, to="agent-ios", type=kind, bead=bead_id, in_format=True, digest="d", tokens=0, head=kind)


def requested(*bead_ids):
    return [review("GO-REQ", bead_id, NOW - 11 * DAY) for bead_id in bead_ids]


def received(text, t):
    """A peer message as the receiver's transcript shows it, through the real parser."""
    p = prompt_of({"content": f"<cross-session-message from=\"x\">{text}</cross-session-message>"}, t)
    return PeerMessage(t=p["t"], to="agent-ios", type=p["type"], bead=p["bead"], in_format=p["in_format"], digest=p["digest"],
                       tokens=0, keys=p["keys"], head=p["head"])


class ReworkTest(unittest.TestCase):
    """pg-45v5 measure 3 (owner q6: correct = GO first try, no reopen or fix within 7 days, judged after the 7 days)."""

    def test_each_closed_bead_gets_its_verdict(self):
        clean, held, pending = closed("pg-aa01", 9), closed("pg-aa02", 9), closed("pg-aa03", 2)
        fixed, reopened = closed("pg-aa04", 9), closed("pg-aa05", 10)
        fix = replace(bead("pg-bb01", title="fix the crash from pg-aa04"), created_at=NOW - 8 * DAY)
        old = closed("pg-aa06", 20)
        unreviewed = closed("pg-aa07", 9)
        next_step = replace(bead("pg-bb02", title="next step after pg-aa07"), created_at=NOW - 8 * DAY)
        history = History(messages=requested("pg-aa01", "pg-aa02", "pg-aa03", "pg-aa04", "pg-aa05", "pg-aa07") + [
                                    review("GO", "pg-aa01", NOW - 9.5 * DAY), review("HOLD", "pg-aa02", NOW - 9.8 * DAY),
                                    review("GO", "pg-aa03", NOW - 2.5 * DAY), review("GO", "pg-aa04", NOW - 9.5 * DAY),
                                    review("GO", "pg-aa02", NOW - 9.5 * DAY), review("HOLD", "pg-aa01", NOW - 9.2 * DAY)])
        rows = {r["bead"]: r for r in rework_rows(BeadTree([clean, held, pending, fixed, reopened, fix, old, unreviewed, next_step]), history,
                                                  {"pg-aa05": NOW - 9.5 * DAY}, NOW)}
        self.assertNotIn("pg-aa06", rows)  # closed 20 days ago
        self.assertEqual(("correct", 0), (rows["pg-aa01"]["verdict"], rows["pg-aa01"]["holds"]))  # a HOLD after its GO is no rework
        self.assertEqual(("rework", 1), (rows["pg-aa02"]["verdict"], rows["pg-aa02"]["holds"]))
        self.assertEqual("pending", rows["pg-aa03"]["verdict"])
        self.assertEqual(("rework", "pg-bb01"), (rows["pg-aa04"]["verdict"], rows["pg-aa04"]["fixes"]))
        self.assertEqual("rework", rows["pg-aa05"]["verdict"])
        self.assertEqual(("not reviewed", ""), (rows["pg-aa07"]["verdict"], rows["pg-aa07"]["fixes"]))  # no GO; a next step is no fix
        lit = rework_light(list(rows.values()))
        self.assertEqual(("watch", "3 of 6 reworked"), (lit["level"], lit["value"]))
        self.assertIn("1 of 4 past their 7 days were correct", lit["why"])
        self.assertIn("1 had no GO-REQ or no GO", lit["why"])

    def test_a_bead_never_sent_for_review_is_not_rework_data(self):
        reopened = closed("pg-aa05", 10)
        rows = rework_rows(BeadTree([reopened]), History(), {"pg-aa05": NOW - 9.5 * DAY}, NOW)
        self.assertEqual("not reviewed", rows[0]["verdict"])

    def test_a_review_from_before_2026_10_14_finds_its_bead_through_the_go_req_sha256_and_patch_name(self):
        history = History(messages=[
            received("GO-REQ ios-weekstrip v1\npatch: /tmp/x/pg-aa02-strip-v1.patch\nsha256: 7c250819aa", NOW - 10 * DAY),
            received("GO-REQ pg-aa01 v1\npatch: /tmp/x/pg-aa01-v1.patch\nsha256: 4ba05a81", NOW - 10 * DAY),
            received("HOLD ios-weekstrip-menu-v1 (7c250819). The fix misses one path", NOW - 9.9 * DAY),
            received("GO on pg-aa02 iOS v2, sha256 7c250819", NOW - 9.5 * DAY),
            received("GO pg-aa01 v1 (4ba05a81) on 51d82d98, tree 1e7c27c6", NOW - 9.5 * DAY)])
        rows = {r["bead"]: r for r in rework_rows(BeadTree([closed("pg-aa01", 9), closed("pg-aa02", 9)]), history, {}, NOW)}
        self.assertEqual(("correct", 0), (rows["pg-aa01"]["verdict"], rows["pg-aa01"]["holds"]))
        self.assertEqual(("rework", 1), (rows["pg-aa02"]["verdict"], rows["pg-aa02"]["holds"]))

    def test_a_bead_seen_closed_then_open_is_logged_reopened_once(self):
        log = FakeActionLog()
        watch = BeadWatch(log, NOW)
        watch.step(BeadTree([closed("pg-aa01", 1)]), NOW)
        watch.step(BeadTree([bead("pg-aa01", status="in_progress")]), NOW + 30)
        watch.step(BeadTree([bead("pg-aa01", status="in_progress")]), NOW + 60)
        self.assertEqual(["pg-aa01"], [r["bead"] for r in log.records if r["event"] == "bead_reopened"])
        self.assertIn("pg-aa01", BeadWatch(log, NOW + 90).reopened)  # kept across a restart


if __name__ == "__main__":
    unittest.main()
