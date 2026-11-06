import glob
import json
import os
import re
import subprocess
from typing import Dict, List, Optional, Tuple

from cockpit.live_sessions.background_pill import background_of
from cockpit.live_sessions.live_session import LiveSession
from cockpit.live_sessions.live_sessions import LiveSessions
from cockpit.sessions.launch_options import flat, options
from cockpit.source_unavailable import SourceUnavailable
from cockpit.team import all_prefixes

STATUS_MODEL = re.compile(r"\|\s*((?:Opus|Sonnet|Haiku|Fable) \d+(?:\.\d+)?)\b")
STATUS_LINES = 12  # the status bar sits under the input box, with one line per running agent under it

PROFILE = re.compile(r"^(\d+)-")
CONFIG_DIR = re.compile(r"(?:^|\s)CLAUDE_CONFIG_DIR=(\S+)")
# ps eww prints the command line, then the environment; only these flags are kept, never a variable (they hold secrets).
LAUNCH_FLAG = re.compile(r"(?:^|\s)(--settings|--plugin-dir)[ =](\S+)")
IDLE_TITLE_MARK = "✳"
PS = ["ps", "eww", "-p"]


class CswapHerdrSessions(LiveSessions):
    """Live records (`<profile>/sessions/<pid>.json`, read only) give pid, session and account; herdr gives
    the pane and busy or idle."""

    def __init__(self, profiles_dir: str, default_sessions_dir: str, herdr: List[str], timeout_s: float, ps: List[str] = PS,
                 project_names: Optional[Dict[str, str]] = None):
        self.profiles_dir = os.path.expanduser(profiles_dir)
        self.default_dir = os.path.expanduser(default_sessions_dir)
        self.herdr = [os.path.expanduser(part) for part in herdr]
        self.timeout_s = timeout_s
        self.ps = ps
        # A side project's session is not launched as <prefix><role>; its working folder names it.
        self.project_names = {os.path.realpath(os.path.expanduser(folder)): name for folder, name in (project_names or {}).items()}

    def list(self) -> List[LiveSession]:
        records = self.records()
        panes = self.panes()
        if not records and panes is None:
            raise SourceUnavailable("no live session records and herdr pane list failed")
        sessions = []
        for record in records:
            pane = (panes or {}).get(record["session_id"], {})
            names = [record["name"] if record["name_source"] != "derived" else "",
                     pane.get("label") or "", pane.get("terminal_title_stripped") or ""]
            # A launch without --name gets a derived name such as <prefix>b9, which is no role; the pane label is.
            name = next((n for n in names if n.startswith(all_prefixes())), "") \
                or (record["cwd"] and self.project_names.get(os.path.realpath(record["cwd"]), "")) or next((n for n in names if n), record["name"])
            model, background = self.status_bar(pane.get("pane_id") or "")
            sessions.append(LiveSession(name=name, session_id=record["session_id"], pid=record["pid"],
                                        pane=pane.get("pane_id", ""), account=record["account"],
                                        state=live_state(pane, record), started_at=record["started_at"],
                                        status_model=model, background=background,
                                        **self.launch_flags(pane, record)))
        return sessions

    def status_bar(self, pane_id: str) -> Tuple[str, str]:
        """(model, background pill) from the pane's status bar: the transcript names the model only on the next reply."""
        if not pane_id:
            return "", ""
        try:
            done = subprocess.run(self.herdr + ["pane", "read", pane_id, "--source", "visible", "--lines", str(STATUS_LINES)],
                                  capture_output=True, text=True, timeout=self.timeout_s)
        except (OSError, subprocess.TimeoutExpired):
            return "", ""
        if done.returncode != 0:
            return "", ""
        found = STATUS_MODEL.findall(done.stdout)
        return (found[-1] if found else ""), background_of(done.stdout)

    def records(self) -> List[dict]:
        found: Dict[int, dict] = {}
        folders = [(path, account_of(path)) for path in sorted(glob.glob(os.path.join(glob.escape(self.profiles_dir), "*", "sessions")))]
        folders.append((self.default_dir, "default"))
        for folder, account in folders:
            for path in glob.glob(os.path.join(glob.escape(folder), "*.json")):
                try:
                    with open(path, encoding="utf-8") as handle:
                        raw = json.load(handle)
                    pid = int(raw.get("pid") or os.path.splitext(os.path.basename(path))[0])
                except (OSError, ValueError, TypeError):
                    continue
                # Every profile's sessions/ can be a symlink to one folder, so the same record shows under each profile.
                if raw.get("sessionId") and pid not in found and is_alive(pid):
                    shown = self.process(pid)
                    found[pid] = {"pid": pid, "session_id": raw["sessionId"], "name": raw.get("name") or "",
                                  "name_source": raw.get("nameSource") or "", "cwd": raw.get("cwd") or "", "status": raw.get("status") or "",
                                  "started_at": started_at(raw),
                                  "account": account_in(shown) or account,
                                  "flags": tuple(part for flag in LAUNCH_FLAG.findall(shown) for part in flag)}
        return list(found.values())

    def process(self, pid: int) -> str:
        """ps eww of the process, "" when ps cannot show it. Read by account_in and LAUNCH_FLAG only, never stored."""
        try:
            done = subprocess.run(self.ps + [str(pid)], capture_output=True, text=True, timeout=self.timeout_s)
        except (OSError, subprocess.TimeoutExpired):
            return ""
        return done.stdout if done.returncode == 0 else ""


    def launch_flags(self, pane: dict, record: dict) -> dict:
        """Every flag of its command line from herdr's argv of the pane's process (brain, pg-o1sq relaunch HOLD 5f13ab8);
        without it, only the --settings and --plugin-dir ps shows, and its flags count as not known. Never the --resume
        id (the session's own) nor the prompt."""
        argv = self.argv(pane.get("pane_id") or "", record["pid"]) if pane else None
        if argv is None:
            return {"flags": record["flags"], "flags_known": False}
        return {"flags": tuple(flat([(f, v) for f, v in options(argv[1:]) if f not in ("--resume", "--session-id")])), "flags_known": True}

    def argv(self, pane_id: str, pid: int) -> Optional[List[str]]:
        try:
            done = subprocess.run(self.herdr + ["pane", "process-info", "--pane", pane_id], capture_output=True, text=True, timeout=self.timeout_s)
            processes = json.loads(done.stdout)["result"]["process_info"]["foreground_processes"]
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
            return None
        return next((p["argv"] for p in processes if p.get("pid") == pid and isinstance(p.get("argv"), list)), None)

    def panes(self) -> Optional[Dict[str, dict]]:
        try:
            done = subprocess.run(self.herdr + ["pane", "list"], capture_output=True, text=True, timeout=self.timeout_s)
            listed = json.loads(done.stdout)["result"]["panes"]
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
            return None
        # pane list, not agent list: herdr misses agents in panes it did not start (panel.py).
        return {(p.get("agent_session") or {}).get("value"): p for p in listed if p.get("agent_session")}


