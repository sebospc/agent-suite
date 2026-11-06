import os
import unittest

from cockpit.action_log.fake_action_log import FakeActionLog
from cockpit.autopilot.rules import SPOT, skipped
from cockpit.jev_record.jev_recorder import JevRecorder
from cockpit.display_time import when
from cockpit.jobs.jobs_section import jobs_section
from cockpit.milestone.tree import BeadTree
from cockpit.prices.anthropic_price_page import parse_prices
from cockpit.prices.fake_price_page import FakePricePage
from cockpit.prices.price_check import PriceCheck, differences
from cockpit.process.process_line import process_line
from cockpit.tokens.landed_beads import landed_beads
from cockpit.tokens.tokens_section import tokens_section
from cockpit.transcripts.history import History, PeerMessage, Request
from cockpit.transcripts.prompt import prompt_of
from tests.builders import FIXTURES, HOUR, NOW, bead, prices, team, thresholds

DAY = 24 * HOUR


def request(t, session="agent-ios", tokens=1000, context=50_000, origin="person", turn="a"):
    return Request(t=t, session=session, tokens=tokens, context=context, origin=origin, turn=turn, read=600, out=100)


def message(t, digest="d1", bead_id="pg-a1", kind="GO-REQ", to="agent-ios", in_format=True, tokens=500):
    return PeerMessage(t=t, to=to, type=kind, bead=bead_id, in_format=in_format, digest=digest, tokens=tokens)


def session(name="ios", spot=100_000, **extra):
    row = {"name": name, "spot": spot, "state": "idle", "model": "Opus 5.5", "effort": "high", "context": 50_000, "over": False,
           "pane": "w:1", "notes_saved": True, "holds": 1, "last_turn_at": NOW - 60}
    row.update(extra)
    return row


class PromptTest(unittest.TestCase):
    def test_a_peer_message_in_the_workflow_format_carries_its_type_and_bead(self):
        p = prompt_of({"content": '<cross-session-message from="uds:/tmp/a.sock">HOLD pg-a18q.3 v2\nsha256: 1a2b</cross-session-message>'}, NOW)
        self.assertEqual(("peer", "HOLD", "pg-a18q.3", True), (p["origin"], p["type"], p["bead"], p["in_format"]))

    def test_a_peer_message_without_a_type_line_is_outside_the_format(self):
        p = prompt_of({"content": '<cross-session-message from="x">thanks, noted</cross-session-message>'}, NOW)
        self.assertEqual(("", False), (p["type"], p["in_format"]))

    def test_who_started_a_turn(self):
        self.assertEqual("command", prompt_of({"content": "/compact"}, NOW)["origin"])
        self.assertEqual("person", prompt_of({"content": "please fix the bug"}, NOW)["origin"])
        self.assertEqual("own", prompt_of({"content": "<task-notification>done</task-notification>"}, NOW)["origin"])
        self.assertIsNone(prompt_of({"content": [{"type": "tool_result", "content": "x"}]}, NOW))


