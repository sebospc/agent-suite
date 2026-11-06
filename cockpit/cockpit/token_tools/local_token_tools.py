import glob
import json
import os
import sqlite3
import subprocess
from typing import List

from cockpit.token_tools.token_tools import TokenTools


class LocalTokenTools(TokenTools):
    """rtk gain's own JSON per repo, and context-mode's session databases (opened read only)."""

    def __init__(self, rtk: List[str], repos: List[str], scratchpads: str, ctx_sessions: str, ctx_transcripts: str, timeout_s: float):
        self.rtk = rtk
        self.repos = [os.path.expanduser(r) for r in repos]
        # Team sessions also run commands in their Claude scratchpad folders; rtk files those under that folder.
        self.scratchpads = os.path.expanduser(scratchpads)
        self.ctx_sessions = os.path.expanduser(ctx_sessions)
        # Finished sessions are not live in the cockpit, so what its hooks cost comes from every transcript of the pilot folder.
        self.ctx_transcripts = os.path.expanduser(ctx_transcripts)
        self.chars_by_file: dict = {}  # (path, mtime, size) -> characters: a finished transcript is read once
        self.timeout_s = timeout_s

    def read(self, day: str) -> dict:
        return {"rtk": self.rtk_saved(day), "ctx": self.ctx_kept_out()}

    def rtk_saved(self, day: str) -> dict:
        saved = {}
        try:
            for repo in self.repos + sorted(glob.glob(self.scratchpads)):
                out = subprocess.run(self.rtk + ["gain", "-p", "-d", "-f", "json"], cwd=repo, capture_output=True,
                                     text=True, timeout=self.timeout_s, check=True).stdout
                saved[os.path.basename(repo)] = sum(d["saved_tokens"] for d in json.loads(out).get("daily") or [] if d["date"] == day)
        except (OSError, subprocess.SubprocessError, ValueError, KeyError) as error:
            return {"error": f"rtk gain: {error}"}
        return saved

    def ctx_kept_out(self) -> dict:
        kept = {}
        try:
            for path in glob.glob(os.path.join(self.ctx_sessions, "*.db")):
                with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
                    for session, avoided, returned, events in db.execute(
                            "select session_id, sum(bytes_avoided), sum(bytes_returned), "
                            "count(case when bytes_avoided > 0 then 1 end) from session_events group by session_id"):
                        kept[session] = {"avoided": avoided or 0, "returned": returned or 0, "events": events or 0}
        except sqlite3.Error as error:
            return {"error": f"context-mode sessions: {error}"}
        for path in glob.glob(self.ctx_transcripts):
            session = os.path.basename(path)[:-len(".jsonl")]
            kept.setdefault(session, {"avoided": 0, "returned": 0, "events": 0})["chars"] = self.hook_chars(path)
        return kept

    def hook_chars(self, path: str) -> int:
        """Characters context-mode's hooks (their output) and its deferred tool lines put in this session's context."""
        stat = os.stat(path)
        key = (path, stat.st_mtime, stat.st_size)
        if key not in self.chars_by_file:
            self.chars_by_file = {k: v for k, v in self.chars_by_file.items() if k[0] != path}
            total = 0
            with open(path, errors="replace") as handle:
                for line in handle:
                    if '"type":"attachment"' not in line or "context-mode" not in line:
                        continue
                    try:
                        attachment = json.loads(line).get("attachment") or {}
                    except ValueError:
                        continue
                    if attachment.get("type") == "hook_success" and "context-mode" in (attachment.get("command") or ""):
                        total += len(str(attachment.get("stdout") or attachment.get("content") or ""))
                    elif attachment.get("type") == "deferred_tools_delta":
                        lines = (attachment.get("addedLines") or []) + (attachment.get("surfacedDefinitions") or [])
                        total += sum(len(str(x)) for x in lines if "context-mode" in str(x))
            self.chars_by_file[key] = total
        return self.chars_by_file[key]
