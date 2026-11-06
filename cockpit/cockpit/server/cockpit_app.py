import threading
import time
from typing import Callable, Optional

from cockpit.autopilot.autopilot import Autopilot
from cockpit.refit.learned_light import learned_light, proposal_needs
from cockpit.refit.refitter import Refitter
from cockpit.metrics.quota_use import QuotaUse
from cockpit.controls.controls import Controls
from cockpit.controls.permission import KINDS
from cockpit.grill.round_keeper import RoundKeeper
from cockpit.jev_record.jev_recorder import JevRecorder
from cockpit.jobs.jobs_section import jobs_section
from cockpit.metrics.metrics_record import MetricsRecord
from cockpit.board.bead_watch import BeadWatch
from cockpit.jev_record.jev_calls import JevCalls
from cockpit.snapshot.comparison_light import comparison_light, finished_tasks
from cockpit.snapshot.rework_light import rework_light, rework_rows
from cockpit.prices.price_check import PriceCheck
from cockpit.server.batch import run_batch
from cockpit.snapshot.health_lights import autopilot_light
from cockpit.snapshot.snapshot_builder import SnapshotBuilder
from cockpit.source_unavailable import SourceUnavailable
from cockpit.team import names_of

GRILL_POLL_S = 2


class CockpitApp:
    """Holds the latest snapshot; one thread rebuilds it every refresh period, another hands the owner's grill
    answers to ask_owner.py within seconds."""

    def __init__(self, builder: SnapshotBuilder, keeper: RoundKeeper, controls: Controls, autopilot: Autopilot, refresh_s: float,
                 log: Callable[[str], None], price_check: PriceCheck, jev: JevRecorder, metrics: Optional[MetricsRecord] = None,
                 refitter: Optional[Refitter] = None, jev_calls: Optional[JevCalls] = None, bead_watch: Optional[BeadWatch] = None):
        self.builder = builder
        self.keeper = keeper
        self.controls = controls
        self.autopilot = autopilot
        self.refresh_s = refresh_s
        self.log = log
        self.price_check = price_check
        self.jev = jev
        self.metrics = metrics
        self.refitter = refitter
        self.jev_calls = jev_calls
        self.bead_watch = bead_watch
        self.quota = QuotaUse(metrics.history) if metrics is not None else None
        if keeper is not None:
            keeper.forward = self.forward_thread
        self.lock = threading.Lock()
        self.snapshot: Optional[dict] = None
        self.grill_error = ""
        self.wake = threading.Event()
        self.stopping = threading.Event()

    def start(self) -> None:
        threading.Thread(target=self.collect_forever, name="collector", daemon=True).start()
        threading.Thread(target=self.grill_forever, name="grill", daemon=True).start()

    def collect_once(self) -> dict:
        snapshot = self.builder.build(self.grill_status(), self.controls, {},
                                      self.autopilot.wrong_labels(), self.autopilot.week_outcomes(),
                                      self.quota.per_account if self.quota is not None else {})
        snapshot["autopilot_today"] = self.autopilot.today()
        # After Context, its neighbour: the autopilot is what brings context back under the sweet spot.
        snapshot["health"].insert(2, autopilot_light(snapshot["autopilot_today"], bool(snapshot.get("pause", {}).get("paused"))))
        snapshot["controls_today"] = self.controls.today()
        now = snapshot["read_at"]
        if self.refitter is not None:
            self.refitter.step(now, self.builder.samples)  # once a day; it returns at once on every other read
            learned = self.refitter.status(now)
            snapshot["health"].append(learned_light(learned, now))
            snapshot["needs"] = snapshot["needs"] + proposal_needs(learned)
        if self.bead_watch is not None:
            self.bead_watch.step(self.builder.tree, now)
            snapshot["health"].append(rework_light(rework_rows(self.builder.tree, self.builder.history, self.bead_watch.reopened, now)))
        snapshot["health"].append(comparison_light(finished_tasks(self.builder.tree, self.builder.history, now)))
        if self.jev_calls is not None:
            snapshot["health"].append(self.jev_calls.light(sum(r.get("tokens_24h") or 0 for r in snapshot["sessions"])))
        if self.quota is not None:
            snapshot["health"].append(self.quota.step(snapshot, now))  # recorded below, so tomorrow's figure has its history
        self.record_metrics(snapshot, now)
        self.price_check.step(now)  # once a day; it returns at once on every other read
        b = self.builder
        self.jev.step(snapshot["sessions"], b.tree, b.history, b.history_start, now)
        broken = sum(1 for r in snapshot["sources"].values() if not r["ok"] and not r["pending"])
        snapshot["prices"] = self.price_check.status()
        snapshot["jobs"] = jobs_section(snapshot["autopilot"], snapshot["autopilot_today"], self.autopilot.skips, snapshot["balancer"],
                                        snapshot["balancer_error"], now, self.refresh_s, broken, snapshot["prices"],
                                        self.jev.summary(now), now, bool(snapshot.get("pause", {}).get("paused")),
                                        snapshot.get("self_compacted", []))
        with self.lock:
            self.snapshot = snapshot
        paused = bool(snapshot.get("pause", {}).get("paused"))
        if self.autopilot.step(snapshot["sessions"], paused, closed=self.bead_closed):
            self.wake.set()  # read again at once, so the page shows what it sent waiting for its proof
        return snapshot

    def bead_closed(self, bead: str) -> Optional[bool]:
        tree = self.builder.tree
        found = tree.by_id.get(bead) if tree else None
        return None if found is None else found.status == "closed"

    def record_metrics(self, snapshot: dict, now: float) -> None:
        if self.metrics is None:
            return
        try:
            self.metrics.record(snapshot["health"], now)
            snapshot["sources"]["metrics"] = {"ok": True, "error": "", "pending": False}
        except SourceUnavailable as error:
            snapshot["sources"]["metrics"] = {"ok": False, "error": str(error), "pending": False}

    def history(self, area: str, row: str, key: str, hours: float) -> dict:
        if self.metrics is None:
            return {"ok": False, "error": "metrics.jsonl is not wired in this run", "points": []}
        try:
            start = self.builder.ports.clock.now() - hours * 3600
            return {"ok": True, "error": "", "points": self.metrics.history(area, row, key, start), "start": start}
        except SourceUnavailable as error:
            return {"ok": False, "error": str(error), "points": []}

    def collect_forever(self) -> None:
        while not self.stopping.is_set():
            try:
                self.collect_once()
            except Exception as error:  # keep the last good snapshot and say why the new one failed
                self.log(f"collector: {type(error).__name__}: {error}")
            self.wake.wait(self.refresh_s)
            self.wake.clear()

    def grill_forever(self) -> None:
        while not self.stopping.is_set():
            try:
                before = len(self.keeper.results)
                self.keeper.handle_sends()
                if len(self.keeper.results) != before:
                    self.wake.set()  # an answered ask leaves panel.json: show it now, not in 30 s
                self.grill_error = ""
            except SourceUnavailable as error:
                self.grill_error = str(error)
            time.sleep(GRILL_POLL_S)

    def latest(self) -> Optional[dict]:
        with self.lock:
            if self.snapshot is not None:
                self.snapshot["asks"]["grill"] = self.grill_status()
            return self.snapshot

    def bead(self, bead_id: str) -> Optional[dict]:
        return self.builder.bead(bead_id)

    def act(self, request: dict) -> dict:
        kind, session, level = request.get("kind"), request.get("session"), request.get("level") or ""
        if kind not in KINDS or not isinstance(session, str) or not isinstance(level, str):
            return {"ok": False, "error": "A control needs a kind (compact, clear, effort) and a session."}
        with self.lock:
            rows = list(self.snapshot["sessions"]) if self.snapshot else []
            needs = list(self.snapshot["needs"]) if self.snapshot else []
        if kind == "need":
            result = self.send_need(session, needs, rows)
        else:
            result = self.controls.act(kind, session, level, rows)
        if result["ok"]:
            self.wake.set()  # read again now, so the page shows it waiting for its proof
        return result

    def send_need(self, need_id: str, needs: list, rows: list) -> dict:
        """The page names a Needs you row, never the text: the core's own prompt is what gets typed, so no other page
        can type into a session through this server."""
        need = next((n for n in needs if n["id"] == need_id and n["action_kind"] == "send"), None)
        if need is None:
            return {"ok": False, "error": "That Needs you row is gone or has nothing to send; the page reads again."}
        row = next((r for r in rows if r["name"] == need["target"]), None)
        if row is None or row["state"] == "off" or not row["pane"]:
            return {"ok": False, "error": f"{need['target']} is not running in a herdr pane; copy the prompt from the row instead."}
        return self.controls.send(row, "prompt", need["action_payload"], "", "owner", need["text"][:120])

    def start_grill(self, request: dict) -> dict:
        ids = request.get("ids")
        if not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids):
            return {"ok": False, "error": "Tick the asks you want in the grill round first."}
        try:
            url = self.keeper.start(ids)
        except SourceUnavailable as error:
            return {"ok": False, "error": str(error)}
        self.wake.set()
        return {"ok": True, "url": url}

    def answer(self, request: dict) -> dict:
        ask_id, option, text = request.get("id"), request.get("option") or "", request.get("text") or ""
        if not isinstance(ask_id, str) or not isinstance(option, str) or not isinstance(text, str):
            return {"ok": False, "error": "An answer needs the ask id and an option or your words."}
        try:
            words = self.keeper.answer_one(ask_id, option, text)
        except SourceUnavailable as error:
            return {"ok": False, "error": str(error)}
        self.wake.set()  # the ask leaves panel.json: show it now
        return {"ok": True, "words": words}

    def batch(self, request: dict) -> dict:
        return run_batch(request, {"answer": self.answer, "action": self.act})

    def wrong(self, request: dict) -> dict:
        """The owner's wrong click on one of the autopilot's decisions (design pg-o1sq Q5)."""
        decision = request.get("id")
        if not isinstance(decision, str) or not decision:
            return {"ok": False, "error": "A wrong click needs the id of the autopilot's decision."}
        result = self.autopilot.mark_wrong(decision)
        if result["ok"]:
            self.wake.set()
        return result

    def pause(self, request: dict) -> dict:
        """The owner's Pause / Resume: writes the mark brain's hook reads; the next read shows whether it holds."""
        paused = request.get("paused")
        if not isinstance(paused, bool):
            return {"ok": False, "error": "Pause needs paused: true or false."}
        try:
            self.builder.ports.pause.set(paused, self.builder.ports.clock.now())
        except SourceUnavailable as error:
            return {"ok": False, "error": str(error)}
        self.log(f"owner: team {'paused' if paused else 'resumed'}")
        self.wake.set()
        return {"ok": True}

    def forward_thread(self, ask: dict, text: str) -> str:
        """A grill thread comment, typed into the pane of the session that asked, through the logged control path."""
        with self.lock:
            rows = list(self.snapshot["sessions"]) if self.snapshot else []
        by = ask.get("by", "")
        row = next((r for r in rows if by in (*names_of(r["name"]), r["name"])), None)
        if row is None or row["state"] == "off" or not row["pane"]:
            return f"Not forwarded: {by or 'the session that asked'} is not running in a herdr pane."
        result = self.controls.send(row, "prompt", f"owner, on ask {ask.get('id')}: {text}", "", "owner", f"grill thread on ask {ask.get('id')}")
        return f"Sent to {row['name']}; its reply is in its pane." if result["ok"] else f"Not forwarded: {result['error']}"

    def grill_status(self) -> dict:
        return {"url": self.keeper.url or "", "session": self.keeper.session or "", "results": self.keeper.results[-10:],
                "error": self.grill_error}
