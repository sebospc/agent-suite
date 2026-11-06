import glob
import os
import threading
from typing import Dict, List, Tuple

from cockpit.source_unavailable import SourceUnavailable
from cockpit.transcripts.history import History
from cockpit.transcripts.history_of_file import history_of_file
from cockpit.transcripts.session_stats import SessionStats
from cockpit.transcripts.transcript_file import TranscriptFile
from cockpit.transcripts.transcript_stats import no_cache, processed, session_stats
from cockpit.transcripts.transcripts import Transcripts


class JsonlTranscripts(Transcripts):
    """~/.claude/projects: with cswap --share-history every account's sessions land in this one tree."""

    def __init__(self, root: str, step_tokens: int, idle_gap_s):
        """idle_gap_s: seconds, or a function giving them, so a re-fit of recovery_idle_gap_minutes applies at once."""
        self.root = os.path.expanduser(root)
        self.step_tokens = step_tokens
        self.idle_gap = idle_gap_s if callable(idle_gap_s) else (lambda: idle_gap_s)
        self.files: Dict[str, TranscriptFile] = {}
        # The first read of a month of transcripts can outlast one cycle; a second reader would redo it.
        self.lock = threading.Lock()

    def file(self, path: str) -> TranscriptFile:
        if path not in self.files:
            self.files[path] = TranscriptFile(path)
        self.files[path].update()
        return self.files[path]

    def locked(self):
        if not self.lock.acquire(timeout=1):
            raise SourceUnavailable("still reading transcripts (the first read of a large folder takes a while)")
        return self.lock

    def stats(self, session_ids: List[str], now: float) -> Dict[str, SessionStats]:
        if not os.path.isdir(self.root):
            raise SourceUnavailable(f"{self.root} does not exist")
        lock = self.locked()
        try:
            found = {}
            for session_id in session_ids:
                mains = glob.glob(os.path.join(glob.escape(self.root), "*", f"{session_id}.jsonl"))
                if not mains:
                    continue
                main = self.file(max(mains, key=os.path.getsize))
                extra = [self.file(p) for p in glob.glob(os.path.join(glob.escape(self.root), "*", session_id, "subagents", "*.jsonl"))]
                found[session_id] = session_stats(main, extra, session_id, now, self.step_tokens, self.idle_gap())
            return found
        finally:
            lock.release()

    def daily_tokens(self, day_starts: Tuple[float, float, float]) -> Tuple[int, int, int]:
        yesterday, today, now = day_starts
        lock = self.locked()
        try:
            paths = glob.glob(os.path.join(glob.escape(self.root), "**", "*.jsonl"), recursive=True)
            totals = [0, 0, 0]
            for path in paths:
                if os.path.getmtime(path) < yesterday:
                    continue
                for row in self.file(path).requests():
                    stamp = row["t_first"] or 0
                    # Yesterday up to the same time of day, so a morning is not compared with a whole day.
                    if yesterday <= stamp <= now - 86400:
                        totals[0] += no_cache(row)
                    elif today <= stamp <= now:
                        totals[1] += no_cache(row)
                        totals[2] += row["read"] + row["write"]
            return totals[0], totals[1], totals[2]
        finally:
            lock.release()

    def history(self, start: float, now: float, names: Dict[str, str]) -> History:
        lock = self.locked()
        try:
            requests, messages, starts, sent = [], [], [], []
            for path in glob.glob(os.path.join(glob.escape(self.root), "*", "*.jsonl")):
                session_dir = path[:-len(".jsonl")]
                extra = glob.glob(os.path.join(glob.escape(session_dir), "subagents", "*.jsonl"))
                if max([os.path.getmtime(p) for p in [path] + extra]) < start:
                    continue
                got_requests, got_messages, got_starts, got_sent = history_of_file(self.file(path), [self.file(p) for p in extra], start,
                                                              names.get(os.path.basename(session_dir), ""))
                requests += got_requests
                messages += got_messages
                starts += got_starts
                sent += got_sent
            return History(sorted(requests, key=lambda r: r.t), sorted(messages, key=lambda m: m.t), starts, sorted(sent, key=lambda s: s.t))
        finally:
            lock.release()

    def daily_totals(self, starts: List[float], now: float) -> List[Tuple[int, int]]:
        lock = self.locked()
        try:
            totals = [0] * len(starts)
            cached = [0] * len(starts)
            ends = starts[1:] + [now]
            for path in glob.glob(os.path.join(glob.escape(self.root), "**", "*.jsonl"), recursive=True):
                if os.path.getmtime(path) < starts[0]:
                    continue
                for row in self.file(path).requests():
                    stamp = row["t_first"] or 0
                    day = next((i for i, (start, end) in enumerate(zip(starts, ends)) if start <= stamp < end), None)
                    if day is not None:
                        totals[day] += processed(row)
                        cached[day] += row.get("read", 0) + row.get("write", 0)
            return list(zip(totals, cached))
        finally:
            lock.release()
