from dataclasses import dataclass
from typing import Optional

from cockpit.accounts.accounts import Accounts
from cockpit.action_log.action_log import ActionLog
from cockpit.accounts.balancer_log import BalancerLog
from cockpit.asks.asks import Asks
from cockpit.board.board import Board
from cockpit.classifier.task_classifier import TaskClassifier
from cockpit.clock.clock import Clock
from cockpit.git.git import Git
from cockpit.live_sessions.live_sessions import LiveSessions
from cockpit.disk.disk import Disk
from cockpit.engram.engram_health import EngramHealth
from cockpit.mac.mac import Mac
from cockpit.hooks.hook_settings import HookSettings
from cockpit.pause.pause_switch import PauseSwitch
from cockpit.role_memory.role_memory import RoleMemory
from cockpit.team_plan.team_plan import TeamPlan
from cockpit.token_tools.token_tools import TokenTools
from cockpit.config_guard.config_files import ConfigFiles
from cockpit.transcripts.transcripts import Transcripts
from cockpit.window_settings.window_settings import WindowSettings


@dataclass(frozen=True)
class Ports:
    clock: Clock
    board: Board
    asks: Asks
    live_sessions: LiveSessions
    transcripts: Transcripts
    accounts: Accounts
    balancer_log: BalancerLog
    git: Git
    team_plan: TeamPlan
    classifier: TaskClassifier
    pause: PauseSwitch
    saved_guard: ActionLog  # brain's saved guard writes one JSON line per block: {t, session, text}
    hooks: HookSettings
    disk: Disk
    role_memory: RoleMemory
    window_settings: WindowSettings
    token_tools: TokenTools
    config_files: ConfigFiles
    engram: Optional[EngramHealth] = None  # None where a project runs without Engram
    mac: Optional[Mac] = None
