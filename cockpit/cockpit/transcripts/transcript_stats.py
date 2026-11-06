import re
from typing import List, Optional

from cockpit.idle_cost.idle_gaps import idle_gaps
from cockpit.transcripts.cache_rewrites import rewrites
from cockpit.transcripts.recovery_span import RecoverySpan
from cockpit.transcripts.refill import refilled_after
from cockpit.transcripts.session_stats import Compaction, SessionStats
from cockpit.transcripts.transcript_file import TranscriptFile

RECENT_TURNS = 50
# Write is the new file; the others edit one.
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
RECOVERY_MAX_REQUESTS = 10
TASK_END = re.compile(r"\bbd\s+close\b")
FIRST_TURNS = 3  # a session cleared too early reads its old files again within its first turns (pg-o6lk)
START_SPREAD_S = 60  # one start runs all its SessionStart hooks within this many seconds


def most_common(values: List[str]) -> str:
    present = [v for v in values if v]
    return max(set(present), key=present.count) if present else ""


CHARS_PER_TOKEN = 3.5  # heuristic: the first message is known only as text, so its tokens are estimated from its length


def processed(row: dict) -> int:
    return row["context"] + row["out"]


def no_cache(row: dict) -> int:
    """Fresh input and output, without cache reads or writes (the owner, 56fba6: every token number defaults to it)."""
    return processed(row) - row["read"] - row["write"]


def start_load(rows: List[dict], prompts: List[dict]) -> Optional[int]:
    """What a session loads before any work (CLAUDE.md, system prompt, tools, memory): its first request's context minus
    the first message that started it, whose tokens are estimated from its length (the owner, 2026-10-16: "sin prompts")."""
    if not rows:
        return None
    first_t = rows[0]["t_first"] or 0
    before = [p for p in prompts if p["t"] <= first_t]
    message = before[-1].get("chars", 0) if before else 0
    return max(0, rows[0]["context"] - round(message / CHARS_PER_TOKEN))


def session_stats(main: TranscriptFile, extra: List[TranscriptFile], session_id: str, now: float,
                  step_tokens: int, idle_gap_s: float) -> SessionStats:
    rows = [r for r in main.requests() if not r["sidechain"]]
    w1h, w5m = sum(r["w1h"] for r in rows), sum(r["w5m"] for r in rows)
    ttl = 3600 if w1h >= w5m and w1h else 300
    for index, row in enumerate(rows):
        previous = rows[index - 1] if index else row
        row["growth"] = row["context"] - previous["context"]
        row["gap"] = (row["t_first"] or 0) - (previous["t_last"] or 0) if index else 0.0
    compactions, skip = [], set()
    boundaries = sorted(main.boundaries, key=lambda b: b["at"])
    for index, boundary in enumerate(boundaries):
        next_at = boundaries[index + 1]["at"] if index + 1 < len(boundaries) else None
        after = [r for r in rows if (r["t_first"] or 0) > boundary["at"]]
        first = after[0] if after else None
        span, counted = recovery(after, boundary["at"], next_at, idle_gap_s)
        skip.update(id(r) for r in counted + ([first] if first else []))
        compactions.append(Compaction(at=boundary["at"], trigger=boundary["trigger"], pre=boundary["pre"],
                                      post=boundary["post"], first_context=first and first["context"],
                                      first_cached=first and first["read"], recovery=span,
                                      refilled_s=refilled_after(after, boundary["at"], boundary["pre"])))
    growth = [r["growth"] for r in rows[1:] if id(r) not in skip and r["gap"] <= ttl and r["growth"] >= 0]
    day_ago = now - 86400
    tokens = sum(no_cache(r) for f in [main] + extra for r in f.requests() if (r["t_first"] or 0) >= day_ago)
    return SessionStats(
        session_id=session_id, title=main.titles[-1] if main.titles else "",
        model=rows[-1]["model"] if rows else "", effort=rows[-1]["effort"] if rows else "",
        ttl_seconds=ttl, context_now=context_now(rows, main.boundaries), floor=rows[0]["context"] if rows else None,
        last_turn_at=rows[-1]["t_last"] if rows else None, tokens_24h=tokens,
        growth=growth[-RECENT_TURNS:], outputs=[r["out"] for r in rows[-RECENT_TURNS:]],
        gaps=[r["gap"] for r in rows[1:]], compactions=compactions,
        haiku_over_step=sum(1 for r in rows if "haiku" in (r["model"] or "") and r["context"] > step_tokens),
        mentioned_beads={bead for at, bead in main.mentions if at >= day_ago},
        mentioned_asks={i for at, kind, i in main.ids if kind == "ask" and at >= day_ago},
        mentioned_commits={i for at, kind, i in main.ids if kind == "commit" and at >= day_ago},
        evidence=[e for e in main.evidence if e[0] >= day_ago],
        saved_without_id=sum(1 for at in main.saved_without_id if at >= day_ago),
        started_at=rows[0]["t_first"] if rows else None, turns=len(main.prompts),
        start_load=start_load(rows, main.prompts), cwd=main.cwd, turn_started_at=turn_started_at(main.prompts),
        saved_places=[place for at, place in main.saved_places if at >= day_ago],
        token_tools={tool for tool, at in main.tool_runs.items() if at >= day_ago},
        tool_failures=[f for f in main.tool_failures if f[0] >= day_ago],
        hook_outputs=tuple((command, at, chars) for command, (at, chars) in main.hook_outputs.items()),
        tasks_closed=sum(1 for r in rows if (r["t_first"] or 0) >= day_ago
                         for tool, target in r["tools"] if tool == "Bash" and target and TASK_END.search(target)),
        re_reads=re_reads(rows, main.boundaries, day_ago), last_turns=tuple(main.last_turns),
        cache_read_24h=sum(r["read"] for r in rows if (r["t_first"] or 0) >= day_ago),
        cache_write_24h=sum(r["write"] for r in rows if (r["t_first"] or 0) >= day_ago),
        expired_writes_24h=expired_writes(rows, ttl, day_ago, now),
        rewrites_24h=rewrites(rows, main.boundaries, ttl, day_ago),
        last_read=rows[-1]["read"] if rows else 0, last_write=rows[-1]["write"] if rows else 0,
        last_context=rows[-1]["context"] if rows else 0,
        idle_gaps_24h=idle_gaps(rows, main.boundaries, ttl, day_ago),
        turn_gaps=turn_gaps(rows, main.prompts, day_ago),
        reads_since_start=reads_after_start(rows, main.prompts, main.last_start),
        task_files=task_files(rows),
        first_reads=first_reads(rows, main.prompts),
        start_modes=start_modes(main.start_modes), start_modes_at=max((at for at, _ in main.start_modes), default=None),
        skills=frozenset(target for r in rows for tool, target in r["tools"] if tool == "Skill" and target),
    )