class TokensTest(unittest.TestCase):
    def test_shares_above_the_sweet_spot_and_at_high_context(self):
        history = History([request(NOW - 100, tokens=3000, context=160_000), request(NOW - 200, tokens=1000, context=50_000),
                           request(NOW - 300, session="agent-ai", tokens=5000, context=20_000, origin="peer"),
                           request(NOW - 2 * DAY, tokens=99_999)])  # older than 24 h: not counted
        days = [{"day": str(i), "tokens": 1000, "no_cache": 100} for i in range(7)]
        section = tokens_section([session(start_load=45_000), session("ai", start_load=30_000)], history, days, (0, 130), team(), thresholds(), NOW)
        ios = section["sessions"][1]
        # Without cache first (the owner, 56fba6): each request less its 600 cache reads.
        self.assertEqual(("ai", 7200, 9000), (section["top"], section["total_24h"], section["with_cache_24h"]))
        self.assertEqual((2800, 4000, 39, 86), (ios["tokens"], ios["with_cache"], ios["share"], ios["above_spot"]))
        self.assertEqual(33, section["high_share"])  # 2400 of 7200 above 150k
        self.assertTrue(section["over_average"])  # today 130 against an average of 100, 20% allowed
        self.assertEqual((45_000, 43), (ios["start_load"], ios["start_share"]))  # its average turn reads 105k
        self.assertEqual((45_000, 45_000, "ios"), (section["start"]["median"], section["start"]["max"], section["start"]["max_session"]))

    def test_cache_hit_is_cache_reads_over_all_prompt_tokens_per_session_and_for_the_team(self):
        coordinator = [Request(NOW - 100, "agent-ios", 1000, 90_000, "own", "t1", read=900, out=40, write=50),
                       Request(NOW - 200, "agent-ai", 1000, 90_000, "own", "t2", read=990, out=0, write=10)]
        section = tokens_section([session(), session("ai")], History(coordinator), [], None, team(), thresholds(), NOW)
        by_name = {s["name"]: s["cache_hit"] for s in section["sessions"]}
        # ios: 900 read of 960 prompt tokens (10 fresh, 50 written, 900 read); output is no prompt token.
        self.assertEqual({"ios": 93.8, "ai": 99.0}, by_name)
        self.assertEqual(96.4, section["cache_hit_24h"])  # 1890 of 1960

    def test_tokens_per_landed_bead_rising_week_over_week(self):
        beads = [bead("pg-a1", status="closed", assignee="agent-ios"), bead("pg-a2", status="closed", assignee="agent-ios")]
        beads = [b.__class__(**dict(b.__dict__, started_at=start, closed_at=start + HOUR)) for b, start in
                 zip(beads, (NOW - 2 * DAY, NOW - 9 * DAY))]
        requests = [request(NOW - 2 * DAY + 60, tokens=5000), request(NOW - 9 * DAY + 60, tokens=1000)]
        shown = landed_beads(beads, requests, team(), 20, NOW)
        self.assertEqual([("ios", 4400, 400, True)], [(s["session"], s["per_bead"], s["per_bead_before"], s["rising"]) for s in shown])


class ProcessTest(unittest.TestCase):
    def test_duplicates_holds_and_the_format_this_week(self):
        messages = [message(NOW - 100), message(NOW - 50, to="agent-coordinator"),  # same event to two sessions
                    message(NOW - 40, digest="h1", kind="HOLD"), message(NOW - 30, digest="h2", kind="HOLD"),
                    message(NOW - 20, digest="x", in_format=False), message(NOW - 8 * DAY, digest="old")]
        line = process_line(messages, {"pg-a1"}, 600, NOW)
        week = line["this_week"]
        self.assertEqual((5, 1, 500, 1), (week["messages"], week["duplicates"], week["duplicate_tokens"], week["outside_format"]))
        self.assertEqual(["pg-a1"], line["two_holds"])
        self.assertEqual(1, line["last_week"]["messages"])


class PriceCheckTest(unittest.TestCase):
    def test_the_page_table_parses_with_haikus_step(self):
        with open(os.path.join(FIXTURES, "pricing.sample.md")) as handle:
            page = parse_prices(handle.read())
        self.assertEqual(5.0, page["claude-haiku-5-5"]["step_factor"])
        self.assertEqual([], differences(prices(), page))

    def test_a_changed_price_is_named_and_checked_once_a_day(self):
        changed = {k: dict(v) for k, v in prices().models.items()}
        changed["claude-opus-5-5"]["output"] = 25.0
        page = FakePricePage(changed)
        check = PriceCheck(page, prices(), "page")
        self.assertTrue(check.step(NOW))
        self.assertEqual(["claude-opus-5-5 output: 20.0 in config/prices.json, 25.0 on the page"], check.status()["differences"])
        self.assertFalse(check.step(NOW + HOUR))
        self.assertTrue(check.step(NOW + DAY))
        self.assertEqual(2, page.reads)

    def test_a_failed_read_retries_within_the_hour(self):
        check = PriceCheck(FakePricePage(None, "offline"), prices(), "page")
        check.step(NOW)
        self.assertEqual("offline", check.status()["error"])
        self.assertTrue(check.step(NOW + HOUR))


