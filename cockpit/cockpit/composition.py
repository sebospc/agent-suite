import json
import os
import sys
from typing import Callable, Optional

from cockpit.accounts.balancer_log_file import BalancerLogFile
from cockpit.action_log.action_log_file import ActionLogFile
from cockpit.metrics.metrics_record import MetricsRecord
from cockpit.accounts.statusline_accounts import StatuslineAccounts
from cockpit.asks.panel_file_asks import PanelFileAsks
from cockpit.autopilot.autopilot import Autopilot
from cockpit.refit.refitter import Refitter
from cockpit.asks.asks import Asks
from cockpit.asks.no_asks import NoAsks
from cockpit.board.bd_board import BdBoard
from cockpit.board.board import Board
from cockpit.board.no_board import NoBoard
from cockpit.milestone.milestone_plan_files import MilestonePlanFiles
from cockpit.milestone.no_milestone_plan import NoMilestonePlan
from cockpit.classifier.cached_classifier import CachedClassifier
from cockpit.classifier.jev_classifier import JevClassifier
from cockpit.classifier.not_connected_classifier import NotConnectedClassifier
from cockpit.classifier.task_classifier import TaskClassifier
from cockpit.clock.system_clock import SystemClock
from cockpit.classifier.jev_wake import JevWakeForecast
from cockpit.compaction.price_table import PriceTable
from cockpit.controls.controls import Controls
from cockpit.git.git_cli import GitCli
from cockpit.grill.grill_server import GrillServer
from cockpit.grill.round_keeper import RoundKeeper
from cockpit.live_sessions.cswap_herdr_sessions import CswapHerdrSessions
from cockpit.panes.herdr_panes import HerdrPanes
from cockpit.disk.disk_usage import DiskUsage
from cockpit.engram.engram_store import EngramStore
from cockpit.mac.system_mac import SystemMac
from cockpit.hooks.settings_files import SettingsFiles
from cockpit.pause.pause_file import PauseFile
from cockpit.board.bead_watch import BeadWatch
from cockpit.jev_record.jev_calls import JevCalls
from cockpit.jev_record.jev_recorder import JevRecorder
from cockpit.prices.anthropic_price_page import AnthropicPricePage
from cockpit.prices.price_check import PriceCheck
from cockpit.project_config.project_config import load_config
from cockpit.role_memory.claude_memory_files import ClaudeMemoryFiles
from cockpit.server.cockpit_app import CockpitApp
from cockpit.snapshot.ports import Ports
from cockpit.snapshot.snapshot_builder import SnapshotBuilder
from cockpit.team import Team, configure, session_name
from cockpit.team_plan.team_plan_file import TeamPlanFile
from cockpit.thresholds import Thresholds
from cockpit.token_tools.local_token_tools import LocalTokenTools
from cockpit.config_guard.json_config_files import JsonConfigFiles
from cockpit.transcripts.jsonl_transcripts import JsonlTranscripts
from cockpit.window_settings.account_settings_files import AccountSettingsFiles

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBPROCESS_TIMEOUT_S = 10
CYCLE_BUDGET_S = 20


def read_config(name: str) -> dict:
    with open(os.path.join(ROOT, "config", name), encoding="utf-8") as handle:
        return json.load(handle)


# Without --project the cockpit runs on its own folder's .cockpit.json.
def project_config(project_dir: str = ROOT) -> dict:
    return load_config(project_dir)


def team_and_thresholds(config: dict):
    raw = config["team"]
    configure(raw.get("session_prefix", "agent-"), raw.get("legacy_prefixes", []), raw.get("lead", "lead"),
              raw.get("coordinator", "coordinator"))
    return Team(raw["roles"], raw["coordinating"], raw["known_holders"]), Thresholds(read_config("thresholds.json"))


def price_table() -> PriceTable:
    return PriceTable(read_config("prices.json"))


def scratch_of(panel_path: str) -> Callable[[], str]:
    def read() -> str:
        try:
            with open(os.path.expanduser(panel_path), encoding="utf-8") as handle:
                return json.load(handle).get("scratch") or ""
        except (OSError, ValueError):
            return ""
    return read


# A project without a board, a panel or a milestone gets the none adapter: the cockpit starts and leaves that section out.
def board_of(paths: dict, now: Callable[[], float]) -> Board:
    if "board_dir" not in paths:
        return NoBoard()
    plan = MilestonePlanFiles(paths["milestone_dir"]) if "milestone_dir" in paths else NoMilestonePlan()
    return BdBoard(paths["board_dir"], paths["bd_command"], SUBPROCESS_TIMEOUT_S, now, plan)


def asks_of(paths: dict, now: Callable[[], float]) -> Asks:
    return PanelFileAsks(paths["panel"], paths["ask_owner"], SUBPROCESS_TIMEOUT_S, now) if "panel" in paths else NoAsks()