def turn_gaps(rows: List[dict], prompts: List[dict], day_ago: float) -> tuple:
    """The gaps inside a turn: the agent working between its own requests. A longer gap than nearly all of them is a
    new prompt or a cold cache, which is what recovery_idle_gap_minutes separates (docs/COMPACTION.md, R)."""
    asked = sorted(p["t"] for p in prompts if p.get("t"))
    found, cursor = [], 0
    for previous, row in zip(rows, rows[1:]):
        start, end = previous["t_last"] or 0, row["t_first"] or 0
        if start < day_ago or end <= start:
            continue
        while cursor < len(asked) and asked[cursor] <= start:
            cursor += 1
        if cursor < len(asked) and asked[cursor] <= end:
            continue  # a prompt opened this request
        found.append(end - start)
    return tuple(found)


def expired_writes(rows: List[dict], ttl: float, day_ago: float, now: float) -> int:
    """Cache writes nothing read: the next request came after the cache's life, or none came and the life ran out
    (heuristic: a 5-minute write in a 1 h session is counted at the session's life)."""
    expired = 0
    for index, row in enumerate(rows):
        if (row["t_first"] or 0) < day_ago or not row["write"]:
            continue
        next_at = rows[index + 1]["t_first"] if index + 1 < len(rows) else None
        if (next_at if next_at is not None else now) - (row["t_last"] or 0) > ttl:
            expired += row["write"]
    return expired


def start_modes(seen: List[tuple]) -> frozenset:
    """The modes of its last start: one start runs its SessionStart hooks within seconds of each other."""
    last = max((at for at, _ in seen), default=0.0)
    return frozenset(mode for at, mode in seen if at >= last - START_SPREAD_S)


def task_files(rows: List[dict]) -> frozenset:
    """The files its last finished task read or changed: between the bd close before its last one and its last one."""
    closes = [i for i, r in enumerate(rows) for tool, target in r["tools"] if tool == "Bash" and target and TASK_END.search(target)]
    if not closes:
        return frozenset()
    start = next((i + 1 for i in reversed(closes) if i < closes[-1]), 0)
    return frozenset(target for r in rows[start:closes[-1] + 1] for tool, target in r["tools"]
                     if (tool == "Read" or tool in EDIT_TOOLS) and target and target.startswith("/"))