class JobsTest(unittest.TestCase):
    def test_one_line_per_job_and_the_log_merged_by_time_with_dates(self):
        rules = [{"name": SPOT, "short": "Compacts", "when": "idle 10 m"}]
        today = {"on": True, "rows": [{"at": NOW - 60, "session": "ios", "reason": f"{SPOT}: 300k over", "result": "Done: 300k to 80k.",
                                       "state": "done"}], "error": "", "cut": 220_000, "done": 1}
        balancer = [{"at": NOW - 30, "t": "23:05", "text": "ai: account 2."}, {"at": NOW - DAY, "t": "Oct 14, 23:05", "text": "ios: account 1."}]
        status = PriceCheck(FakePricePage(prices().models), prices(), "page")
        status.step(NOW)
        jev = {"beads": 0, "closed": 0, "error": "", "classes": []}
        section = jobs_section(rules, today, [{"session": "ai", "rule": SPOT, "why": "busy"}], balancer, "", NOW, 30, 0,
                               status.status(), jev, NOW)
        self.assertEqual(["autopilot", "rule-0", "balancer", "read", "prices", "jev"], [j["id"] for j in section["jobs"]])
        self.assertEqual("ios: Done: 300k to 80k.", section["jobs"][1]["did"])
        self.assertIn(["Left alone now", "ai: busy"], section["jobs"][1]["detail"])
        self.assertEqual(["Balancer: ai: account 2.", "Autopilot", "Balancer: ios: account 1."],
                         [r["text"] if r["text"].startswith("Balancer") else "Autopilot" for r in section["log"]])
        self.assertEqual("Oct 14, 23:05", section["log"][2]["t"])

    def test_claude_codes_own_compaction_shows_under_the_autopilot(self):
        from dataclasses import replace
        from cockpit.jobs.jobs_section import autopilot_job, self_compacted
        from cockpit.transcripts.session_stats import Compaction
        from tests.test_sessions import stats
        own = [Compaction(NOW - 60, "auto", 267_000, 22_000, None, None), Compaction(NOW - 30, "manual", 200_000, 9_000, None, None),
               Compaction(NOW - 2 * DAY, "auto", 267_000, 22_000, None, None)]
        itself = self_compacted({"brain": replace(stats(22_000), compactions=own)}, NOW - DAY)
        self.assertEqual([("brain", 267_000, 22_000)], [(c["session"], c["pre"], c["post"]) for c in itself])
        job = autopilot_job({"on": True, "rows": [], "cut": 0, "done": 0}, [], NOW, itself)
        self.assertIn("1 session compacted by itself", job["did"])
        self.assertIn("267k to 22k, before the sweet-spot rule did", dict(job["detail"])["Compacted by itself"])

    def test_a_rule_switched_off_says_so_and_is_not_amber(self):
        from cockpit.jobs.jobs_section import autopilot_jobs
        rows = [{"at": NOW - 60, "session": "format", "reason": "Jev's model: x", "result": "Waiting for its next turn on claude-sonnet-5-5.",
                 "state": "waiting"}]
        rules = [{"name": "Jev's model", "short": "x", "when": "Off: jev_model_rule_on is false in config/thresholds.json (set)"}]
        job = autopilot_jobs(rules, {"on": True, "rows": rows, "cut": 0, "done": 0}, [], NOW)[1]
        self.assertEqual(("stopped: jev_model_rule_on is false in config/thresholds.json (set)", ""), (job["did"], job["level"]))

    def test_a_step_waiting_for_its_proof_closes_when_its_rule_is_turned_off(self):
        from cockpit.jobs.jobs_section import closed_when_off
        rows = [{"at": NOW - 7200, "session": "format", "reason": "Jev's model: x", "result": "Waiting for its next turn on claude-sonnet-5-5.",
                 "state": "waiting"},
                {"at": NOW - 60, "session": "ai", "reason": "Sweet spot: y", "result": "Waiting.", "state": "waiting"}]
        rules = [{"name": "Jev's model", "when": "Off: jev_model_rule_on is false in config/thresholds.json (set)"},
                 {"name": "Sweet spot", "when": "On"}]
        closed, open_ = closed_when_off(rules, rows)
        self.assertEqual(("stopped", "Closed without a proof: the rule is off (jev_model_rule_on is false in config/thresholds.json (set))."),
                         (closed["state"], closed["result"]))
        self.assertEqual(rows[1], open_)

    def test_the_autopilot_is_one_job_like_the_others_with_every_action_today(self):
        from cockpit.jobs.jobs_section import autopilot_job
        rows = [{"at": NOW - 60, "session": "ios", "reason": "x", "result": "", "state": "waiting"},
                {"at": NOW - 600, "session": "ai", "reason": "x", "result": "No proof.", "state": "not_seen"},
                {"at": NOW - 900, "session": "web", "reason": "x", "result": "Done.", "state": "done"}]
        on = autopilot_job({"on": True, "rows": rows, "cut": 571_000, "done": 1}, [], NOW)
        self.assertEqual(("Autopilot", "1 proved compaction cut 571k of context; 1 waiting for its proof; 1 not proved", "amber"),
                         (on["name"], on["did"], on["level"]))
        self.assertEqual(when(NOW - 60, NOW), on["last"])  # its latest action, as every job shows it
        idle = autopilot_job({"on": True, "rows": [], "cut": 0, "done": 0}, [{"session": "ai", "why": "busy"}], NOW)
        self.assertEqual(("nothing to do today; 1 session left alone now", ""), (idle["did"], idle["level"]))
        off = autopilot_job({"on": False, "rows": [], "cut": 0, "done": 0}, [], NOW)
        self.assertEqual(("stopped: autopilot_on is false in config/thresholds.json", "amber"), (off["did"], off["level"]))

    def test_the_autopilot_light_watches_a_stop_or_an_unproved_action(self):
        from cockpit.snapshot.health_lights import autopilot_light
        done = {"on": True, "error": "", "cut": 571_000, "done": 3,
                "rows": [{"session": "ios", "state": "done", "result": "Done.", "text": "/compact"}]}
        self.assertEqual(("571k cut in 3", "ok"), (autopilot_light(done, False)["value"], autopilot_light(done, False)["level"]))
        self.assertEqual("paused", autopilot_light(done, True)["value"])
        self.assertEqual(("stopped", "watch"), tuple(autopilot_light(dict(done, on=False), False)[k] for k in ("value", "level")))
        lost = dict(done, rows=[{"session": "ai", "state": "not_seen", "result": "No proof after 15 min.", "text": "/compact"}])
        self.assertEqual(("1 not proved", "watch"), tuple(autopilot_light(lost, False)[k] for k in ("value", "level")))
        self.assertEqual("unknown", autopilot_light(dict(done, error="unreadable"), False)["level"])

    def test_the_autopilot_says_why_it_leaves_a_session_alone(self):
        rows = [session(over=True, state="busy"), session("ai", over=True, last_turn_at=NOW - 120), session("android", over=True, notes_saved=False)]
        whys = {s["session"]: s["why"] for s in skipped(rows, set(), thresholds(), NOW)}
        self.assertEqual({"ios": "busy, so it waits for the turn to end", "ai": "idle 2 m of the 10 m it waits",
                          "android": "idle 1 m of the 10 m it waits"}, whys)  # unsaved notes no longer hold it


