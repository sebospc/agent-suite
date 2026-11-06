from datetime import datetime, timezone
import time
from typing import List, Optional, Tuple

from cockpit.board.bead import Bead
from cockpit.compaction.inputs_from_stats import inputs_for
from cockpit.compaction.price_table import PriceTable
from cockpit.compaction.recovery_mix import RecoveryMix
from cockpit.compaction.ceiling import ceiling
from cockpit.compaction.sweet_spot import extra_per_turn, recovery_cost, recovery_tokens, sweet_spot
from cockpit.display_time import age, clock_time
from cockpit.idle_cost.idle_gap import IdleGap
from cockpit.idle_cost.idle_policies import actual, break_even_cap, eligible_for_probe
from cockpit.idle_cost.rules_from import rules_from
from cockpit.live_sessions.live_session import LiveSession
from cockpit.sessions.model_names import model_label
from cockpit.thresholds import Thresholds
from cockpit.transcripts.session_stats import SessionStats

K = 1000


def context_boost(role: str, thresholds) -> float:
    # The owner can let one session grow for a day before the autopilot compacts it (thresholds.json context_boost).
    # A boost with no "until" stays until the owner changes it (owner 2026-11-03: brain 2x, no end date).
    boost = (thresholds.value("context_boost") if "context_boost" in thresholds.items else {}).get(role)
    until = boost.get("until") if boost else None
    if not boost or (until and datetime.now(timezone.utc) >= datetime.fromisoformat(until.replace("Z", "+00:00"))):
        return 1
    return boost["factor"]


def kilo(tokens: Optional[float]) -> str:
    return "" if tokens is None else f"{round(tokens / K)}k"


