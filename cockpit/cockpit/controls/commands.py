import shlex
from abc import ABC, abstractmethod
from typing import Optional, Tuple

from cockpit.compaction.auto_compact_window import OFF_WINDOW
from cockpit.compaction.sweet_spot import TRIGGER_OFFSET
from cockpit.autopilot.window_step import window_level
from cockpit.controls.action import Action
from cockpit.controls.permission_rules import EFFORTS, clear_permission
from cockpit.display_time import clock_time
from cockpit.sessions.launch_options import options
from cockpit.transcripts.cache_rewrites import REWRITE_SHARE
from cockpit.transcripts.session_stats import SessionStats


# Claude Code compacts at the window minus min(max output, 20k) minus 13k, so the point moves by up to about 20k.
TRIGGER_SLACK = 20_000


def kilo(tokens: Optional[float]) -> str:
    return "?" if tokens is None else f"{round(tokens / 1000)}k"


class ControlCommand(ABC):
    """Command (design chat D10): one control's rule, what it types, and how the transcript proves it. Controls is the
    template around them: check, type, then wait for the proof."""
    kind = ""
    holds_session = True       # nothing else is sent to the session until its proof comes
    proof_window_s = 15 * 60   # None: its proof can take as long as the next compaction
    rechecked = False          # after its proof, a later source confirms it or refutes it

    def refutation(self, action: Action, row: dict, stats: Optional[SessionStats]) -> str:
        """The sentence that proves it did not take, or "" (most controls only wait and then go unseen)."""
        return ""

    def confirmation(self, action: Action, row: dict, stats: Optional[SessionStats]) -> str:
        """The second check's sentence once it shows, or "" (only a rechecked command has one)."""
        return ""

    @abstractmethod
    def text(self, row: dict, level: str) -> Tuple[Optional[str], str]:
        """What to type, or None with the reason it is not allowed now."""

    @abstractmethod
    def proof(self, action: Action, row: dict, stats: Optional[SessionStats]) -> str:
        """The sentence that proves it from the transcript, or "" while it has not shown."""

    @abstractmethod
    def awaited(self, action: Action) -> str:
        pass


class Compact(ControlCommand):
    kind = "compact"

    def text(self, row, level):
        return ("/compact", "") if row["can_compact"] else (None, row["why"] or "It is under its sweet spot, so compacting costs more than it saves.")

    def proof(self, action, row, stats):
        after = [c for c in stats.compactions if c.at >= action.sent_at] if stats else []
        if not after:
            return ""
        first = min(after, key=lambda c: c.at)
        post = first.post or first.first_context
        if post is None:
            return f"Done at {clock_time(first.at)}: {kilo(first.pre)} compacted (compact_boundary); its next turn shows the new size."
        return f"Done at {clock_time(first.at)}: {kilo(first.pre)} to {kilo(post)} (compact_boundary)."

    def awaited(self, action):
        return "Waiting for its compact_boundary record."


class Clear(ControlCommand):
    kind = "clear"

    def text(self, row, level):
        allowed, why = clear_permission(row)
        return ("/clear", "") if allowed else (None, why)

    def proof(self, action, row, stats):
        if row["session_id"] and row["session_id"] != action.before_session_id:
            return f"Done: new session {row['session_id'][:8]}, context {kilo(action.before_context)} before, {kilo(row['context'])} now."
        return ""

    def awaited(self, action):
        return "Waiting for its new session after /clear."


class Effort(ControlCommand):
    kind = "effort"
    # Only its next turn shows it, and an idle session may take none for hours (brain's report F2): it waits for that
    # turn instead of reading "not proved", and holds nothing else back meanwhile.
    holds_session = False
    proof_window_s = None

    def text(self, row, level):
        if level not in EFFORTS:
            return None, f"Effort must be one of {', '.join(EFFORTS)}."
        if level == row["effort"]:
            return None, f"It already runs at {level}."
        return f"/effort {level}", ""  # keeps the cache on the 5.5 models (docs/COMPACTION.md rule 9)

    def proof(self, action, row, stats):
        if stats and stats.last_turn_at and stats.last_turn_at >= action.sent_at and stats.effort == action.level:
            return f"Done: its turn at {clock_time(stats.last_turn_at)} ran at {action.level} (was {action.before_effort or 'unknown'})."
        return ""

    def awaited(self, action):
        return f"Waiting for its next turn to run at {action.level}."


class Prompt(ControlCommand):
    """A Needs you prompt; its text is the core's, chosen by the row, so text() is never asked."""
    kind = "prompt"

    def text(self, row, level):
        return None, "A prompt is sent from its Needs you row."

    def proof(self, action, row, stats):
        if stats and stats.last_turn_at and stats.last_turn_at >= action.sent_at:
            return f"Done: its turn at {clock_time(stats.last_turn_at)} read it."
        return ""

    def awaited(self, action):
        return "Waiting for its next turn."