class JevRecordTest(unittest.TestCase):
    def test_a_suggestion_is_kept_once_and_its_outcome_written_when_the_bead_closes(self):
        record = FakeActionLog()
        row = session(suggested={"bead": "pg-a1", "model": "Sonnet 5.5", "effort": "medium", "agrees": False})
        jev = JevRecorder(record, lambda line: None)
        open_tree = BeadTree([bead("pg-a1", status="in_progress", assignee="agent-ios")])
        self.assertEqual(1, jev.step([row], open_tree, History(), 0, NOW))
        self.assertEqual(0, jev.step([row], open_tree, History(), 0, NOW + 30))  # same suggestion, same model: not again
        closed = bead("pg-a1", status="closed", assignee="agent-ios")
        closed = closed.__class__(**dict(closed.__dict__, started_at=NOW, closed_at=NOW + HOUR))
        history = History([request(NOW + 60, tokens=7000)], [message(NOW + 70, kind="HOLD")])
        self.assertEqual(1, jev.step([], BeadTree([closed]), history, NOW - DAY, NOW + 2 * HOUR))
        outcome = record.records[-1]
        self.assertEqual(("outcome", 7000, 1, 1, False), (outcome["event"], outcome["tokens"], outcome["turns"], outcome["holds"], outcome["partial"]))
        again = JevRecorder(record, lambda line: None)  # a restart reads the record back and writes nothing twice
        self.assertEqual(0, again.step([row], BeadTree([closed]), history, NOW - DAY, NOW + 3 * HOUR))
        summary = again.summary(NOW + 3 * HOUR)
        self.assertEqual((1, 1, 7000), (summary["beads"], summary["closed"], summary["classes"][0]["per_bead"]))


