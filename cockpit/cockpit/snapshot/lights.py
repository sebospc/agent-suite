from typing import List, Optional, Tuple

from cockpit.display_time import age
from cockpit.git.gate_state import GateState
from cockpit.snapshot.health_tables import context_table, holds_table, landed_table, main_table, tokens_table
from cockpit.snapshot.status_lines import with_cache

# Fixed order, so a light's position becomes memory (docs/DESIGN.md, layout B). act: the owner acts now;
# watch: abnormal, look when you can; ok: normal and quiet; unknown: its source could not be read.
# Each light carries the sentence, rule and source its detail band shows under the strip (design chat LI3).


def light(id: str, label: str, value: str, level: str, tab: str, why: str = "", rule: str = "", source: str = "",
          table: Optional[dict] = None) -> dict:
    """table: what its Team health dropdown shows; None when its source could not be read, and why says so."""
    return {"id": id, "label": label, "value": value, "level": level, "tab": tab, "why": why, "rule": rule, "source": source, "table": table}


def context_light(rows: List[dict]) -> dict:
    haiku = [r for r in rows if r["haiku_over_step"]]
    over = [r for r in rows if r["over"] and not r["haiku_over_step"]]
    rule = "ACT when a Haiku session is over 100k; WATCH when a session is over its sweet spot"
    source = "transcripts, the sweet-spot model"
    names = ", ".join(r.get("name", "") for r in haiku + over)
    if haiku:
        return light("context", "Context", f"{len(haiku) + len(over)} over", "act", "sessions",
                     f"{names}: Haiku bills every turn above 100k at 5 times the price.", rule, source, context_table(rows))
    if over:
        return light("context", "Context", f"{len(over)} over", "watch", "sessions",
                     f"{names} over the sweet spot: each turn re-reads context it does not need.", rule, source, context_table(rows))
    running = sum(1 for r in rows if r["state"] != "off")
    return light("context", "Context", f"{running} running", "ok", "sessions", "Every running session is under its sweet spot.", rule, source, context_table(rows))


def main_light(gate: Optional[GateState]) -> dict:
    rule = "ACT when the last gate is red; WATCH when commits wait to be pushed"
    source = gate.source if gate else "the gate logs verify_commit.sh writes"
    if gate and not gate.in_flight:
        return light("main", "Code", f"{gate.unpushed} to push" if gate.unpushed else "nothing in flight", "watch" if gate.unpushed else "ok",
                     "milestone", f"No gate in flight; the pushed head is {gate.commit[:8]}"
                     + (f"; {gate.unpushed} commits wait to be pushed." if gate.unpushed else "."), rule, source, main_table(gate))
    if gate is None or gate.green is None:
        return light("main", "Code", "running" if gate and gate.running else "unknown", "unknown", "milestone",
                     f"The gate on {gate.commit} is still running." if gate and gate.running else "No gate log is read yet.", rule, source)
    if gate.green is False:
        return light("main", "Code", f"red, {gate.commit[:7]}", "act", "milestone",
                     f"The gate on {gate.commit} failed: {gate.failing} failing test{'' if gate.failing == 1 else 's'}.", rule, source, main_table(gate))
    return light("main", "Code", f"{gate.unpushed} to push" if gate.unpushed else "green", "watch" if gate.unpushed else "ok", "milestone",
                 f"Gate green on {gate.commit}" + (f"; {gate.unpushed} commits wait to be pushed." if gate.unpushed else "."), rule, source, main_table(gate))


def tokens_light(tokens: Optional[Tuple[int, int, int]], section: Optional[dict] = None) -> dict:
    """WATCH once today is already over the 7-day average by its margin (design chat LI11); the value names the top
    spender, so the light says where to look."""
    rule, source = "WATCH once today is over the 6-day average by its margin", "transcripts, deduplicated by message id; without cache: fresh input and output"
    if not tokens:
        return light("tokens", "Tokens", "unknown", "unknown", "tokens", "Transcripts could not be read.", rule, source)
    section = section or {}
    top = f" {section['top']}" if section.get("top") else ""  # the top spender, named in full in its detail
    why = f"{tokens[1] / 1e6:.1f}M without cache so far today, {with_cache(tokens[1], tokens[2])}" + (f", {section['top']} spends most" if section.get("top") else "") + (f", over the 6-day average of {section['average'] / 1e6:.1f}M" if section.get("over_average") and section.get("average") else "") + "."
    result = light("tokens", "Tokens", f"{tokens[1] / 1e6:.1f}M{top}", "watch" if section.get("over_average") else "ok", "tokens",
                   why, rule, source, tokens_table(section))
    result["more"] = [landed_table(section.get("landed") or []), holds_table(section.get("holds"))]
    return result
