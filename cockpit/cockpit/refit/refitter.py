import threading
from typing import Callable, Dict, List, Optional

from cockpit.action_log.action_log import ActionLog
from cockpit.refit.bounds import Range, bounded
from cockpit.refit.fitters import FITTERS, MIN_LABELS, MIN_SAMPLES, label_rows
from cockpit.source_unavailable import SourceUnavailable
from cockpit.thresholds import Thresholds

DAY, WEEK = 86400, 7 * 86400


class Refitter:
    """Once a day, re-fits each learned number from the logs (design pg-o1sq Q14). A fit inside its range moves it,
    at most its weekly change; one outside becomes a proposal in Your tasks. Each change is a line in learned.jsonl,
    so a restart applies them again and config/thresholds.json stays what the repo says."""

    def __init__(self, thresholds: Thresholds, actions: ActionLog, learned: ActionLog, log: Callable[[str], None], now: float):
        self.thresholds = thresholds
        self.actions = actions
        self.learned = learned
        self.log = log
        self.lock = threading.Lock()
        self.ran_at = 0.0
        self.error = ""
        self.restore(now)

    def records(self, since: float) -> List[dict]:
        try:
            return self.learned.since(since)
        except SourceUnavailable as error:
            self.error = str(error)
            return []

    def restore(self, now: float) -> None:
        for r in self.records(0):
            if r.get("event") == "learned" and self.range_of(r["name"]):
                self.thresholds.learn(r["name"], r["to"])
            # The cockpit restarts on every code change; the daily run is kept across them.
            self.ran_at = max(self.ran_at, r["t"] if r.get("event") == "refit_ran" else 0)

    def range_of(self, name: str):
        return Range.of(self.thresholds[name].range) if name in self.thresholds.items else None

    def step(self, now: float, samples: Optional[dict] = None) -> int:
        """samples: what the transcripts measured for the fitters that need it (the snapshot builder's)."""
        if now - self.ran_at < DAY:
            return 0
        self.ran_at = now
        try:
            actions = self.actions.since(now - 2 * WEEK)
        except SourceUnavailable as error:
            self.error = str(error)
            return 0
        week = self.records(now - WEEK)
        self.write({"t": now, "event": "refit_ran"})
        changed = 0
        for name, fit in FITTERS.items():
            rng = self.range_of(name)
            found = fit(actions, dict(samples or {}, now=now), self.thresholds.value(name)) if rng else None
            if rng is None or found is None:
                continue
            fitted, count, how = found
            current = self.thresholds.value(name)
            start = next((r["from"] for r in week if r.get("event") == "learned" and r["name"] == name), current)
            value, outside = bounded(fitted, start, rng)
            if outside:
                self.write({"t": now, "event": "proposal", "name": name, "from": current, "fitted": fitted, "n": count, "why": f"{outside}; {how}"})
            elif value != current:
                self.write({"t": now, "event": "learned", "name": name, "from": current, "to": value, "fitted": fitted, "n": count, "why": how})
                self.thresholds.learn(name, value)
                self.log(f"refit: {name} {current} to {value} ({how})")
                changed += 1
        return changed

    def write(self, record: dict) -> None:
        try:
            self.learned.append(record)
        except SourceUnavailable as error:
            self.error = str(error)

    def status(self, now: float) -> Dict[str, list]:
        """Each learned number with its range and latest change, and the proposals of the week still standing."""
        week = self.records(now - WEEK)
        numbers = []
        for name, t in self.thresholds.items.items():
            if not t.range:
                continue
            last = next((r for r in reversed(week) if r.get("event") == "learned" and r["name"] == name), None)
            numbers.append({"name": name, "value": t.value, "range": t.range, "fitter": name in FITTERS, "last": last})
        latest = {}
        for r in week:
            if r.get("event") in ("learned", "proposal"):
                latest[r["name"]] = r
        proposals = [r for r in latest.values() if r["event"] == "proposal"]
        return {"numbers": numbers, "proposals": proposals, "error": self.error, "min_samples": MIN_SAMPLES, "min_labels": MIN_LABELS,
                "labels": self.label_counts(now)}

    def label_counts(self, now: float) -> Optional[Dict[str, int]]:
        """Measured against confounded TASK starts (pg-6inz), the same two weeks the fit reads; None when unreadable."""
        try:
            measured, confounded = label_rows(self.actions.since(now - 2 * WEEK), now)
        except SourceUnavailable:
            return None
        return {"measured": len(measured), "confounded": confounded}
