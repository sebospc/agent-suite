from typing import Optional

from cockpit.controls.action import Action
from cockpit.controls.commands import COMMANDS
from cockpit.display_time import clock_time
from cockpit.transcripts.session_stats import SessionStats


def effect(action: Action, row: dict, stats: Optional[SessionStats], now: float) -> dict:
    """waiting, done (then confirmed, for a rechecked command), failed or not seen, read from the transcript: a
    compact_boundary record, a new session after /clear, the effort on the session's next turn."""
    sent = f"Typed {action.text} into {action.session}'s pane at {clock_time(action.sent_at)}."
    command = COMMANDS[action.kind]
    refuted = command.refutation(action, row, stats)
    if refuted:
        return {"state": "failed", "text": f"{sent} {refuted}"}
    proof = command.proof(action, row, stats)
    if proof:
        confirmed = command.confirmation(action, row, stats)
        return dict({"state": "confirmed" if confirmed else "done", "text": " ".join(filter(None, (sent, proof, confirmed)))},
                    **cut(action, stats))
    if command.proof_window_s is not None and now - action.sent_at > command.proof_window_s:
        return {"state": "not_seen", "text": f"{sent} No proof in its transcript after {command.proof_window_s // 60} min; check its pane."}
    return {"state": "waiting", "text": f"{sent} {command.awaited(action)}"}


def cut(action: Action, stats: Optional[SessionStats]) -> dict:
    """The measured before and after of a compaction, for the log and the autopilot's tokens figure."""
    if action.kind != "compact" or stats is None:
        return {}
    after = [c for c in stats.compactions if c.at >= action.sent_at]
    first = min(after, key=lambda c: c.at) if after else None
    return {"pre": first.pre, "post": first.post or first.first_context, "proved_at": first.at} if first else {}