def first_reads(rows: List[dict], prompts: List[dict]) -> frozenset:
    end = prompts[FIRST_TURNS]["t"] if len(prompts) > FIRST_TURNS else float("inf")
    return frozenset(target for r in rows if (r["t_first"] or 0) < end for tool, target in r["tools"] if tool == "Read" and target)


def reads_after_start(rows: List[dict], prompts: List[dict], start: float) -> Optional[frozenset]:
    """The files its first turns after its last SessionStart read, by the Read tool or in a Bash command (sessions
    cat and grep their state file); None when no start was seen or no request came after it yet."""
    after = [r for r in rows if (r["t_first"] or 0) >= start]
    if not start or not after:
        return None
    asked = [p for p in prompts if (p.get("t") or 0) >= start]
    end = asked[FIRST_TURNS]["t"] if len(asked) > FIRST_TURNS else float("inf")
    return frozenset(target for r in after if (r["t_first"] or 0) < end for tool, target in r["tools"] if tool in ("Read", "Bash") and target)


def re_reads(rows: List[dict], boundaries: List[dict], day_ago: float) -> int:
    """A file read again while the first read is still in context costs its tokens twice; a compaction drops it."""
    cuts = sorted(b["at"] for b in boundaries)
    seen, count, cut = set(), 0, 0
    for row in rows:
        while cut < len(cuts) and cuts[cut] < (row["t_first"] or 0):
            seen, cut = set(), cut + 1
        for tool, target in row["tools"]:
            if tool != "Read" or not target:
                continue
            count += target in seen and (row["t_first"] or 0) >= day_ago
            seen.add(target)
    return count


def turn_started_at(prompts: List[dict]) -> Optional[float]:
    """When the last turn began. prompts holds no tool result already; a slash command (/effort, /model) starts no turn.
    shortcut: a skill's slash command does start one and is skipped here, so the start is early; upgrade if it matters."""
    return next((p["t"] for p in reversed(prompts) if p["origin"] != "command"), None)


def context_now(rows: List[dict], boundaries: List[dict]) -> Optional[int]:
    """The newest main-thread request's context, or the size a later compaction left. A compaction that did not record
    its size leaves it unknown until the next turn, never the size before it, nor 0 (brain's report: "157k to 0")."""
    last = rows[-1] if rows else None
    latest = max(boundaries, key=lambda b: b["at"]) if boundaries else None
    if latest and (last is None or latest["at"] > (last["t_first"] or 0)):
        return latest.get("post")
    return last["context"] if last else None


def recovery(after: List[dict], start: float, next_at: Optional[float], idle_gap_s: float):
    """The requests after a compaction until the session works again (docs/COMPACTION.md, R). Stops at the first edit
    or new file (the work itself, not counted), 10 requests, the task end (bd close), the next compaction or an idle gap:
    a request after one is a new prompt, so the reads that follow are the next task's, not recovery (panel cc0de8).
    A span the transcript has not finished is None: it would change on the next read."""
    counted, ended_by, previous = [], "", start
    for row in after:
        # The first gap counts from the compaction: the idle time before an autopilot compaction is not recovery's.
        gap, previous = (row["t_first"] or 0) - previous, row["t_last"] or previous
        if next_at is not None and (row["t_first"] or 0) > next_at:
            ended_by = "next compaction"
            break
        tools = row["tools"]
        if any(tool in EDIT_TOOLS for tool, _ in tools):
            ended_by = "edit"
            break
        if gap > idle_gap_s:
            ended_by = "idle gap"
            break
        counted.append(row)
        if any(tool == "Bash" and target and TASK_END.search(target) for tool, target in tools):
            ended_by = "task end"
            break
        if len(counted) == RECOVERY_MAX_REQUESTS:
            ended_by = f"{RECOVERY_MAX_REQUESTS} requests"
            break
    if not ended_by and next_at is not None:
        ended_by = "next compaction"
    if not ended_by:
        return None, counted
    span = RecoverySpan(fresh=sum(r["fresh"] for r in counted), write=sum(r["write"] for r in counted),
                        read=sum(r["read"] for r in counted), out=sum(r["out"] for r in counted),
                        requests=len(counted), ended_by=ended_by)
    return span, counted
