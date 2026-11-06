from statistics import median
from typing import Dict, List

from cockpit.snapshot.health_tables import table
from cockpit.snapshot.lights import light
from cockpit.transcripts.session_stats import SessionStats

TOOLS = ("rtk", "caveman", "ponytail", "context-mode", "i-have-adhd")
# caveman and ponytail are plugins: on where the session's settings layers enable them, whether or not their hook ran in
# 24 h (a session older than a day ran no SessionStart since). i-have-adhd is brain's own SessionStart hook (owner 2ae134).
PLUGINS = ("caveman", "ponytail")
BYTES_PER_TOKEN = 4  # heuristic: context-mode counts bytes kept out, not tokens
RULE = ("UNKNOWN when its own numbers cannot be read; WATCH when its hook crashed or timed out in 24 h, or the sessions "
        "with it on spend more tokens per finished task than those without it")


def k(tokens: float) -> str:
    sign, tokens = ("-", -tokens) if tokens < 0 else ("", tokens)
    return sign + (f"{tokens / 1e6:.1f}M" if tokens >= 1e6 else f"{round(tokens / 1000)}k")


def per_task(group: List[SessionStats]):
    tasks = sum(s.tasks_closed for s in group)
    return sum(s.tokens_24h for s in group) / tasks if tasks else None


def group_line(label: str, names: List[str], group: List[SessionStats], outputs: bool) -> str:
    if not group:
        return f"{label}: none"
    cost, tasks = per_task(group), sum(s.tasks_closed for s in group)
    parts = [f"~{k(cost)} per finished task ({tasks} closed)" if cost else "no task closed",
             f"{sum(s.re_reads for s in group)} re-reads"]
    turns = [o for s in group for o in s.outputs]
    if outputs and turns:
        parts.append(f"median output {round(median(turns))} per turn")
    return f"{label} ({', '.join(names)}): {', '.join(parts)}"


def tool_table(tool: str, on: Dict[str, SessionStats], named: Dict[str, SessionStats], own_count, own_label: str,
               kept: Dict[str, float], costs: Dict[str, float], events: int) -> dict:
    """One row per session, with it on or off: whether the tool pays shows as the per-task column of each group."""
    columns = [("session", "Session", "text"), ("on", "On", "flag"), ("tasks", "Tasks", "count"),
               ("per_task", "Per task", "tokens"), ("re_reads", "Re-reads", "count"), ("failures", "Hook failures", "count")]
    if tool == "context-mode":
        columns += [("kept", "Kept out ~", "tokens"), ("cost", "Cost ~", "tokens"), ("net", "Net ~", "tokens")]
    rows = [{"id": n, "session": n, "on": n in on, "tasks": s.tasks_closed,
             "per_task": round(s.tokens_24h / s.tasks_closed) if s.tasks_closed else None, "re_reads": s.re_reads,
             "failures": sum(1 for _, name, _ in s.tool_failures if name == tool), "kept": kept.get(n),
             "cost": round(costs[s.session_id]) if s.session_id in costs else None,
             "net": round(kept.get(n, 0) - costs[s.session_id]) if s.session_id in costs else None}
            for n, s in named.items()]
    cost_on, cost_off = per_task(list(on.values())), per_task([s for n, s in named.items() if n not in on])
    totals = [("own", own_label, "tokens", own_count)] if own_label else []
    if tool == "context-mode":
        totals += [("cost", "Cost ~, counted once", "tokens", round(sum(costs.values()))),
                   ("net", "Net ~, estimate", "tokens", round(own_count - sum(costs.values()))),
                   ("events", "Redirect and snapshot events", "count", events)]
    totals += [("per_task_on", "Per task, on", "tokens", round(cost_on) if cost_on else None),
               ("per_task_off", "Per task, off", "tokens", round(cost_off) if cost_off else None),
               ("sessions_on", "Sessions on", "count", len(on))]
    return table(f"{tool} per session, 24 h; it pays when per task on is under per task off", columns, rows, totals)


