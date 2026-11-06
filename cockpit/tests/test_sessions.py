import unittest
from dataclasses import replace

from cockpit.live_sessions.live_session import LiveSession
from cockpit.milestone.criteria import Criteria
from cockpit.milestone.tree import BeadTree
from cockpit.sessions.session_row import session_row
from cockpit.sessions.working_on import working_on
from cockpit.transcripts.session_stats import Compaction, SessionStats
from tests.builders import NOW, bead, milestone, prices, thresholds

DOD = {"milestones": {"pg-m4": {"dod": ["pg-c1"]}}}


def board(*beads):
    tree = BeadTree([milestone(), milestone("pg-m5", 5)] + list(beads))
    return tree, Criteria(tree, tree.by_id["pg-m4"], DOD, [])


def work(role, state, *beads, coordinating=False):
    tree, criteria = board(*beads)
    return working_on(role, f"agent-{role}", list(tree.by_id.values()), tree, criteria, coordinating, state)


def stats(context, model="claude-opus-5-5", effort="high", last_turn=NOW - 600, turn_started=NOW - 700):
    return SessionStats(session_id="s1", title="agent-ios", model=model, effort=effort, ttl_seconds=3600,
                        context_now=context, floor=72_000, last_turn_at=last_turn, tokens_24h=1_000_000,
                        growth=[2_779] * 20, outputs=[519] * 20, gaps=[10.0] * 20,
                        compactions=[Compaction(1.0, "auto", 300_000, 66_630, 117_212, 46_630)], haiku_over_step=0,
                        turn_started_at=turn_started)


def row(context, state="idle", held=(), plan=None, model="claude-opus-5-5", effort="high"):
    live = LiveSession("agent-ios", "s1", 1, "w1:p2", "15", state)
    w = {"bead": "pg-c1", "tag": "", "kind": "dod", "line": "", "held": [b.id for b in held]}
    return session_row("ios", live, stats(context, model, effort), w, list(held), plan, [], thresholds(), prices(), NOW)


class WorkingOnTest(unittest.TestCase):
    def test_kinds_and_tag_for_a_session_holding_a_criterion_and_m5_work(self):
        result = work("ios", "busy", bead("pg-c1", "in_progress", parent="pg-m4", assignee="agent-ios"),
                      bead("pg-x", "in_progress", parent="pg-m5", assignee="agent-ios"))
        self.assertEqual(("pg-c1 +1", "M4 done criterion, and 1 M5 bead", "next"), (result["bead"], result["tag"], result["kind"]))

    def test_coordinating_sessions_hold_no_bead_by_design(self):
        self.assertEqual("role", work("reviewer", "idle", coordinating=True)["kind"])
        self.assertEqual("reviews, holds no bead", work("reviewer", "idle", coordinating=True)["tag"])

    def test_an_idle_session_with_open_beads_is_flagged(self):
        result = work("format", "idle", bead("pg-o", "open", parent="pg-m4", assignee="agent-format"))
        self.assertEqual(("idle", "idle, 1 open bead assigned"), (result["kind"], result["tag"]))

    def test_parked_beads_are_no_work_to_wake_for(self):
        parked = bead("pg-28it", "open", assignee="agent-format", priority=4, title="Parked: later idea")
        self.assertNotEqual("idle", work("format", "idle", parked)["kind"])


