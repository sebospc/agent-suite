import json
import re
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from cockpit.accounts.fake_accounts import FakeAccounts
from cockpit.accounts.fake_balancer_log import FakeBalancerLog
from cockpit.action_log.fake_action_log import FakeActionLog
from cockpit.asks.fake_asks import FakeAsks
from cockpit.board.fake_board import FakeBoard
from cockpit.classifier.not_connected_classifier import NotConnectedClassifier
from cockpit.clock.fixed_clock import FixedClock
from cockpit.git.fake_git import FakeGit
from cockpit.git.gate_state import GateState
from cockpit.live_sessions.fake_live_sessions import FakeLiveSessions
from cockpit.live_sessions.live_session import LiveSession
from cockpit.disk.fake_disk import FakeDisk
from cockpit.role_memory.fake_role_memory import FakeRoleMemory
from cockpit.hooks.fake_hook_settings import FakeHookSettings
from cockpit.pause.fake_pause import FakePause
from cockpit.milestone.milestone_view import milestone_view
from cockpit.board.board_state import BoardState
from cockpit.server.batch import run_batch
from cockpit.server.http_handler import handler_for
from cockpit.snapshot.ports import Ports
from cockpit.snapshot.snapshot_builder import SnapshotBuilder
from cockpit.snapshot.source_reads import SourceReads
from cockpit.source_unavailable import SourceUnavailable
from cockpit.team_plan.fake_team_plan import FakeTeamPlan
from cockpit.transcripts.fake_transcripts import FakeTranscripts
from cockpit.window_settings.fake_window_settings import FakeWindowSettings
from cockpit.token_tools.fake_token_tools import FakeTokenTools
from cockpit.config_guard.fake_config_files import FakeConfigFiles
from tests.builders import NOW, ROOT, fixture_beads, fixture_json, prices, team, thresholds


class BrokenAccounts(FakeAccounts):
    def list(self):
        raise SourceUnavailable("cswap list --json: not installed")


def builder(accounts=None, live=()):
    panel = fixture_json("panel.json")
    ports = Ports(clock=FixedClock(NOW), board=FakeBoard(fixture_beads(), fixture_json("dod.json"), fixture_json("goal.json"), NOW),
                  asks=FakeAsks(panel["asks"], panel["answered"], NOW), live_sessions=FakeLiveSessions(list(live)),
                  transcripts=FakeTranscripts({}, 100, 80), accounts=accounts or FakeAccounts([]),
                  balancer_log=FakeBalancerLog(None), git=FakeGit(GateState("C120", True, False, 0, 0, "t"), {}),
                  team_plan=FakeTeamPlan(None), classifier=NotConnectedClassifier(), pause=FakePause(),
                  saved_guard=FakeActionLog(), hooks=FakeHookSettings([]),
                  disk=FakeDisk(100 * 1024 ** 3, 500 * 1024 ** 3), role_memory=FakeRoleMemory(),
                  window_settings=FakeWindowSettings(), token_tools=FakeTokenTools(), config_files=FakeConfigFiles())
    return SnapshotBuilder(ports, team(), thresholds(), prices(), 5)


