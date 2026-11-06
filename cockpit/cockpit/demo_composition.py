import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from typing import Callable

from cockpit.accounts.cswap_accounts import account_from
from cockpit.accounts.fake_accounts import FakeAccounts
from cockpit.accounts.fake_balancer_log import FakeBalancerLog
from cockpit.action_log.fake_action_log import FakeActionLog
from cockpit.metrics.metrics_record import MetricsRecord
from cockpit.asks.fake_asks import FakeAsks
from cockpit.autopilot.autopilot import Autopilot
from cockpit.board.bd_board import BdBoard
from cockpit.milestone.milestone_plan_files import MilestonePlanFiles
from cockpit.classifier.not_connected_classifier import NotConnectedClassifier
from cockpit.clock.fixed_clock import FixedClock
from cockpit.composition import CYCLE_BUDGET_S, ROOT, SUBPROCESS_TIMEOUT_S, price_table, project_config, team_and_thresholds
from cockpit.controls.controls import Controls
from cockpit.git.git_cli import GitCli
from cockpit.grill.grill_server import GrillServer
from cockpit.grill.round_keeper import RoundKeeper
from cockpit.live_sessions.fake_live_sessions import FakeLiveSessions
from cockpit.live_sessions.live_session import LiveSession
from cockpit.panes.fake_panes import FakePanes
from cockpit.disk.disk_usage import DiskUsage
from cockpit.role_memory.claude_memory_files import ClaudeMemoryFiles
from cockpit.hooks.fake_hook_settings import FakeHookSettings
from cockpit.pause.fake_pause import FakePause
from cockpit.jev_record.jev_recorder import JevRecorder
from cockpit.prices.fake_price_page import FakePricePage
from cockpit.prices.price_check import PriceCheck
from cockpit.server.cockpit_app import CockpitApp
from cockpit.snapshot.ports import Ports
from cockpit.snapshot.snapshot_builder import SnapshotBuilder
from cockpit.team_plan.fake_team_plan import FakeTeamPlan
from cockpit.transcripts.jsonl_transcripts import JsonlTranscripts
from cockpit.window_settings.fake_window_settings import FakeWindowSettings
from cockpit.token_tools.fake_token_tools import FakeTokenTools
from cockpit.config_guard.fake_config_files import FakeConfigFiles
from cockpit.team import session_name

FIXTURES = os.path.join(ROOT, "fixtures")
# The fixtures are the board snapshot 3dd1d84; the demo clock stands at its read time so ages read as they did.
SNAPSHOT_TIME = datetime.fromisoformat("2026-10-15T23:05:40-05:00").timestamp()
DEMO_SESSION = "fa5982a7-9c01-5238-bfed-dd0f785ab697"


def demo_app(log: Callable[[str], None]) -> CockpitApp:
    """`python3 cockpit.py --demo`: the real page and core on the fixtures, for a look without the Mac's data.
    Sources the fixtures do not cover are shown as unavailable, never filled with made-up values."""
    team, thresholds = team_and_thresholds(project_config())  # the fixtures are a sample board
    clock = FixedClock(SNAPSHOT_TIME)
    work = tempfile.mkdtemp(prefix="cockpit-demo-")
    os.makedirs(os.path.join(work, "projects", "demo"))
    shutil.copy(os.path.join(FIXTURES, "transcript.sample.jsonl"), os.path.join(work, "projects", "demo", f"{DEMO_SESSION}.jsonl"))
    shutil.copy(os.path.join(FIXTURES, "dod.json"), work)
    shutil.copy(os.path.join(FIXTURES, "goal.json"), work)
    with open(os.path.join(FIXTURES, "panel.json"), encoding="utf-8") as handle:
        panel = json.load(handle)
    with open(os.path.join(FIXTURES, "real", "cswap-list.json"), encoding="utf-8") as handle:
        accounts = [account_from(a) for a in json.load(handle)["accounts"]]  # the owner's redacted real list
    asks = FakeAsks(panel.get("asks") or [], panel.get("answered") or [], SNAPSHOT_TIME)
    beads_cat = [sys.executable, "-c", "import sys; sys.stdout.write(open(sys.argv[1]).read())", os.path.join(FIXTURES, "beads.sample.jsonl")]
    ports = Ports(
        clock=clock,
        board=BdBoard(work, beads_cat, SUBPROCESS_TIMEOUT_S, clock.now, MilestonePlanFiles(work)),
        asks=asks,
        live_sessions=FakeLiveSessions([LiveSession(session_name("ai"), DEMO_SESSION, 0, "demo:1", "", "idle")]),
        transcripts=JsonlTranscripts(os.path.join(work, "projects"), thresholds.value("haiku_step_tokens"),
                                     thresholds.value("recovery_idle_gap_minutes") * 60),
        accounts=FakeAccounts(accounts),
        balancer_log=FakeBalancerLog(None),
        git=GitCli(work, "stack-brain", lambda: "", SUBPROCESS_TIMEOUT_S),
        team_plan=FakeTeamPlan(None),
        classifier=NotConnectedClassifier(),
        pause=FakePause(),
        saved_guard=FakeActionLog(),
        hooks=FakeHookSettings([]),
        disk=DiskUsage("/", {"cockpit fixtures": FIXTURES}),
        role_memory=ClaudeMemoryFiles(os.path.join(work, "projects")),
        window_settings=FakeWindowSettings(), token_tools=FakeTokenTools(), config_files=FakeConfigFiles(),
    )
    os.environ["GRILL_HOME"] = os.path.join(work, "grill")
    grill = GrillServer(os.environ.get("COCKPIT_NODE", "node"), os.path.join(ROOT, "reference", "grill-with-ui", "server.mjs"),
                        work, SUBPROCESS_TIMEOUT_S)
    keeper = RoundKeeper(grill, asks, os.path.join(work, "grill-asks.md"), log)
    builder = SnapshotBuilder(ports, team, thresholds, price_table(), CYCLE_BUDGET_S)
    log(f"demo: fixtures copied to {work}; answers stay in memory")
    action_log = FakeActionLog()
    controls = Controls(FakePanes(), clock, log, action_log)  # the demo types into no pane; a control waits for a proof that never comes
    table = price_table()
    prices = PriceCheck(FakePricePage(table.models), table, "the demo reads no web page; it compares config/prices.json with itself")
    return CockpitApp(builder, keeper, controls, Autopilot(controls, thresholds, action_log, clock, log), thresholds.value("refresh_seconds"), log,
                      prices, JevRecorder(FakeActionLog(), log), MetricsRecord(FakeActionLog()))
