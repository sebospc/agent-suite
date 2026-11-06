import re
from typing import Dict, List, Optional, Tuple

from cockpit.compaction.auto_compact_window import MAX_SETTABLE, MIN_SETTABLE, OFF_WINDOW, ON_WINDOW

# Opus, Sonnet and Fable get 1M while the autopilot compacts them at their sweet spot (the owner, 2026-10-16).
WINDOWED_FAMILIES = ("opus", "sonnet", "fable")
# Haiku bills 5 times above 100k, so its window follows its live sweet spot instead (the owner, 2026-10-17: the autopilot
# "(the owner's words)"). Its spot moves between 95k and 100k from read to read,
# and both get the same window under the step (sweet_spot.py), so a changed window is retyped at once.
# Claude Code saves /autocompact under the canonical name and matches [1m] and dated ids to it.
VARIANT_SUFFIX = re.compile(r"(\[1m\]|-\d{8})$")
LEGACY_LEVELS = {"on": ON_WINDOW, "off": OFF_WINDOW}  # what actions.jsonl held before levels were token counts


def canonical_model(model_id: str) -> str:
    model = model_id.strip().lower()
    while VARIANT_SUFFIX.search(model):
        model = VARIANT_SUFFIX.sub("", model)
    return model


def family(model: str) -> str:
    return next((f for f in WINDOWED_FAMILIES + ("haiku",) if f"-{f}-" in f"-{model}-"), "")


def window_key(row: dict) -> Tuple[str, str]:
    return row.get("account") or "", canonical_model(row.get("model_id") or "")


def window_level(level: str) -> Optional[int]:
    if level in LEGACY_LEVELS:
        return LEGACY_LEVELS[level]
    return int(level) if level and level.isdigit() else None


def target_window(row: dict, switched_on: bool) -> Optional[int]:
    """What the window of this session's model should be now, or None to leave it alone. Haiku's comes from its own
    sweet spot (its trigger plus Claude Code's 33k), clamped to what /autocompact takes; none before it has one."""
    kind = family(window_key(row)[1])
    if kind in WINDOWED_FAMILIES:
        return ON_WINDOW if switched_on else OFF_WINDOW
    if kind == "haiku" and row.get("window"):
        return max(MIN_SETTABLE, min(MAX_SETTABLE, int(row["window"])))
    return None


def needs_typing(target: int, last: Optional[int], haiku: bool) -> bool:
    if last is None:
        return haiku or target != OFF_WINDOW  # a model never set has Claude Code's 200k already
    return target != last


def window_commands(switched_on: bool, rows: List[dict], last_set: Dict[Tuple[str, str], str]) -> List[dict]:
    """One /autocompact per model per cswap account (the owner, 2026-10-16: each account has its own settings folder),
    into one live session of it, idle first: an idle session applies it now, a busy one after its turn."""
    chosen = {}
    for row in sorted(rows, key=lambda r: (r["state"] != "idle", r["name"])):
        key = window_key(row)
        target = target_window(row, switched_on)
        if row["state"] in ("idle", "busy") and row["pane"] and key[0] and target is not None and key not in chosen \
                and needs_typing(target, window_level(last_set.get(key, "")), family(key[1]) == "haiku"):
            chosen[key] = (row, target)
    return [{"session": row["name"], "account": account, "model": model, "text": f"/autocompact {target}", "level": str(target)}
            for (account, model), (row, target) in sorted(chosen.items())]