class SessionRowTest(unittest.TestCase):
    def test_over_the_sweet_spot_and_idle_with_notes_saved_can_compact(self):
        held = [bead("pg-c1", "in_progress", updated=NOW - 60)]
        r = row(400_000, held=held)
        self.assertTrue(r["over"])
        self.assertEqual(283_788, round(r["spot"]))  # E1 with T_s = y, as research/scripts/m.py prints it
        self.assertTrue(r["can_compact"])
        self.assertIn("about 26% more per turn", r["advice"])

    def test_notes_not_saved_after_the_last_turn_or_a_busy_session_cannot_compact(self):
        self.assertFalse(row(400_000, held=[bead("pg-c1", "in_progress", updated=NOW - 6000)])["can_compact"])
        self.assertFalse(row(400_000, state="busy")["can_compact"])

    def test_below_the_sweet_spot_there_is_nothing_to_compact(self):
        r = row(150_000)
        self.assertFalse(r["over"] or r["can_compact"])

    def test_drift_against_team_json(self):
        self.assertEqual("team.json says effort medium", row(150_000, plan={"model": "claude-opus-5-5", "effort": "medium"})["drift"])
        self.assertEqual("", row(150_000, plan={"model": "claude-opus-5-5", "effort": "high"})["drift"])

    def test_a_haiku_session_over_100k_is_flagged_while_its_sweet_spot_stays_under_it(self):
        low = replace(stats(118_000, "claude-haiku-5-5"), compactions=[Compaction(1.0, "auto", 95_000, 40_000, 50_000, 30_000)])
        live = LiveSession("agent-coordinator", "s1", 1, "w1:p3", "12", "idle")
        w = {"bead": "", "tag": "", "kind": "role", "line": "", "held": []}
        flagged = session_row("coordinator", live, low, w, [], None, [], thresholds(), prices(), NOW)
        self.assertTrue(flagged["haiku_over_step"])
        # Its last compaction left it at 117k, so no window keeps it under 100k: its sweet spot rules, not the step.
        self.assertFalse(row(118_000, model="claude-haiku-5-5")["haiku_over_step"])

    def test_a_session_that_is_not_running_says_so(self):
        w = {"bead": "no bead", "tag": "", "kind": "none", "line": "", "held": []}
        r = session_row("ios", None, None, w, [], None, [], thresholds(), prices(), NOW)
        self.assertEqual(("off", "Not running."), (r["state"], r["why"]))


if __name__ == "__main__":
    unittest.main()


class LiveByRoleTest(unittest.TestCase):
    def test_the_session_herdr_sees_in_a_pane_wins_its_role(self):
        from cockpit.sessions.live_by_role import live_by_role
        stale = LiveSession("agent-brain", "old", 1, "", "3", "idle")
        real = LiveSession("agent-brain", "new", 2, "w4:p3", "3", "busy")
        role_of = lambda name: name.replace("agent-", "")
        self.assertEqual("new", live_by_role([stale, real], role_of)["brain"].session_id)
        self.assertEqual("new", live_by_role([real, stale], role_of)["brain"].session_id)


class StateFileRereadTest(unittest.TestCase):
    def test_a_host_session_with_a_state_file_is_measured_like_a_role(self):
        from dataclasses import replace
        live = LiveSession("agent-ios", "s1", 1, "w1:p2", "15", "idle")
        work = {"bead": "pg-c1", "tag": "", "kind": "dod", "line": "", "held": ["pg-c1"]}
        read = replace(stats(90_000), reads_since_start=frozenset({"/mem/project_ios_state.md"}))
        found = session_row("ios", live, read, work, [], None, [], thresholds(), prices(), NOW, memory_file="project_ios_state.md")
        self.assertEqual(("", True), (found["notes_file"], found["notes_reread"]))  # notes_saved still judges it by its bead
        by_shell = replace(read, reads_since_start=frozenset({"grep -n Now $M/project_ios_state.md | head"}))
        self.assertTrue(session_row("ios", live, by_shell, work, [], None, [], thresholds(), prices(), NOW,
                                    memory_file="project_ios_state.md")["notes_reread"])
        missed = replace(read, reads_since_start=frozenset({"/repo/x.py"}))
        self.assertFalse(session_row("ios", live, missed, work, [], None, [], thresholds(), prices(), NOW,
                                     memory_file="project_ios_state.md")["notes_reread"])
        self.assertIsNone(session_row("ios", live, read, work, [], None, [], thresholds(), prices(), NOW)["notes_reread"])
