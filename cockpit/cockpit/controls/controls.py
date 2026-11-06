import threading
import uuid
from typing import Callable, Dict, List, Set

from cockpit.action_log.action_log import ActionLog
from cockpit.action_log.day_log import day_rows, midnight
from cockpit.clock.clock import Clock
from cockpit.controls.action import Action, from_record
from cockpit.controls.commands import COMMANDS
from cockpit.controls.effect import effect
from cockpit.controls.permission import command_for
from cockpit.panes.panes import Panes
from cockpit.source_unavailable import SourceUnavailable

SHOWN = 12


class Controls:
    """The owner's controls (phase 2) and the autopilot's (phase 3) take one path: typed into the session's pane, kept
    until its effect shows in the transcript, and logged with its before and its proved after."""

    def __init__(self, panes: Panes, clock: Clock, log: Callable[[str], None], action_log: ActionLog):
        self.panes = panes
        self.clock = clock
        self.log = log
        self.action_log = action_log
        self.actions: List[Action] = []
        self.resolved: Dict[str, str] = {}  # action id -> the outcome logged for it
        self.lock = threading.Lock()
        self.reload()

    def reload(self) -> None:
        """Today's controls still waiting for their proof, read back from the log: a restart (on every code change, pg-32oo)
        otherwise drops them and their proof is never matched (brain's pg-sb4m)."""
        try:
            records = self.action_log.since(midnight(self.clock.now()))
        except SourceUnavailable as error:
            self.log(f"action log: {error}")
            return
        ends = {r["id"]: r["event"] for r in records if r.get("event") in ("done", "confirmed", "failed", "not_seen")}
        typed = {r["id"] for r in records if r.get("event") in ("sent", "not_typed")}
        for r in records:
            # A typing line with no sent or not_typed after it: the cockpit stopped while typing it, so it may have gone out.
            cut_off = r.get("event") == "typing" and r["id"] not in typed
            if (r.get("event") != "sent" and not cut_off) or r.get("kind") not in COMMANDS or ends.get(r["id"]) in ("confirmed", "failed", "not_seen"):
                continue
            self.actions.append(from_record(r))
            if r["id"] in ends:
                self.resolved[r["id"]] = ends[r["id"]]

    def act(self, kind: str, session: str, level: str, rows: List[dict]) -> dict:
        row = next((r for r in rows if r["name"] == session), None)
        if row is None:
            return {"ok": False, "error": f"No session named {session}."}
        text, why = command_for(kind, row, level)
        if text is None:
            return {"ok": False, "error": why}
        return self.send(row, kind, text, level, "owner", "")

    def send(self, row: dict, kind: str, text: str, level: str, origin: str, reason: str) -> dict:
        action = Action(id=uuid.uuid4().hex[:8], kind=kind, session=row["name"], text=text, sent_at=self.clock.now(),
                        before_context=row["context"], before_effort=row["effort"], before_session_id=row["session_id"],
                        level=level, origin=origin, reason=reason)
        record = {"t": action.sent_at, "id": action.id, "event": "sent", "origin": origin, "kind": kind, "session": action.session,
                  "text": text, "level": level, "reason": reason, "account": row.get("account", ""), "model_id": row.get("model_id", ""),
                  "before_context": action.before_context, "before_effort": action.before_effort,
                  "before_session_id": action.before_session_id}
        # Logged before it is typed: a restart between the two finds the typing line (reload) and waits for its proof
        # instead of sending the same control again. Unlogged, it is not typed at all.
        try:
            self.action_log.append(dict(record, event="typing"))
        except SourceUnavailable as error:
            return {"ok": False, "error": f"not typed, the action log could not be written: {error}"}
        try:
            self.panes.type_into(row["pane"], text)
        except SourceUnavailable as error:
            self.write({"t": self.clock.now(), "id": action.id, "event": "not_typed", "origin": origin, "kind": kind,
                        "session": action.session, "why": str(error)})
            return {"ok": False, "error": str(error)}
        with self.lock:
            self.actions.append(action)
        self.write(record)
        self.log(f"control ({origin}): typed {text!r} into {action.session} ({row['pane']}); context {row['context']}, effort {row['effort']}")
        return {"ok": True, "id": action.id}

    def pending(self) -> Set[str]:
        """Sessions with a control still waiting for its proof: nothing more is sent to them until it resolves."""
        with self.lock:
            return {a.session for a in self.actions if a.id not in self.resolved and COMMANDS[a.kind].holds_session}

    def effects(self, rows: List[dict], stats_by_id: Dict[str, object], now: float) -> List[dict]:
        by_name = {r["name"]: r for r in rows}
        with self.lock:
            open_actions = [a for a in self.actions if self.still_open(a)]
            recent = list(self.actions[-SHOWN:])
        results = {}
        for action in {a.id: a for a in open_actions + recent}.values():
            row = by_name.get(action.session)
            if row is None:
                continue
            result = effect(action, row, stats_by_id.get(row["session_id"]), now)
            results[action.id] = dict(result, id=action.id, kind=action.kind, session=action.session, origin=action.origin)
            if result["state"] not in ("waiting", self.resolved.get(action.id)) and self.still_open(action):
                self.resolve(action, result, now)
        return [results[a.id] for a in reversed(recent) if a.id in results]

    def still_open(self, action: Action) -> bool:
        """Unresolved, or done and still waiting for its second check, whose outcome is logged as a second line."""
        outcome = self.resolved.get(action.id)
        return outcome is None or (outcome == "done" and COMMANDS[action.kind].rechecked)

    def resolve(self, action: Action, result: dict, now: float) -> None:
        with self.lock:
            self.resolved[action.id] = result["state"]
        self.write({"t": now, "id": action.id, "event": result["state"], "origin": action.origin, "kind": action.kind,
                    "session": action.session, "text": result["text"], "pre": result.get("pre"), "post": result.get("post"),
                    "proved_at": result.get("proved_at")})

    def today(self) -> dict:
        """The Sessions log: the owner's controls sent today with their proved results, read back from the log so a
        restart keeps them."""
        try:
            now = self.clock.now()
            return {"rows": day_rows(self.action_log.since(midnight(now)), "owner", now), "error": ""}
        except SourceUnavailable as error:
            return {"rows": [], "error": str(error)}

    def write(self, record: dict) -> None:
        try:
            self.action_log.append(record)
        except SourceUnavailable as error:  # the control itself went through; say the log did not
            self.log(f"action log: {error}")