class Probe(ControlCommand):
    """The autopilot's keep-warm probe (mb-s347.1): one short prompt whose turn must read the context from the cache.
    Its request is the proof: a cache read of about the context it had is a warm cache, a rewrite refutes it."""
    kind = "probe"
    proof_window_s = 15 * 60

    def text(self, row, level):
        return None, "A probe is the autopilot's, near the end of an idle session's cache life."

    def answered(self, action: Action, stats: Optional[SessionStats]) -> bool:
        return bool(stats and stats.last_turn_at and stats.last_turn_at >= action.sent_at)

    def proof(self, action, row, stats):
        if self.answered(action, stats) and stats.last_read >= REWRITE_SHARE * stats.last_context:
            return f"Done: its turn at {clock_time(stats.last_turn_at)} read {kilo(stats.last_read)} of {kilo(stats.last_context)} from the cache."
        return ""

    def refutation(self, action, row, stats):
        if self.answered(action, stats) and stats.last_write >= REWRITE_SHARE * stats.last_context:
            return (f"The cache was already cold: its turn at {clock_time(stats.last_turn_at)} wrote {kilo(stats.last_write)} "
                    f"of {kilo(stats.last_context)}.")
        return ""

    def awaited(self, action):
        return "Waiting for its probe turn to show a cache read."


class Model(ControlCommand):
    """Sent by the autopilot only at a clear or once the cache is cold, so the switch costs no re-read (rules.py)."""
    kind = "model"
    # Only its next turn shows it, and an idle session may take none for hours (brain's report F2): it waits for that
    # turn instead of reading "not proved", and holds nothing else back meanwhile.
    holds_session = False
    proof_window_s = None

    def text(self, row, level):
        return None, "A model change is the autopilot's, at a clear or a cold cache."

    def proof(self, action, row, stats):
        if stats and stats.last_turn_at and stats.last_turn_at >= action.sent_at and stats.model.startswith(action.level):
            return f"Done: its turn at {clock_time(stats.last_turn_at)} ran on {action.level}."
        return ""

    def awaited(self, action):
        return f"Waiting for its next turn on {action.level}."


class Window(ControlCommand):
    """The autopilot's /autocompact step (the owner's one exception to "never change ~/.claude", REQUIREMENTS.md).
    Only a compaction proves it: a project settings file can override the account's setting (brain's report F11: a
    300k line in .claude/settings.local.json beat the 1M), so the settings file only says it was saved. Claude Code
    compacts by itself near the window minus 33k: an automatic compaction there proves it, one well below refutes it,
    and a manual one proves it only above what the 200k default would have allowed."""
    kind = "window"
    holds_session = False      # its proof is a compaction, which the other rules must stay free to send
    proof_window_s = None

    def text(self, row, level):
        return None, "The auto-compact window is the autopilot's, when it turns on or off."

    def proof(self, action, row, stats):
        found, verified = self.deciding(action, stats)
        return f"Its compaction at {clock_time(found.at)} came at {kilo(found.pre)} ({found.trigger}), as a {kilo(window_of(action))} window allows." \
            if verified else ""

    def refutation(self, action, row, stats):
        found, verified = self.deciding(action, stats)
        return f"Not applied: its compaction at {clock_time(found.at)} came at {kilo(found.pre)} ({found.trigger}); a project " \
               f"settings file may override it." if found and verified is False else ""

    def deciding(self, action, stats):
        window = window_of(action)
        trigger = window - TRIGGER_OFFSET
        after = sorted((c for c in (stats.compactions if stats else []) if c.at >= action.sent_at and c.pre), key=lambda c: c.at)
        for c in after:
            if c.trigger == "auto":
                return c, abs(c.pre - trigger) <= TRIGGER_SLACK
            if c.pre > trigger + TRIGGER_SLACK:
                return c, False
            if window > OFF_WINDOW and c.pre > OFF_WINDOW - TRIGGER_OFFSET + TRIGGER_SLACK:
                return c, True
        return None, None

    def awaited(self, action):
        return f"Saved as {kilo(window_of(action))}; waiting for a compaction to show it applies (a project settings file can override it)."


class Relaunch(ControlCommand):
    """The autopilot's /exit, then the resume with the session's full flags typed into its shell (autopilot.py). Its
    proof is a process started after the /exit whose argv (herdr) carries every flag the resume typed: a start mode
    line is not enough, since a resume can write none (brain, pg-o1sq relaunch HOLD: its "not_seen" was wrong)."""
    kind = "relaunch"

    def text(self, row, level):
        return None, "A relaunch is the autopilot's, once its cache is cold."

    def proof(self, action, row, stats):
        if restarted(action, row) and not missing_typed(action, row):
            modes = f"; its start shows {', '.join(row['start_modes'])}" if row.get("start_modes") else ""
            return f"Done: its process started at {clock_time(row['process_started_at'])} with every flag its resume typed{modes}."
        return ""

    def refutation(self, action, row, stats):
        missing = missing_typed(action, row) if restarted(action, row) else []
        return f"Its process started at {clock_time(row['process_started_at'])} without {', '.join(missing)}." if missing else ""

    def awaited(self, action):
        return "Waiting for it to exit and start again with its full flags."


def restarted(action: Action, row: dict) -> bool:
    return bool(row.get("flags_known")) and (row.get("process_started_at") or 0) >= action.sent_at


def missing_typed(action: Action, row: dict) -> list:
    """The flags of the typed resume (Q_TERM=1 claude --resume <id> ...) its live argv lacks."""
    typed = [(f, v) for f, v in options(shlex.split(action.level or "")) if f != "--resume"]
    live = set(options(row.get("flags") or []))
    return [f"{f} {v}".strip() for f, v in typed if (f, v) not in live]


def window_of(action: Action) -> int:
    return window_level(action.level) or OFF_WINDOW


COMMANDS = {c.kind: c for c in (Compact(), Clear(), Effort(), Prompt(), Probe(), Model(), Window(), Relaunch())}