def session_row(role: str, live: Optional[LiveSession], stats: Optional[SessionStats], work: dict,
                held: List[Bead], plan: Optional[dict], fleet: List[SessionStats], thresholds: Thresholds,
                prices: PriceTable, now: float, state_file: str = "", state_file_at: Optional[float] = None,
                recovery: Optional[RecoveryMix] = None, task_kind: str = "", kind_source: str = "", memory_file: str = "") -> dict:
    row = {"name": role, "state": live.state if live else "off", "account": live.account if live else "",
           "pane": live.pane if live else "", "session_id": live.session_id if live else "",
           "bead": work["bead"], "tag": work["tag"], "kind": work["kind"], "work_line": work["line"],
           "model": "", "effort": "", "drift": "", "context": None, "spot": None, "window": None, "over": False, "ceiling": None, "idle_cost": None, "keep_warm": None,
           "tokens_24h": None, "advice": "", "inputs": [], "spot_kind": "", "idle_for": "", "notes_saved": None,
           "can_compact": False, "why": "", "haiku_over_step": False, "last_turn_at": None, "stuck": "", "marks": [],
           "holds": len(work["held"]), "held": list(work["held"]), "age": "", "compactions_today": [], "cache_ttl": None,
           "base": None, "start_load": None, "notes_file": state_file, "memory_file": memory_file, "unsaved_answers": [],
           "haiku_guarded": False, "refills": [], "model_id": "", "flags": list(live.flags) if live else [], "background": live.background if live else "", "flags_known": bool(live and live.flags_known), "process_started_at": live.started_at if live else 0.0, "launch": list((plan or {}).get("launch") or []),
           "plugins": [], "skills": [], "start_modes": [], "start_modes_note": ""}
    if live is None or stats is None:
        row["why"] = "Not running." if live is None else "No transcript for its session id under the transcripts folder: launched without cswap --share-history?"
        return row
    step = thresholds.value("haiku_step_tokens")
    shown = live.status_model or model_label(stats.model)
    row.update(last_turn_at=stats.last_turn_at, model=shown, model_id=stats.model, effort=stats.effort,
               context=stats.context_now, tokens_24h=stats.tokens_24h, tasks_closed=stats.tasks_closed,
               per_task=round(stats.tokens_24h / stats.tasks_closed) if stats.tasks_closed else None,
               idle_for=age(now - stats.last_turn_at) if stats.last_turn_at and live.state == "idle" else "")
    row["drift"] = drift(stats, plan)
    row["cache_ttl"] = stats.ttl_seconds
    # What a compaction cannot go below: its first turn's context (CLAUDE.md, tools, memory) or its last compaction's size.
    posts = [c.post for c in stats.compactions if c.post]
    row["base"] = max([stats.floor or 0] + posts[-1:]) or None
    row["start_load"] = stats.start_load  # its first request minus the message that started it (~ heuristic)
    row["cwd"] = stats.cwd
    row["started_at"] = stats.started_at
    row["task_files"], row["first_reads"] = sorted(stats.task_files), sorted(stats.first_reads)  # lists: the row goes out as JSON
    row["skills"] = sorted(stats.skills)
    row["last_auto_compaction_at"] = max((c.at for c in stats.compactions if c.trigger == "auto"), default=0.0)
    row["last_compaction_at"] = max((c.at for c in stats.compactions), default=0.0)
    row["start_modes"], row["start_modes_note"] = modes_since_start(stats, live.started_at)
    if stats.started_at:
        row["age"] = f"{stats.turns} turns in {age(now - stats.started_at)} since its fresh start"
    midnight = time.mktime(time.localtime(now)[:3] + (0, 0, 0, 0, 0, -1))
    row["compactions_today"] = [f"{clock_time(c.at)} {kilo(c.pre)} to {kilo(c.post or c.first_context)} ({c.trigger or 'unknown'})"
                                for c in stats.compactions if c.at >= midnight]
    if stats.context_now is None and stats.compactions:
        row["context_note"] = f"compacted {clock_time(stats.compactions[-1].at)}, size on its next turn"
    row["notes_saved"] = notes_saved(held, stats, state_file, state_file_at)
    # Design pg-o1sq Q13: after a restart it reads its state file again, or it works from what it forgot.
    row["notes_reread"] = (any(memory_file in target for target in stats.reads_since_start)
                           if memory_file and stats.reads_since_start is not None else None)
    # The thrash guard (COMPACTION.md rule 8) reads where each of the last two compactions left it.
    row["refills"] = [c.first_context for c in stats.compactions[-2:]]
    card = prices.card_for(stats.model, step)
    row["marks"] = model_marks(stats, card)
    inputs = inputs_for(stats, fleet, recovery) if card else None
    row["compaction_costs"] = compaction_costs(stats, inputs)
    spot = sweet_spot(inputs, card, thresholds.value("quality_cap_tokens")) if inputs else None
    context = stats.context_now or 0
    # An expensive recovery can put a Haiku session's sweet spot over the price step; then it is compacted at its
    # sweet spot like any other session, not kept under the step.
    row["haiku_guarded"] = "haiku" in stats.model and (spot is None or spot.trigger <= step)
    row["haiku_over_step"] = row["haiku_guarded"] and context > step
    if spot is None:
        row["advice"] = (f"No price card for {stats.model}, so no sweet spot." if not card
                         else "Not enough turns yet to measure its growth per turn.")
    else:
        boost = context_boost(role, thresholds)
        row.update(spot=spot.trigger * boost, window=spot.window, over=context > spot.trigger * boost, spot_kind=spot.kind,
                   ceiling=ceiling(inputs, card, spot) * boost, boost=boost)
        idle = actual(stats.idle_gaps_24h, card, stats.ttl_seconds, inputs, spot)
        row["idle_cost"] = {"usd": round(idle.usd, 2), "tokens": idle.tokens, "cold": idle.cold, "compacts": idle.compacts, "probes": idle.probes}
        row["keep_warm"] = keep_warm_of(context, card, stats.ttl_seconds, inputs, spot, rules_from(thresholds))
        row["advice"] = advice(context, spot, inputs, card, row["haiku_over_step"], step)
        row["inputs"] = [
            {"name": "P, size right after a compaction", "value": f"{kilo(inputs.P)}, {inputs.basis}"},
            {"name": "g, growth per turn", "value": f"{inputs.g / K:.1f}k, trimmed mean of the last {len(stats.growth)} turns"},
            {"name": "Task kind", "value": f"{task_kind}, from {kind_source}" if task_kind else f"not known yet: {kind_source}"},
            {"name": "R, recovery after a compaction", "value": recovery_line(inputs, card)},
            {"name": "C, cost of one compaction", "value": f"${spot.compaction_cost:.2f} at list price"},
            {"name": "Ceiling, compacts at the next finished turn", "value": f"{kilo(row['ceiling'])}, where carrying a chat of "
                                                                          f"1/q turns costs one compaction, within 1.25x to 2.5x the spot"},
            {"name": "r, cached read price", "value": f"${card.at(inputs.P).cache_read * 1e6:.2f} per M"
                                                      + ("" if card.is_flat else f", 5 times above {kilo(step)}")},
        ]
    row["can_compact"], row["why"] = compact_permission(row, bool(thresholds.value("autopilot_on")))
    return row


def keep_warm_of(context: int, card, ttl: int, inputs, spot, rules) -> dict:
    """What a keep-warm probe may do for this session now: allowed at or under the multiple of its spot, and how many
    probes cost what the cheaper alternative (a cold rewrite or a compaction) costs at its context."""
    cap, other = break_even_cap(IdleGap(0, context, False), card, ttl, inputs, spot, rules)
    return {"eligible": eligible_for_probe(context, spot, rules), "cap": cap, "instead": "compaction" if other.compacts else "a cold rewrite"}