def task_classifier(calls: Optional[JevCalls] = None, answers_path: Optional[str] = None) -> TaskClassifier:
    """Jev when TYPESAFE_API_KEY holds its key (the owner, 2026-10-16); shadow mode either way: shown, never applied."""
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    usage = calls.record if calls else (lambda key, questions, usage: None)
    return CachedClassifier(JevClassifier(key, SUBPROCESS_TIMEOUT_S, on_usage=usage) if key else NotConnectedClassifier(),
                            answers_path if key else None)


def real_app(log: Callable[[str], None], config: dict) -> CockpitApp:
    """The one composition root: it alone names the technologies (bd, cswap, herdr, git, grill-with-ui)."""
    paths = config["paths"]
    team, thresholds = team_and_thresholds(config)
    clock = SystemClock()
    jev_calls = JevCalls(ActionLogFile(paths["jev_calls"]), clock.now, log)
    gate_logs = scratch_of(paths["panel"]) if paths["gate_logs"] == "panel.json scratch" else (lambda: paths["gate_logs"])
    classifier = task_classifier(jev_calls, paths["jev_answers"])
    asks = asks_of(paths, clock.now)
    ports = Ports(
        clock=clock,
        board=board_of(paths, clock.now),
        asks=asks,
        live_sessions=CswapHerdrSessions(paths["cswap_profiles"], paths["default_sessions"], paths["herdr"], SUBPROCESS_TIMEOUT_S,
                                         project_names={folder: session_name(role) for role, folder in config["team"].get("projects", {}).items()}),
        transcripts=JsonlTranscripts(paths["transcripts"], thresholds.value("haiku_step_tokens"),
                                     lambda: thresholds.value("recovery_idle_gap_minutes") * 60),
        accounts=StatuslineAccounts(paths["usage"]),
        balancer_log=BalancerLogFile(paths["balancer_log"]),
        git=GitCli(paths["repo"], paths["landing_ref"], gate_logs, SUBPROCESS_TIMEOUT_S, paths["repos"],
                   os.path.join(paths["board_dir"], "stack.json") if "board_dir" in paths else ""),
        team_plan=TeamPlanFile(paths["team_json"]),
        classifier=classifier,
        pause=PauseFile(paths["pause_file"]),
        saved_guard=ActionLogFile(paths["saved_guard_log"]),
        hooks=SettingsFiles(paths["hook_settings"]),
        disk=DiskUsage(paths["disk_volume"], paths["disk_folders"]),
        role_memory=ClaudeMemoryFiles(paths["transcripts"]),
        window_settings=AccountSettingsFiles(paths["cswap_profiles"], paths["default_settings"]),
        token_tools=LocalTokenTools(paths["rtk"], paths["repos"], paths["rtk_scratchpads"], paths["context_mode_sessions"], paths["context_mode_transcripts"], SUBPROCESS_TIMEOUT_S),
        config_files=JsonConfigFiles(paths["guarded_configs"], paths["config_baseline"]),
        engram=EngramStore(paths["engram_bin"], paths["engram_db"], paths["transcripts"], paths["engram_project"]),
        mac=SystemMac(paths["transcripts"], paths.get("claude_bin", "~/.local/bin/claude"), thresholds.value("orphan_min_hours")),
    )
    grill = GrillServer(paths["node"], paths["grill_server"], paths["repo"], SUBPROCESS_TIMEOUT_S)
    keeper = RoundKeeper(grill, asks, os.path.expanduser(paths["grill_doc"]), log)
    builder = SnapshotBuilder(ports, team, thresholds, price_table(), CYCLE_BUDGET_S, paths["hook_logs"],
                              paths["docs_not_describing_code"], paths.get("decision_log", "docs/DECISIONS.md"))
    action_log = ActionLogFile(paths["action_log"])
    panes = HerdrPanes(paths["herdr"], SUBPROCESS_TIMEOUT_S)
    controls = Controls(panes, clock, log, action_log)
    autopilot = Autopilot(controls, thresholds, action_log, clock, log, JevWakeForecast(classifier))
    prices = PriceCheck(AnthropicPricePage(paths["prices_page"], SUBPROCESS_TIMEOUT_S), builder.prices, paths["prices_page"])
    jev = JevRecorder(ActionLogFile(paths["jev_record"]), log)
    return CockpitApp(builder, keeper, controls, autopilot, thresholds.value("refresh_seconds"), log, prices, jev,
                      MetricsRecord(ActionLogFile(paths["metrics_log"])),
                      Refitter(thresholds, action_log, ActionLogFile(paths["learned_log"]), log, clock.now()),
                      jev_calls, BeadWatch(action_log, clock.now()))



def port(config: dict) -> int:
    return int(config["port"])


def stderr_log(line: str) -> None:
    print(line, file=sys.stderr, flush=True)
