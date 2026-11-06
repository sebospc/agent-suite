import os
import re
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

from cockpit.mac.mac import Mac
from cockpit.source_unavailable import SourceUnavailable

VERSION_TAIL_BYTES = 65_536  # every transcript line carries the Claude Code version; the last few lines are enough
# ponytail: one-shot tools by name, plus anything that names a Claude scratchpad; a long-lived daemon (herdr, dolt, adb)
# is never on it. Widen the set when a new kind of leftover shows up.
ONE_SHOT_TOOLS = {"tail", "grep", "ugrep", "rg", "find", "sleep", "cat", "xargs", "jq", "sqlite3"}
CLAUDE_SCRATCH = "/tmp/claude-"
SWAP_USED = re.compile(r"used = ([\d.]+)M")
VERSION = re.compile(r'"version":"(\d+\.\d+\.\d+)"')
VERSION_NAME = re.compile(r"\d+\.\d+\.\d+")


def elapsed_seconds(etime: str) -> int:
    """ps etime is [[dd-]hh:]mm:ss."""
    days, _, clock = etime.rpartition("-")
    parts = [int(p) for p in clock.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    hours, minutes, seconds = parts
    return (int(days) if days else 0) * 86400 + hours * 3600 + minutes * 60 + seconds


def orphans(ps_lines: List[str], min_age_s: int) -> List[dict]:
    """ps -axo pid=,ppid=,etime=,args= lines of the user's processes: whose parent is launchd, old enough, and left by a session."""
    found = []
    for line in ps_lines:
        fields = line.split(None, 3)
        if len(fields) < 4 or fields[1] != "1":
            continue
        pid, _, etime, args = fields
        age = elapsed_seconds(etime)
        tool = os.path.basename(args.split()[0])
        if age >= min_age_s and (tool in ONE_SHOT_TOOLS or CLAUDE_SCRATCH in args):
            found.append({"pid": int(pid), "age_s": age, "args": args[:200]})
    return found


def last_version(transcript: Path) -> Optional[str]:
    with transcript.open("rb") as f:
        f.seek(max(0, transcript.stat().st_size - VERSION_TAIL_BYTES))
        versions = VERSION.findall(f.read().decode("utf-8", "ignore"))
    return versions[-1] if versions else None


class SystemMac(Mac):
    def __init__(self, transcripts: str, claude_bin: str, orphan_min_hours: float):
        self.transcripts = Path(os.path.expanduser(transcripts))
        self.claude_bin = os.path.expanduser(claude_bin)
        self.orphan_min_s = int(orphan_min_hours * 3600)

    def read(self) -> dict:
        try:
            free = int(self._run(["sysctl", "-n", "kern.memorystatus_level"]))
            swap = SWAP_USED.search(self._run(["sysctl", "-n", "vm.swapusage"]))
            ps = self._run(["ps", "-xo", "pid=,ppid=,etime=,args="]).splitlines()
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            raise SourceUnavailable(f"sysctl or ps: {error}")
        return {"memory_free_pct": free, "swap_used_mb": float(swap.group(1)) if swap else None,
                "orphans": orphans(ps, self.orphan_min_s), "claude_version": self._claude_version(),
                "session_versions": self._session_versions()}

    def _run(self, command: List[str]) -> str:
        return subprocess.run(command, capture_output=True, text=True, timeout=10, check=True).stdout

    def _claude_version(self) -> Optional[str]:
        # The installer links the binary to versions/<version>, so the link names what a new session starts on.
        target = os.path.realpath(self.claude_bin)
        return os.path.basename(target) if VERSION_NAME.fullmatch(os.path.basename(target)) else None

    def _session_versions(self) -> Dict[str, str]:
        since = time.time() - 86400
        found = {}
        for path in self.transcripts.glob("*/*.jsonl"):
            if path.stat().st_mtime >= since and (version := last_version(path)):
                found[path.stem] = version
        return found
