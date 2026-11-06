from typing import Callable, Dict, List, Optional

from cockpit.action_log.action_log import ActionLog
from cockpit.action_log.day_log import day_rows, midnight
from cockpit.autopilot.session_changes import SessionChanges
from cockpit.autopilot.relaunch import EXIT_WAIT_S
from cockpit.autopilot.task_start import TASK_START
from cockpit.autopilot.wrong_clicks import decisions, labels, marked, pending_undos, undo_of, wrong_record
from cockpit.autopilot.keep_warm import KEEP_WARM, Stretch, Stretches, probe_choice, probe_state, verdict
from cockpit.autopilot.no_forecast import NoForecast
from cockpit.autopilot.compact_verdicts import judge_compacts
from cockpit.autopilot.rules import compaction_starts, decide, skipped
from cockpit.autopilot.wake_forecast import WakeForecast
from cockpit.autopilot.window_step import window_commands, window_key
from cockpit.clock.clock import Clock
from cockpit.controls.controls import Controls
from cockpit.display_time import clock_time
from cockpit.source_unavailable import SourceUnavailable
from cockpit.thresholds import Thresholds


UNREACHABLE_HOLD_S = 30 * 60
WRONG_CLEAR_DAYS, WRONG_CLEARS_TO_STOP = 7, 2
VERDICTS = ("cleared", "wrong_clear", "right_clear", "right_compact", "wrong_compact")