class SnapshotTest(unittest.TestCase):
    def test_a_failing_source_is_named_with_its_error_never_zero(self):
        snapshot = builder(BrokenAccounts([])).build()
        self.assertEqual({"ok": False, "error": "cswap list --json: not installed", "pending": False}, snapshot["sources"]["accounts"])
        self.assertTrue(snapshot["sources"]["balancer"]["pending"])  # waits on pg-81e3: expected, shown apart from a breakage
        self.assertEqual("cswap list --json: not installed", snapshot["accounts_error"])
        self.assertEqual([], snapshot["accounts"])

    def test_a_bead_card_has_its_text_links_and_comments(self):
        b = builder()
        b.build()
        card = b.bead("pg-a18q.35")
        self.assertEqual(("pg-a18q.35", "M4"), (card["id"], card["milestone"]))
        self.assertEqual("pg-a18q", card["parent"][0]["id"])
        self.assertTrue(card["comments"][0]["text"].startswith("brain: reopened"))
        self.assertIsNone(b.bead("pg-nope"))

    def test_the_snapshot_is_plain_json_with_every_section(self):
        snapshot = json.loads(json.dumps(builder().build()))
        self.assertEqual("M4", snapshot["milestone"]["name"])
        # Nothing runs in this fixture and no bead is in progress: only the three the team stops without stay, as off.
        self.assertEqual(["brain", "coordinator", "reviewer"], [r["name"] for r in snapshot["sessions"]])
        cockpit = LiveSession("agent-cockpit", "s-cockpit", 1, "w1:p9", "default", "idle")
        shown = builder(live=[cockpit]).build()["sessions"]
        self.assertIn("cockpit", [r["name"] for r in shown])  # shown once it runs, the owner, 2026-10-17 (09670e)
        self.assertIn("main is green (gate on C120), nothing waits to be pushed", snapshot["clear"])
        self.assertTrue(any("20% under yesterday" in line for line in snapshot["clear"]))
        self.assertTrue(snapshot["needs"])
        self.assertEqual(["tokens", "context", "memory", "said", "disk", "coordination", "main", "rtk", "caveman", "ponytail", "context-mode", "i-have-adhd", "outcomes", "good_use", "rewrites", "hook_output", "docs_age"], [l["id"] for l in snapshot["health"]])
        self.assertEqual(7, len(snapshot["tokens"]["days"]))  # tokens per day, today last
        self.assertFalse(any("loaded_files" in r for r in snapshot["sessions"]))  # dropped, the owner 2026-10-17 (d00915)

    def test_a_slow_source_is_cut_at_the_budget(self):
        started = time.time()
        result = SourceReads(0.2).read({"slow": lambda: time.sleep(2), "fast": lambda: 1})
        self.assertLess(time.time() - started, 1.5)
        self.assertEqual((False, True), (result["slow"]["ok"], result["fast"]["ok"]))


class MilestoneViewTest(unittest.TestCase):
    def test_goal_cells_and_what_is_left_from_the_fixtures(self):
        board = BoardState(fixture_beads(), fixture_json("dod.json"), fixture_json("goal.json"), NOW, NOW, "fixture")
        view = milestone_view(board, fixture_json("panel.json")["asks"], team(), thresholds(), NOW)
        self.assertEqual((2, 10, 6), (view["goal"]["value"], view["goal"]["total"], view["goal"]["target"]))
        goal_cell = [c for c in view["criteria"]["cells"] if c["is_goal"]]
        self.assertEqual(["pg-a18q.29"], [c["id"] for c in goal_cell])
        left = {row["id"]: row for row in view["left"]}
        self.assertTrue(left["pg-a18q.29"]["amber"])
        self.assertIn("No bead in progress is linked to it.", left["pg-a18q.29"]["note"])
        self.assertTrue(left["pg-a18q.30"]["amber"])
        self.assertIn("you (assigned to", left["pg-a18q.30"]["who"])
        self.assertFalse(left["pg-a18q.35"]["amber"])


