from typing import Callable, List

from cockpit.action_log.action_log import ActionLog
from cockpit.snapshot.health_tables import table
from cockpit.snapshot.lights import light
from cockpit.source_unavailable import SourceUnavailable

DAY = 86400
RULE = "WATCH when Jev's own tokens of 24 h are over 1% of the team's tokens without cache: the judge then costs more than it can save"
SOURCE = "~/.cockpit/jev_calls.jsonl: one line per Jev request, with the usage TypeSafe returns"


class JevCalls:
    """Jev's own calls and tokens (design pg-45v5, measured from day one): what the classifier costs, beside what it
    is meant to save."""

    def __init__(self, log: ActionLog, now: Callable[[], float], on_error: Callable[[str], None]):
        self.log = log
        self.now = now
        self.on_error = on_error

    def record(self, key: str, questions: int, usage: dict) -> None:
        try:
            self.log.append({"t": self.now(), "key": key, "questions": questions,
                             "in": int(usage.get("input_tokens") or 0), "out": int(usage.get("output_tokens") or 0)})
        except (SourceUnavailable, TypeError, ValueError) as error:
            self.on_error(f"jev calls: {error}")

    def light(self, team_tokens_24h: int) -> dict:
        now = self.now()
        try:
            week = self.log.since(now - 7 * DAY)
        except SourceUnavailable as error:
            return light("jev_cost", "Jev's own cost", "unknown", "unknown", "", str(error), RULE, SOURCE)
        day = [r for r in week if r["t"] >= now - DAY]
        rows = [period_row("24 h", day), period_row("7 days", week)]
        tokens = rows[0]["in"] + rows[0]["out"]
        share = tokens / team_tokens_24h if team_tokens_24h else 0.0
        why = (f"{rows[0]['calls']} Jev calls in 24 h used {tokens:,} tokens"
               + (f", {share:.2%} of the team's {team_tokens_24h:,} tokens without cache" if team_tokens_24h else ""))
        columns = [("period", "Period", "text"), ("calls", "Calls", "count"), ("questions", "Questions", "count"),
                   ("in", "Input", "tokens"), ("out", "Output", "tokens")]
        return light("jev_cost", "Jev's own cost", f"{tokens:,} tokens in 24 h", "watch" if share > 0.01 else "ok", "", why + ".",
                     RULE, SOURCE, table("Jev's requests and the tokens TypeSafe counted", columns, rows))


def period_row(period: str, records: List[dict]) -> dict:
    return {"id": period, "period": period, "calls": len(records), "questions": sum(r.get("questions", 0) for r in records),
            "in": sum(r.get("in", 0) for r in records), "out": sum(r.get("out", 0) for r in records)}