class Autopilot:
    """Phase 3: after every read, sends the compactions its two rules call for through the same controls the owner
    uses, so each one is proved and logged the same way."""

    def __init__(self, controls: Controls, thresholds: Thresholds, action_log: ActionLog, clock: Clock, log: Callable[[str], None],
                 wake: WakeForecast = NoForecast()):
        self.controls = controls
        self.thresholds = thresholds
        self.action_log = action_log
        self.clock = clock
        self.log = log
        self.wake = wake
        self.stretches = Stretches()
        self.restore_stretches()
        self.skips: List[dict] = []
        self.task_starts = self.decided_tasks()  # TASK ids already decided, kept across restarts
        self.unreachable: dict = {}  # session -> (pane, until, error): its pane refused the last send
        self.refusals: Dict[str, int] = {}  # session -> refusals since its last send went through
        self.read_gap = 0.0
        self.window_set = self.last_window_levels()  # (account, model) -> what its last /autocompact set, kept across restarts
        self.window_held = False
        self.exiting, self.relaunched = self.relaunches()
        self.changes = SessionChanges(action_log, clock.now())
        # ponytail: in memory, so a bead closed while the cockpit restarts is not cleared; keep it in actions.jsonl if that matters.
        self.held: Dict[str, set] = {}  # session -> beads it held on the last read
        self.finished: Dict[str, str] = {}  # session -> its closed bead, cleared at its next idle moment with nothing to lose
        self.last_step_at: Optional[float] = None  # its read gap opens the compaction window that much earlier

    def step(self, rows: List[dict], paused: bool = False, arriving: Optional[Dict[str, dict]] = None,
             closed: Callable[[str], Optional[bool]] = lambda bead: None) -> int:
        self.changes.step(rows, self.clock.now())  # logged on or off, paused or not: the fitters read them
        self.note_finished(rows, closed)
        sent = self.window_step(rows, paused)
        # A paused team gets nothing typed: a compaction is a turn, and the owner stopped the team.
        if not self.thresholds.value("autopilot_on") or paused:
            return sent
        now = self.clock.now()
        read_gap, self.last_step_at = (now - self.last_step_at if self.last_step_at else 0), now
        self.read_gap = read_gap
        by_name = {r["name"]: r for r in rows}
        hold = self.controls.pending() | {r["name"] for r in rows if self.held_unreachable(r, now)}
        warm, warm_skips = self.keep_warm_verdicts(rows, hold, now, read_gap)
        skips = skipped(rows, self.controls.pending(), self.thresholds, now, read_gap) + self.unreachable_skips(rows, now) + warm_skips
        for skip in skips:
            if skip not in self.skips:  # logged when a reason starts, not on every read
                self.log(f"autopilot: left {skip['session']} alone ({skip['rule']}): {skip['why']}")
                # Kept in actions.jsonl too: the thresholds are calibrated from what the rules did and did not do.
                self.write(dict(skip, t=self.clock.now(), event="skipped", origin="autopilot",
                                context=by_name[skip["session"]]["context"]))
        self.skips = skips
        wrong = self.judge_clears(rows, now)
        self.judge_compacts(rows, now)
        only_compact = {name for name, n in wrong.items() if n >= WRONG_CLEARS_TO_STOP}
        undecided = {name: task for name, task in (arriving or {}).items() if task["id"] not in self.task_starts}
        for choice in decide(rows, hold, self.thresholds, now, undecided, only_compact, read_gap, self.finished, warm):
            row = by_name[choice["session"]]
            if choice["kind"] == "keep":
                self.task_started(choice, row, now)
                continue
            result = self.controls.send(row, choice["kind"], choice["text"], choice["level"], "autopilot",
                                        f"{choice['rule']}: {choice['reason']}")
            sent += result["ok"]
            if result["ok"]:
                self.refusals.pop(row["name"], None)
            if result["ok"] and choice.get("task"):
                self.task_started(choice, row, now, result["id"])
            if result["ok"] and choice["kind"] == "probe":
                self.probe_sent(row, result["id"], now)
            if result["ok"] and choice["kind"] == "clear":
                self.finished.pop(row["name"], None)
                # What the next session would lose: judged on its first turns (judge_clears).
                self.write({"t": now, "event": "cleared", "origin": "autopilot", "id": result["id"], "session": row["name"],
                            "bead": choice.get("bead", ""), "files": row.get("task_files") or []})
            if not result["ok"]:
                self.refused(row, choice["kind"], result["error"], now)
        return sent + self.relaunch_step(rows, hold, now)

    def keep_warm_verdicts(self, rows: List[dict], hold: set, now: float, read_gap: float) -> tuple:
        """Per session due for a probe, Jev's wake forecast turned into probe, hold or leave (keep_warm.py), and the
        skip lines for the ones left alone. Jev is asked only when a probe is due and nothing waits on the session."""
        found, skips = {}, []
        for row in rows:
            self.stretches.observe(row, now)
            probes = self.stretches.probes(row["name"])
            state = probe_state(row, probes, self.thresholds, now, read_gap)
            if state == "capped":
                skips.append({"session": row["name"], "rule": KEEP_WARM,
                              "why": f"{probes} probes sent, the break-even count at its context; its cache goes cold or the other rules decide"})
            if state != "due" or row["name"] in hold:
                continue
            try:
                forecast = self.wake.forecast(row, self.stretches.idle_since(row), now)
            except SourceUnavailable as error:
                skips.append({"session": row["name"], "rule": KEEP_WARM, "why": f"no wake forecast ({error}), so nothing is probed"})
                continue
            decision = verdict(row, probes, forecast, self.thresholds.value("jev_yes_probability"))
            if decision["act"] == "probe":
                found[row["name"]] = dict(decision, choice=probe_choice(row, decision["why"]))
            elif decision["act"] == "hold":
                found[row["name"]] = decision
            if decision["act"] != "probe":
                skips.append({"session": row["name"], "rule": KEEP_WARM, "why": decision["why"]})
        return found, skips

    def probe_sent(self, row: dict, control: str, now: float) -> None:
        stretch = self.stretches.sent(row, now)
        self.write({"t": now, "event": "probe_sent", "origin": "autopilot", "id": control, "session": row["name"],
                    "idle_since": stretch.idle_since, "n": stretch.probes, "cap": row["keep_warm"]["cap"], "context": row["context"]})

    def restore_stretches(self) -> None:
        """Kept across restarts (the cockpit restarts on every code change): the last probe of each session's stretch;
        the next read drops it if the session worked since."""
        try:
            records = self.action_log.since(self.clock.now() - 86400)
        except SourceUnavailable:
            return
        for r in (r for r in records if r.get("event") == "probe_sent"):
            self.stretches.by_session[r["session"]] = Stretch(r["idle_since"], r["n"], r["t"])

    def note_finished(self, rows: List[dict], closed: Callable[[str], Optional[bool]]) -> None:
        for row in rows:
            now_held = set(row.get("held") or [])
            if now_held:
                self.finished.pop(row["name"], None)  # it took new work: a clear now would drop it
            for bead in self.held.get(row["name"], set()) - now_held:
                if closed(bead):
                    self.finished[row["name"]] = bead
            self.held[row["name"]] = now_held

    def task_started(self, choice: dict, row: dict, now: float, control: str = "") -> None:
        """One record per TASK, typed or kept, so the outcomes (step 6) can judge each case of the table. It keeps Jev's
        scores and the cut-off they were read at, and the control's id its outcome is joined by (cockpit/refit)."""
        s = row.get("suggested") or {}
        self.task_starts.add(choice["task"])
        self.log(f"autopilot: TASK {choice['task']} for {row['name']}: {choice['kind']} (case {choice['case']})")
        self.write({"t": now, "event": "task_start", "origin": "autopilot", "task": choice["task"], "session": row["name"],
                    "bead": choice["bead"], "action": choice["kind"], "case": choice["case"], "why": choice["reason"],
                    "context": row["context"], "control": control,
                    "scores": s.get("bead_scores") or {} if s.get("bead") == choice["bead"] else {},
                    "session_scores": s.get("scores") or {}, "yes": self.thresholds.value("jev_yes_probability")})

    def decided_tasks(self) -> set:
        try:
            return {r["task"] for r in self.action_log.since(self.clock.now() - WRONG_CLEAR_DAYS * 86400) if r.get("event") == "task_start"}
        except SourceUnavailable:
            return set()

    def relaunch_step(self, rows: List[dict], hold: set, now: float) -> int:
        """A relaunch already begun (an owner's undo): once its process is gone after the /exit, the resume is typed
        into its pane's shell."""
        sent = 0
        live_ids = {r.get("session_id") for r in rows if r["state"] != "off"}
        for exit_id, pending in list(self.exiting.items()):
            if pending["session_id"] in live_ids and now - pending["t"] < EXIT_WAIT_S:
                continue
            del self.exiting[exit_id]
            if pending["session_id"] in live_ids:
                self.write({"t": now, "event": "relaunch_dropped", "origin": "autopilot", "id": exit_id, "session": pending["session"],
                            "why": f"still running {EXIT_WAIT_S // 60} min after its /exit"})
                continue
            # Logged first: typed twice, the resume would land as a prompt in the session the first one started.
            self.write({"t": now, "event": "relaunch_typed", "origin": "autopilot", "id": exit_id, "session": pending["session"]})
            try:
                self.controls.panes.run_in(pending["pane"], pending["command"])
            except SourceUnavailable as error:
                self.write({"t": now, "event": "relaunch_dropped", "origin": "autopilot", "id": exit_id, "session": pending["session"],
                            "why": str(error)})
                continue
            self.log(f"autopilot: ran {pending['command']!r} in {pending['pane']}")
            sent += 1
        sent += self.undo_step(rows, hold, now)
        # The autopilot never relaunches a session (owner 2026-10-19): /compact and /clear only.
        return sent

    def start_relaunch(self, row: dict, command: str, origin: str, reason: str, now: float, undo: str = "") -> str:
        """/exit now; the resume command is typed into its shell once its process is gone. Returns the control id."""
        result = self.controls.send(row, "relaunch", "/exit", command, origin, reason)
        if not result["ok"]:
            self.refused(row, "relaunch", result["error"], now)
            return ""
        self.refusals.pop(row["name"], None)
        self.relaunched.add((row["session_id"], command))
        self.exiting[result["id"]] = {"t": now, "session": row["name"], "session_id": row["session_id"], "pane": row["pane"], "command": command}
        self.write(dict(self.exiting[result["id"]], event="relaunch_exit", origin="autopilot", id=result["id"], undo_command=undo))
        return result["id"]

    def undo_step(self, rows: List[dict], hold: set, now: float) -> int:
        """The owner's wrong click on a relaunch, applied at the session's next idle moment, never mid-turn (Q5)."""
        try:
            undos = pending_undos(self.action_log.since(now - WRONG_CLEAR_DAYS * 86400))
        except SourceUnavailable:
            return 0
        by_name = {r["name"]: r for r in rows}
        sent = 0
        for wrong in undos:
            row = by_name.get(wrong["session"])
            if row is None or row["name"] in hold or row["state"] != "idle" or not row["pane"] or row["last_turn_at"] is None \
                    or row.get("background"):  # an /exit kills its background tasks
                continue
            control = self.start_relaunch(row, wrong["undo"], "owner", f"Undo of {wrong['of']}: the owner marked it wrong", now)
            if control:
                self.write({"t": now, "event": "undo_sent", "origin": "owner", "of": wrong["of"], "session": row["name"], "id": control})
                sent += 1
        return sent

    def mark_wrong(self, decision_id: str) -> dict:
        """The owner's wrong click on one of the autopilot's decisions in 7 days: always the label, and the undo when
        the decision has one."""
        now = self.clock.now()
        try:
            records = self.action_log.since(now - WRONG_CLEAR_DAYS * 86400)
        except SourceUnavailable as error:
            return {"ok": False, "error": str(error)}
        decision = decisions(records).get(decision_id)
        if decision is None:
            return {"ok": False, "error": "That decision is not one of the autopilot's in the last 7 days."}
        if decision_id in marked(records):
            return {"ok": False, "error": "Already marked wrong."}
        undo, why = undo_of(decision, records)
        self.write(wrong_record(decision, undo, why, now))
        self.log(f"owner: marked {decision_id} of {decision['session']} wrong" + ("; undo at its next idle moment" if undo else f"; {why}"))
        return {"ok": True, "undo": bool(undo), "why": why or "it is undone at the session's next idle moment, same session id"}

    def week_outcomes(self) -> Dict[str, dict]:
        """Per session in 7 days: its TASK starts by action, its clears that lost work, and the owner's wrong clicks."""
        try:
            records = self.action_log.since(self.clock.now() - WRONG_CLEAR_DAYS * 86400)
        except SourceUnavailable:
            return {}
        found: Dict[str, dict] = {}
        for r in records:
            mine = found.setdefault(r.get("session", ""), {"task_starts": {}, "wrong_clears": 0, "wrong": 0})
            if r.get("event") == "task_start":
                mine["task_starts"][r["action"]] = mine["task_starts"].get(r["action"], 0) + 1
            elif r.get("event") in ("wrong_clear", "wrong"):
                mine["wrong_clears" if r["event"] == "wrong_clear" else "wrong"] += 1
        return found

    def wrong_labels(self) -> dict:
        try:
            return labels(self.action_log.since(self.clock.now() - WRONG_CLEAR_DAYS * 86400))
        except SourceUnavailable:
            return {}

    def relaunches(self) -> tuple:
        """Kept across restarts (the cockpit restarts on every code change): the exits still waiting for their resume,
        and every session id and command already relaunched once."""
        try:
            records = self.action_log.since(self.clock.now() - WRONG_CLEAR_DAYS * 86400)
        except SourceUnavailable:
            return {}, set()
        ended = {r.get("id") for r in records if r.get("event") in ("relaunch_typed", "relaunch_dropped")}
        exits = [r for r in records if r.get("event") == "relaunch_exit"]
        return ({r["id"]: {k: r[k] for k in ("t", "session", "session_id", "pane", "command")} for r in exits if r["id"] not in ended},
                {(r["session_id"], r.get("command", "")) for r in exits})

    def window_step(self, rows: List[dict], paused: bool) -> int:
        """Its first step when it turns on is /autocompact 1000000 once per model per cswap account, and /autocompact
        200000 when it turns off; never while the pause file exists (the owner, 2026-10-16). A held step is logged once
        and sent once the pause lifts; a pair whose session shows up later gets it then."""
        switched_on = bool(self.thresholds.value("autopilot_on"))
        now = self.clock.now()
        reachable = [r for r in rows if not self.held_unreachable(r, now)]
        commands = window_commands(switched_on, reachable, self.window_set)
        if not commands:
            return 0
        if paused:
            if not self.window_held:
                self.window_held = True
                self.log("autopilot: /autocompact step held, the team is paused")
                self.write({"t": now, "event": "held", "origin": "autopilot", "kind": "window",
                            "level": commands[0]["level"], "why": "the pause file exists, so nothing was typed"})
            return 0
        by_name = {r["name"]: r for r in rows}
        sent = 0
        for command in commands:
            row = by_name[command["session"]]
            result = self.controls.send(row, "window", command["text"], command["level"], "autopilot",
                                        f"sets the window for {command['model']} on account {command['account']} to {command['level']}")
            sent += result["ok"]
            if result["ok"]:
                self.refusals.pop(row["name"], None)
                self.window_set[window_key(row)] = command["level"]
            else:
                self.refused(row, "window", result["error"], now)
        self.window_held = False
        return sent

    def held_unreachable(self, row: dict, now: float) -> bool:
        pane, until, _ = self.unreachable.get(row["name"], ("", 0, ""))
        return now < until and row["pane"] == pane

    def refused(self, row: dict, kind: str, error: str, now: float) -> None:
        """A pane herdr does not know as an agent (a restarted agent, a wrapped shell) refuses the text. It is tried
        again only after the hold, and the refusal goes to actions.jsonl and Background jobs, not only to the console."""
        until = now + UNREACHABLE_HOLD_S
        if row.get("cache_ttl") and row.get("last_turn_at") and now < row["last_turn_at"] + row["cache_ttl"]:
            # A warm cache's hold ends where its compaction window opens: a 30-minute hold hid agent-ddp's 55-minute one (2026-10-23).
            until = min(until, row["last_turn_at"] + compaction_starts(row["cache_ttl"], self.thresholds, self.read_gap))
        self.unreachable[row["name"]] = (row["pane"], until, error)
        self.log(f"autopilot: {row['name']}: {error}; not tried again until {clock_time(until)}")
        self.refusals[row["name"]] = self.refusals.get(row["name"], 0) + 1
        if self.refusals[row["name"]] == 2:
            try:
                self.controls.panes.notify("Cockpit", f"{row['name']} refused the autopilot twice: {error[:120]}")
            except SourceUnavailable as failed:
                self.log(f"autopilot: notification: {failed}")
        self.write({"t": now, "event": "refused", "origin": "autopilot", "kind": kind, "session": row["name"],
                    "pane": row["pane"], "why": error})

    def unreachable_skips(self, rows: List[dict], now: float) -> List[dict]:
        return [{"session": r["name"], "rule": "Any control",
                 "why": f"its pane {r['pane']} refused the last text ({self.unreachable[r['name']][2]}); tried again at "
                        f"{clock_time(self.unreachable[r['name']][1])}"}
                for r in rows if self.held_unreachable(r, now)]

    def last_window_levels(self) -> dict:
        try:
            sent = [r for r in self.action_log.since(0) if r.get("kind") == "window" and r.get("event") == "sent"]
        except SourceUnavailable:
            return {}
        return {window_key(r): r.get("level") for r in sent}

    def judge_clears(self, rows: List[dict], now: float) -> dict:
        """A clear is wrong when the session after it reads, in its first turns, a file its last task read or changed:
        it had to load again what the clear dropped. Each one is logged once in actions.jsonl. Returns the wrong
        clears per session in 7 days."""
        try:
            records = self.action_log.since(now - WRONG_CLEAR_DAYS * 86400)
        except SourceUnavailable:
            return {}
        wrong = [r for r in records if r.get("event") == "wrong_clear"]
        judged = {r.get("id") for r in records if r.get("event") in ("wrong_clear", "right_clear")}
        by_name = {r["name"]: r for r in rows}
        for clear in (r for r in records if r.get("event") == "cleared" and r.get("id") not in judged):
            row = by_name.get(clear.get("session"))
            if not row or (row.get("started_at") or 0) <= clear["t"]:
                continue
            hits = sorted(set(row.get("first_reads") or []) & set(clear.get("files") or []))
            if hits:
                record = {"t": now, "event": "wrong_clear", "origin": "autopilot", "id": clear["id"], "session": clear["session"],
                          "bead": clear.get("bead", ""), "files": hits}
                self.write(record)
                wrong.append(record)
                self.log(f"autopilot: wrong clear of {clear['session']}: its new session read {len(hits)} file(s) of its last task again")
            elif row.get("first_reads"):
                self.write({"t": now, "event": "right_clear", "origin": "autopilot", "id": clear["id"], "session": clear["session"],
                            "bead": clear.get("bead", "")})
        counts: dict = {}
        for r in wrong:
            counts[r["session"]] = counts.get(r["session"], 0) + 1
        return counts

    def judge_compacts(self, rows: List[dict], now: float) -> None:
        try:
            records = self.action_log.since(now - WRONG_CLEAR_DAYS * 86400)
        except SourceUnavailable:
            return
        judge_compacts(records, rows, now, self.write, self.log)

    def write(self, record: dict) -> None:
        try:
            self.action_log.append(record)
        except SourceUnavailable as error:
            self.log(f"action log: {error}")

    def today(self) -> dict:
        """What it did today, from its log: each compaction with its reason and proved outcome, and the context it cut."""
        now = self.clock.now()
        try:
            records = self.action_log.since(midnight(now))
            week = self.action_log.since(now - WRONG_CLEAR_DAYS * 86400)
        except SourceUnavailable as error:
            return {"on": bool(self.thresholds.value("autopilot_on")), "error": str(error), "rows": [], "cut": 0, "done": 0}
        rows = sorted(day_rows(records, "autopilot", now) + kept_rows(records), key=lambda r: -r["at"])
        wrongs = marked(week)
        for row in rows:
            row["wrong"] = wrong_state(wrongs.get(row["id"]), week)
        done = [r["cut"] for r in rows if r["cut"] is not None]
        return {"on": bool(self.thresholds.value("autopilot_on")), "error": "", "rows": rows, "cut": sum(done), "done": len(done),
                "clears": self.clears_of_week(now)}

    def clears_of_week(self, now: float) -> List[dict]:
        """Per session in 7 days: the autopilot's clears and compacts judged right and wrong, and whether it gets only compact now."""
        try:
            records = self.action_log.since(now - WRONG_CLEAR_DAYS * 86400)
        except SourceUnavailable:
            return []
        found: dict = {}
        latest_compact = {r.get("id"): r for r in records if r.get("event") in ("right_compact", "wrong_compact")}
        for r in records:
            if r.get("event") in VERDICTS and (r.get("event") not in ("right_compact", "wrong_compact") or latest_compact.get(r.get("id")) is r):
                counts = found.setdefault(r["session"], dict.fromkeys(VERDICTS, 0))
                counts[r["event"]] += 1
        return [{"session": name, "clears": c["cleared"], "wrong": c["wrong_clear"], "right": c["right_clear"],
                 "compacts_right": c["right_compact"], "compacts_wrong": c["wrong_compact"],
                 "only_compact": c["wrong_clear"] >= WRONG_CLEARS_TO_STOP}
                for name, c in sorted(found.items())]


def kept_rows(records: List[dict]) -> List[dict]:
    """A TASK the autopilot kept as it was typed nothing, so only its task_start record shows the decision."""
    return [{"t": clock_time(r["t"]), "at": r["t"], "session": r["session"], "kind": "keep", "text": "", "id": f"task:{r['task']}",
             "reason": f"{TASK_START}: {r['why']}", "state": "kept", "result": "Kept as it was: nothing typed.", "cut": None}
            for r in records if r.get("event") == "task_start" and r.get("action") == "keep"]


def wrong_state(wrong: Optional[dict], records: List[dict]) -> str:
    """What the owner's wrong click did to the decision: empty when not marked."""
    if wrong is None:
        return ""
    if not wrong.get("undo"):
        return f"Marked wrong: {wrong['why']}."
    sent = any(r.get("event") == "undo_sent" and r.get("of") == wrong["of"] for r in records)
    return "Marked wrong: undone, relaunched with team.json's own flags." if sent else "Marked wrong: undo waits for its next idle moment."