def recovery_line(inputs, card) -> str:
    """What a compaction of this kind of task costs until the session edits again, beyond one normal turn."""
    mix = inputs.recovery
    if mix is None:
        return "not measured yet: no compaction has a finished recovery span, so R counts as 0"
    cost = f"{kilo(recovery_tokens(inputs))} tokens, ${recovery_cost(inputs, card):.2f} at list price"
    if mix.provisional:
        return f"{cost}; fleet value of its last {mix.compactions} compactions, provisional (too few of this kind)"
    return f"{cost}; mean of its kind's last {mix.compactions} compactions"


def model_marks(stats: SessionStats, card) -> List[str]:
    return [] if card else [f"no price for {stats.model or 'its model'}"]


def drift(stats: SessionStats, plan: Optional[dict]) -> str:
    if not plan:
        return ""
    gaps = []
    if plan.get("model") and not stats.model.startswith(plan["model"]):
        gaps.append(f"model {model_label(plan['model'])}")
    if plan.get("effort") and stats.effort and plan["effort"] != stats.effort:
        gaps.append(f"effort {plan['effort']}")
    return "team.json says " + " and ".join(gaps) if gaps else ""


def notes_saved(held: List[Bead], stats: SessionStats, state_file: str = "", state_file_at: Optional[float] = None) -> Optional[bool]:
    """Notes count as saved when they changed after its last turn STARTED: a session saves during a turn and replies
    after it, so the end of the turn is always later (bd notes carry no time of their own, so a bead's update stands
    in). A role session holds no bead; its state file is its memory, and a missing file is not saved."""
    if not stats.turn_started_at:
        return None
    if state_file:
        return (state_file_at or 0) >= stats.turn_started_at
    if not held:
        return None
    return any((b.last_update() or 0) >= stats.turn_started_at for b in held)


def advice(context, spot, inputs, card, over_step: bool, step: int) -> str:
    if over_step:
        return f"Haiku bills the whole request 5 times above {kilo(step)}, so its sweet spot stays under that line."
    if context > spot.trigger:
        extra = extra_per_turn(context, spot, inputs, card)
        return (f"Each turn re-reads {kilo(context - spot.trigger)} tokens it does not need, "
                f"about {round(extra * 100)}% more per turn than at its sweet spot.")
    return "Below its sweet spot, carrying this context costs less than compacting it."


def compact_permission(row: dict, autopilot_on: bool = False) -> Tuple[bool, str]:
    if not row["over"] and not row["haiku_over_step"]:
        return False, ""
    if row["state"] == "busy":
        return False, ("Busy. The autopilot compacts it once it is idle with its notes saved." if autopilot_on
                       else "Busy. Compact it when its turn ends.")
    if row["state"] != "idle":
        return False, f"It is {row['state']}, so wait."
    if row["notes_saved"] is False:
        return False, "Its notes were not saved after its last turn, so a compaction could lose work."
    if row["notes_saved"] is None:
        return True, "Idle. It holds no bead to show its notes are saved; check its pane first."
    return True, "Idle with its notes saved, so nothing is lost."


START_SLACK_S = 5  # its hooks run right after the record's startedAt; this covers the two clocks


def modes_since_start(stats, process_started_at: float) -> tuple:
    """Only the modes of a SessionStart record of this process: a resume whose hooks wrote no record would otherwise show
    the modes of a start days before, with plugins it no longer loads (brain, pg-g22n note)."""
    if not process_started_at or (stats.start_modes_at or 0) >= process_started_at - START_SLACK_S:
        return sorted(stats.start_modes), ""
    return [], f"no SessionStart record since its process started at {clock_time(process_started_at)}"


def compaction_costs(stats, inputs) -> list:
    """Per compaction: what its finished recovery span cost and what the cut saved, in input-token equivalents at the
    flat cards' ratios (cache read 0.1, write 1.25, output 5), None while the span is not finished; and how soon it was
    back near its size (refilled_s), what a Haiku compaction is judged by. The cut saves its re-read on every turn of a
    typical chat, 1/q turns; 10 when q is not known. Each request of the span is charged only what it cost over a normal
    turn at the compacted size, which it would have made anyway (panel cc0de8). A heuristic, not a measure."""
    turns = 1 / inputs.q if inputs and inputs.q else 10
    found = []
    for c in stats.compactions:
        after = c.post or c.first_context
        if not c.pre or not after:
            continue
        span = c.recovery
        normal_turn = 0.1 * after + (1.25 * inputs.g + 5 * inputs.y if inputs else 0)
        spent = span.fresh + 1.25 * span.write + 0.1 * span.read + 5 * span.out if span else 0
        found.append({"at": c.at, "refilled_s": c.refilled_s,
                      "recovery": round(max(0.0, spent - span.requests * normal_turn)) if span else None,
                      "saved": round(0.1 * max(0, c.pre - after) * turns) if span else None})
    return found