def tools_on(stats: SessionStats, row: dict) -> set:
    hooks = set(stats.token_tools) - set(PLUGINS)
    return hooks | (set(PLUGINS) & set(row["plugins"])) | ({"i-have-adhd"} if "adhd" in row["start_modes"] else set())


def token_tool_lights(measured: dict, named: Dict[str, SessionStats], rows: List[dict]) -> List[dict]:
    """One Team health row per token tool (the owner, ask 8ccee2: "(the owner\'s words)"): which
    sessions run it, what it saved by its own count, and whether it pays against the sessions that run without it."""
    measured = measured or {}
    by_name = {r["name"]: r for r in rows}
    running = {n: tools_on(s, by_name[n]) for n, s in named.items()}
    lights = []
    for tool in TOOLS:
        on = {n: s for n, s in named.items() if tool in running[n]}
        off = {n: s for n, s in named.items() if n not in on}
        failures = [f"{n}: {said}" for n, s in named.items() for _, name, said in s.tool_failures if name == tool]
        own = measured.get("rtk" if tool == "rtk" else "ctx") if tool in ("rtk", "context-mode") else {}
        own_count, own_label, kept, kept_all, costs, events, net = None, "", {}, {}, {}, 0, 0.0
        if tool == "rtk" and "error" not in (own or {}):
            own_count, own_label = sum(own.values()), "Saved today, its own count"
            value, source = f"{k(sum(own.values()))} saved today", "rtk gain per team repo and team scratchpad folder (rtk's own count), transcripts"
        elif tool == "context-mode" and "error" not in (own or {}):
            kept = {n: own.get(s.session_id, {}).get("avoided", 0) / BYTES_PER_TOKEN for n, s in on.items()}
            kept_all = {sid: v["avoided"] / BYTES_PER_TOKEN for sid, v in own.items()}
            costs = {sid: v.get("chars", 0) / BYTES_PER_TOKEN for sid, v in own.items()}
            events = sum(v.get("events", 0) for v in own.values())
            own_count, own_label = round(sum(kept_all.values())), "Kept out ~, its own count"
            net = sum(kept_all.values()) - sum(costs.values())
            value = f"~{k(net)} net (estimate)"
            source = ("context-mode session databases (raw size minus what it handed over, an upper bound), hook output and tool lines "
                      "in the transcripts; bytes / 4, heuristic; each counted once")
        else:
            value = f"on in {len(on)} of {len(named)}"
            source = ("each session's settings layers (enabledPlugins in user, project, local and --settings; --plugin-dir), transcripts"
                      if tool in PLUGINS else "transcripts (its SessionStart line at the last start)")
        if own and "error" in own:
            lights.append(light(tool, tool, "unknown", "unknown", "", own["error"], RULE, source))
            continue
        cost_on, cost_off = per_task(list(on.values())), per_task(list(off.values()))
        dearer = (cost_on is not None and cost_off is not None and cost_on > cost_off) or net < 0
        lines = [group_line("On", list(on), list(on.values()), tool in ("caveman", "ponytail")),
                 group_line("Off", list(off), list(off.values()), tool in ("caveman", "ponytail"))]
        if kept_all or costs:
            lines.insert(0, f"Pilot, all its sessions: kept out ~{k(sum(kept_all.values()))} (upper bound), cost ~{k(sum(costs.values()))}, "
                            f"net ~{k(net)} (estimate), {events} events, counted once each")
        if failures:
            lines.append("Its hook failed: " + "; ".join(failures))
        if dearer:
            lines.append("It does not pay yet: its net is negative, or the sessions with it spend more per finished task")
        lights.append(light(tool, tool, value, "watch" if failures or dearer else "ok", "", ". ".join(lines) + ".", RULE, source,
                            tool_table(tool, on, named, own_count, own_label, kept, costs, events)))
    return lights