class StubApp:
    def __init__(self):
        self.started = 0

    def latest(self):
        return {"ok": True}

    def send_gate(self, request):
        return {"ok": True, "allow": True, "why": ""}

    def act(self, request):
        self.acted = request
        return {"ok": request.get("kind") == "compact", "error": ""}

    def bead(self, bead_id):
        return {"id": bead_id} if bead_id == "pg-a18q.29" else None

    def start_grill(self, request):
        self.started += 1
        return {"ok": True, "url": "http://127.0.0.1:1/"}

    def answer(self, request):
        self.answered = request
        return {"ok": True, "words": "A"}

    def pause(self, request):
        return {"ok": True}

    def wrong(self, request):
        return {"ok": True}

    def batch(self, request):
        self.batched = request
        return {"ok": True, "results": []}

    def history(self, area, row, key, hours):
        self.asked = (area, row, key, hours)
        return {"ok": True, "error": "", "points": [[1.0, 5]], "start": 0}


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.app = StubApp()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(self.app, f"{ROOT}/page", lambda: self.server.server_port))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def request(self, path, method="GET", headers=None, body=None):
        request = urllib.request.Request(self.base + path, method=method, headers=headers or {}, data=body)
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def test_page_and_snapshot_are_served(self):
        self.assertEqual(200, self.request("/")[0])
        self.assertEqual((200, b'{"ok": true}'), self.request("/api/snapshot"))

    def test_every_file_the_page_loads_is_served(self):
        page = self.request("/")[1].decode()
        for path in re.findall(r'(?:src|href)="(/[\w.]+)"', page):
            self.assertEqual(200, self.request(path)[0], path)

    def test_a_bead_opens_by_id_and_an_unknown_one_is_404(self):
        self.assertEqual((200, b'{"id": "pg-a18q.29"}'), self.request("/api/bead?id=pg-a18q.29"))
        self.assertEqual(404, self.request("/api/bead?id=pg-nope")[0])

    def test_a_measure_history_is_asked_by_area_row_and_key_with_bounded_hours(self):
        self.assertEqual(200, self.request("/api/history?area=tokens&row=ios&key=input&hours=9999")[0])
        self.assertEqual(("tokens", "ios", "input", 24 * 31), self.app.asked)
        self.assertEqual(400, self.request("/api/history?area=tokens&hours=x")[0])

    def test_a_control_is_posted_as_json_from_the_page_only(self):
        self.assertEqual(403, self.request("/api/action", "POST", {"Origin": "http://evil.example"}, b'{"kind": "compact"}')[0])
        self.assertEqual(200, self.request("/api/action", "POST", {"Origin": self.base}, b'{"kind": "compact", "session": "ios"}')[0])
        self.assertEqual({"kind": "compact", "session": "ios"}, self.app.acted)
        self.assertEqual(400, self.request("/api/action", "POST", {"Origin": self.base}, b'not json')[0])

    def test_a_post_from_another_origin_or_host_is_refused(self):
        self.assertEqual(403, self.request("/api/grill", "POST", {"Origin": "http://evil.example"})[0])
        self.assertEqual(403, self.request("/api/snapshot", headers={"Host": "evil.example"})[0])
        self.assertEqual(0, self.app.started)
        self.assertEqual(200, self.request("/api/grill", "POST", {"Origin": self.base})[0])
        self.assertEqual(1, self.app.started)
        self.assertEqual(403, self.request("/api/answer", "POST", {"Origin": "http://evil.example"}, b'{"id": "696253"}')[0])
        self.assertEqual(200, self.request("/api/answer", "POST", {"Origin": self.base}, b'{"id": "696253", "option": "A"}')[0])

    def test_staged_items_are_posted_together_from_the_page_only(self):
        body = b'{"items": [{"type": "answer", "id": "696253", "option": "A"}]}'
        self.assertEqual(403, self.request("/api/batch", "POST", {"Origin": "http://evil.example"}, body)[0])
        self.assertEqual(200, self.request("/api/batch", "POST", {"Origin": self.base}, body)[0])
        self.assertEqual("696253", self.app.batched["items"][0]["id"])
        long = json.dumps({"items": [{"type": "answer", "id": str(n), "text": "w" * 2000} for n in range(10)]}).encode()
        self.assertEqual(200, self.request("/api/batch", "POST", {"Origin": self.base}, long)[0])
        self.assertEqual(10, len(self.app.batched["items"]))


class BatchTest(unittest.TestCase):
    def test_each_staged_item_runs_in_order_and_one_failure_does_not_stop_the_rest(self):
        ran = []
        handlers = {"answer": lambda i: ran.append(i["id"]) or {"ok": i["id"] != "bad", "error": "gone"},
                    "action": lambda i: ran.append(i["kind"]) or {"ok": True, "id": "a1"}}
        result = run_batch({"items": [{"type": "answer", "id": "bad"}, {"type": "action", "kind": "compact"},
                                      {"type": "answer", "id": "696253"}, {"type": "shell"}]}, handlers)
        self.assertEqual(["bad", "compact", "696253"], ran)
        self.assertEqual(([False, True, True, False], "2 of 4 not sent; each says why."),
                         ([r["ok"] for r in result["results"]], result["error"]))
        self.assertFalse(run_batch({"items": []}, handlers)["ok"])
        self.assertFalse(run_batch({"items": "x"}, handlers)["ok"])


if __name__ == "__main__":
    unittest.main()
