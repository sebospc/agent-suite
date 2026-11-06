from typing import List, Optional

from cockpit.snapshot.health_tables import autopilot_table, clears_table, coordination_table, disk_table, memory_table, said_table
from cockpit.snapshot.lights import light

GB = 1024 ** 3

# Team health (the owner, 2026-10-15: "health check como sección de salud del equipo"; 2026-10-16: "said vs saved ...
# todos los recursos, tokens, memory, disk, todo todo"): the areas the lights did not cover yet.


def memory_light(rows: List[dict]) -> dict:
    """What each session loads before any work, against its role's usual, and whether its notes are saved."""
    rule = "WATCH when a session's start load is over its role's usual by its margin, or its notes were not saved during its last turn"
    over = [r["name"] for r in rows if r.get("start_over")]
    unsaved = [r["name"] for r in rows if r["state"] == "idle" and r["notes_saved"] is False]
    loads = sorted(r["start_load"] for r in rows if r.get("start_load"))
    problems = [p for p in (f"{', '.join(over)} start{'s' if len(over) == 1 else ''} heavier than usual" if over else "",
                            f"{', '.join(unsaved)}: notes not saved during the last turn" if unsaved else "") if p]
    return light("memory", "Memory", f"start ~{round(loads[len(loads) // 2] / 1000)}k" if loads else "no start read",
                 "watch" if problems else "ok", "sessions",
                 "; ".join(problems) + "." if problems else "Every session starts at its usual size and its idle sessions saved their notes.", rule,
                 "transcripts (first request minus its first message), bd notes, role state files", memory_table(rows))


def said_light(saved: Optional[dict], needs: List[dict]) -> dict:
    """What was said against what lasts: answers in DECISIONS.md, ids that exist, 'saved' with an id, the saved guard."""
    rule = "WATCH when an answer is not in DECISIONS.md, a reply says saved with no id, names a missing id, or the guard stopped one"
    saved = saved or {}
    missing = len(saved.get("not_in_decisions", []))
    no_id = sum(saved.get("without_id", {}).values())
    named = [n for n in needs if n["id"].startswith("missing-")]
    blocks = saved.get("blocks", 0)
    problems = [p for p in (f"{missing} answer{'s' if missing != 1 else ''} not in DECISIONS.md" if missing else "",
                            f"{no_id} 'saved' with no id" if no_id else "",
                            f"{blocks} stopped by the saved guard" if blocks else "") if p]
    # Each row says which id, and quotes the reply line it came from.
    problems += [n.get("text", n["id"]).rstrip(".") for n in named]
    return light("said", "Said vs saved", f"{len(problems)} gap{'s' if len(problems) != 1 else ''}" if problems else "all saved",
                 "watch" if problems else "ok", "", "; ".join(problems) + "." if problems else "What was said today is saved with an id.",
                 rule, "panel.json, DECISIONS.md, bd, git, transcript replies of 24 h, the saved guard's log", said_table(saved))


def disk_light(disk: Optional[dict], min_gb: float, watch_gb: float, error: str = "") -> dict:
    rule = f"ACT under {min_gb:g} GB free (no build starts, WORKFLOW Disk); WATCH under {watch_gb:g} GB"
    if disk is None:
        return light("disk", "Disk", "unknown", "unknown", "", error or "Not read.", rule, "disk usage")
    free = disk["free"] / GB
    folders = ", ".join(f"{name} {size / GB:.1f} GB" for name, size in disk["folders"].items() if size is not None)
    level = "act" if free < min_gb else "watch" if free < watch_gb else "ok"
    return light("disk", "Disk", f"{free:.0f} GB free", level, "",
                 f"{free:.0f} GB free of {disk['total'] / GB:.0f} GB on {disk['volume']}" + (f"; {folders}." if folders else "."), rule,
                 "disk usage of the data volume and the team's folders (sized every 10 min)", disk_table(disk))


def coordination_light(process: Optional[dict], needs: List[dict]) -> dict:
    """Messages between sessions: duplicates, the format, the review receipts, and the team rules."""
    rule = "ACT when review receipts do not match; WATCH on a duplicate, a message outside the format or a broken team rule"
    source = "transcripts (messages between sessions), bd"
    if process is None:
        return light("coordination", "Coordination", "unknown", "unknown", "tokens", "Transcripts could not be read.", rule, source)
    receipts = any(n["id"] == "receipts" for n in needs)
    rules = any(n["id"] == "team-rules" for n in needs)
    week = process["this_week"]
    problems = [p for p in ("review receipts do not match" if receipts else "",
                            f"{process['today_duplicates']} duplicate{'s' if process['today_duplicates'] != 1 else ''} today" if process["today_duplicates"] else "",
                            f"{week['outside_format']} message{'s' if week['outside_format'] != 1 else ''} outside the format this week" if week["outside_format"] else "",
                            "team rules broken" if rules else "") if p]
    level = "act" if receipts else "watch" if problems else "ok"
    return light("coordination", "Coordination", f"{len(problems)} issue{'s' if len(problems) != 1 else ''}" if problems else "in order",
                 level, "tokens", "; ".join(problems) + "." if problems else
                 f"{week['messages']} messages this week, " + (f"median {week['median']} per bead" if week.get("beads", 1) else "none names a bead")
                 + ", none duplicated.", rule, source, coordination_table(process))


def autopilot_light(today: dict, paused: bool) -> dict:
    result = autopilot_state(today, paused)
    result["more"] = [clears_table(today.get("clears", []))]
    return result


def autopilot_state(today: dict, paused: bool) -> dict:
    """Whether the autopilot runs and its actions took (the owner, 2026-10-16: the autopilot "debe afectar algo en el
    team health")."""
    rule = "WATCH when it is stopped in config/thresholds.json, or an action today failed or went unproved"
    source = "actions.jsonl, config/thresholds.json"
    if today.get("error"):
        return light("autopilot", "Autopilot", "unknown", "unknown", "jobs", f"actions.jsonl could not be read: {today['error']}", rule, source)
    unproved = [r for r in today["rows"] if r["state"] in ("failed", "not_seen")]
    cut = f"{round(today['cut'] / 1000)}k cut in {today['done']}" if today["done"] else "nothing cut"
    if not today["on"]:
        return light("autopilot", "Autopilot", "stopped", "watch", "jobs",
                     "autopilot_on is false in config/thresholds.json: nothing compacts or clears idle sessions by itself.", rule, source, autopilot_table(today))
    if unproved:
        return light("autopilot", "Autopilot", f"{len(unproved)} not proved", "watch", "jobs",
                     "; ".join(f"{r['session']}: {r['result'] or r['text']}" for r in unproved), rule, source, autopilot_table(today))
    return light("autopilot", "Autopilot", "paused" if paused else cut, "ok", "jobs",
                 ("Paused with the team: nothing is typed until the pause ends. " if paused else "")
                 + f"{len(today['rows'])} action{'' if len(today['rows']) == 1 else 's'} today, every one proved or waiting for its proof; {cut}.",
                 rule, source, autopilot_table(today))