class SaidVsSavedTest(unittest.TestCase):
    def test_answers_missing_from_decisions_and_saved_claims_with_no_id(self):
        from cockpit.saved.said_vs_saved import said_vs_saved
        view = said_vs_saved([{"id": "696253", "answer": "A"}, {"id": "4c9041", "answer": "yes"}], "... panel 696253 ...", [],
                             [{"sha": "abc1234", "t": NOW, "subject": "x"}],
                             {"ios": {"saved": 2, "places": ["scratchpad"]}, "ai": {"saved": 0, "places": ["a file", "scratchpad"]}}, {})
        self.assertEqual([{"id": "4c9041", "answer": "yes"}], view["not_in_decisions"])
        self.assertEqual({"ios": 2}, view["without_id"])
        self.assertEqual({"place": "scratchpad", "count": 2, "trust": "not trusted"}, view["places"][0])
        self.assertEqual([], said_vs_saved([{"id": "x", "answer": "y"}], None, [], None, {}, {"decisions": "no repo"})["not_in_decisions"])
        stopped = said_vs_saved([], "", [], [], {}, {}, [{"t": NOW, "session": "ios", "text": "saved the notes"}])
        self.assertEqual((1, "1 reply stopped today: ios: saved the notes"), (stopped["blocks"], stopped["guard"]))


class ReceiptsTest(unittest.TestCase):
    def msg(self, t, kind, sha="", bead_id="pg-a18q"):
        return PeerMessage(t=t, to="x", type=kind, bead=bead_id, in_format=True, digest=f"{kind}{t}", tokens=0,
                           keys={"sha256": sha} if sha else {})

    def test_each_review_must_name_the_patch_hash_its_request_sent(self):
        from cockpit.process.receipts import receipt_breaks
        good = [self.msg(NOW - 50, "GO-REQ", "aaaa1111"), self.msg(NOW - 40, "GO", "aaaa1111"),
                self.msg(NOW - 30, "LAND-READY", "aaaa1111"), self.msg(NOW - 20, "LANDED")]
        self.assertEqual([], receipt_breaks(good, NOW))
        bad = [self.msg(NOW - 50, "GO-REQ", "aaaa1111"), self.msg(NOW - 40, "GO", "bbbb2222"), self.msg(NOW - 30, "LAND-READY", "aaaa1111"),
               self.msg(NOW - 20, "HOLD"), self.msg(NOW - 10, "LANDED", bead_id="pg-zzzz")]
        self.assertEqual(["GO on pg-a18q names sha256 bbbb2222, which no GO-REQ sent",
                          "LAND-READY on pg-a18q names sha256 aaaa1111, which no GO approved",
                          "HOLD on pg-a18q names no sha256", "LANDED on pg-zzzz with no GO before it"], receipt_breaks(bad, NOW))

    def test_a_peer_message_after_claude_codes_wrapper_line_is_still_a_peer_message(self):
        p = prompt_of({"content": 'Another Claude session sent a message:\n<cross-session-message from="x">GO pg-a18q.3 v2\nsha256: 1a2b3c4d</cross-session-message>'}, NOW)
        self.assertEqual(("peer", "GO", "pg-a18q.3"), (p["origin"], p["type"], p["bead"]))

    def test_the_hash_is_read_from_the_message_lines(self):
        p = prompt_of({"content": '<cross-session-message from="x">GO-REQ pg-a18q.3 v2\npatch: /s/p.diff\nsha256: 1A2B3C4D\nbase: abc1234</cross-session-message>'}, NOW)
        self.assertEqual({"sha256": "1a2b3c4d", "base": "abc1234", "patch": "/s/p.diff"}, p["keys"])


class NextRunTest(unittest.TestCase):
    def test_each_job_says_when_it_runs_next(self):
        from cockpit.jobs.jobs_section import next_runs
        jobs = [{"id": "rule-0", "did": "nothing today"}, {"id": "read", "did": ""}, {"id": "prices", "did": ""},
                {"id": "jev", "did": ""}, {"id": "balancer", "did": ""}]
        next_runs(jobs, NOW, 30, {"tried_at": NOW - 3600, "error": ""}, False, NOW)
        self.assertTrue(jobs[0]["next"].startswith("next read, "))
        self.assertEqual("when a session starts or moves (its hook)", jobs[4]["next"])
        self.assertNotEqual("", jobs[2]["next"])
        next_runs(jobs, NOW, 30, {"tried_at": NOW, "error": ""}, True, NOW)
        self.assertEqual("paused with the team", jobs[3]["next"])