def started_at(raw: dict) -> float:
    try:
        return float(raw.get("startedAt") or 0) / 1000
    except (TypeError, ValueError):
        return 0.0


def account_of(sessions_folder: str) -> str:
    match = PROFILE.match(os.path.basename(os.path.dirname(sessions_folder)))
    return match.group(1) if match else "?"


def is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def live_state(pane: dict, record: dict) -> str:
    """Busy when either source says so: each one can lag the other for a moment around a tool call (brain's F13)."""
    states = [pane_state(pane) if pane else "", record_state(record)]
    return "busy" if "busy" in states else states[0] or states[1]


def pane_state(pane: dict) -> str:
    status = pane.get("agent_status") or "unknown"
    if status == "unknown":
        # herdr says unknown for a pane it did not start; Claude's title mark still tells idle from working.
        return "idle" if (pane.get("terminal_title") or "").startswith(IDLE_TITLE_MARK) else "busy"
    return {"working": "busy", "blocked": "waits"}.get(status, "idle")


def record_state(record: dict) -> str:
    return {"busy": "busy", "idle": "idle", "waiting": "waits"}.get(record.get("status"), "unknown")


def account_in(shown: str) -> str:
    """The account the process really runs on: cswap launches it with CLAUDE_CONFIG_DIR=<profiles>/<n>-<email>; none
    is the default login. "" when ps cannot tell. Only that one variable is kept: the environment holds secrets."""
    if not shown.strip():
        return ""
    match = CONFIG_DIR.search(shown)
    if not match:
        # No HOME= either means ps showed no environment at all (a sandbox), so it cannot tell.
        return "default" if re.search(r"(?:^|\s)HOME=", shown) else ""
    profile = PROFILE.match(os.path.basename(match.group(1).rstrip("/")))
    return profile.group(1) if profile else "?"
