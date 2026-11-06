import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from cockpit.board.bead import Bead
from cockpit.milestone.tree import BeadTree
from cockpit.team import session_name

TEXT_CHARS = 600   # of a bead's description: enough for its scope line, not its whole log
OPEN_BEADS = 8
TASK_FILES = 15


@dataclass(frozen=True)
class World:
    """What Jev sees beside each session (design pg-o1sq Q4 A-F): its role, the milestone, its account's quota and
    its last turns. The owner's "wrong" clicks (Q4 G) join with step 5, which records them."""
    roles: Dict[str, str] = field(default_factory=dict)          # session -> its role line in team.json
    coordinating: frozenset = frozenset()
    milestone: dict = field(default_factory=dict)
    quota: Dict[str, dict] = field(default_factory=dict)         # account -> used share of its 5 h and 7 d windows
    turns: Dict[str, tuple] = field(default_factory=dict)        # session -> (time, who, text) of its last turns
    wrongs: Dict[str, list] = field(default_factory=dict)        # Q4 G: session -> the owner's latest wrong clicks


def world_of(rows: List[dict], tree: Optional[BeadTree], board, plan: Dict[str, dict], coordinating, stats_by_id: dict,
             accounts: list, wrongs: Optional[Dict[str, list]] = None,
             quota_per_task: Optional[Dict[str, float]] = None) -> World:
    return World(roles={name: p.get("role", "") for name, p in plan.items()}, coordinating=frozenset(coordinating),
                 milestone=milestone_brief(tree, board.dod, board.goal) if tree and board else {},
                 quota={a.number: {"five_hour_used_pct": a.five_hour_pct, "seven_day_used_pct": a.seven_day_pct,
                                   "seven_day_points_per_finished_task": (quota_per_task or {}).get(a.number)} for a in accounts},
                 turns={r["name"]: stats_by_id[r["session_id"]].last_turns for r in rows if r["session_id"] in stats_by_id},
                 wrongs=wrongs or {})


def open_beads(tree: BeadTree, holder: str) -> List[Bead]:
    """Its work: the beads it holds first, then the open ones assigned to it, by priority; never a milestone, an epic
    or a parked bead."""
    mine = [b for b in tree.by_id.values() if b.assignee == holder and b.is_open and not b.is_parked
            and b.issue_type not in ("milestone", "epic")]
    return sorted(mine, key=lambda b: (b.status != "in_progress", b.priority, b.id))[:OPEN_BEADS]


def last_finished(tree: BeadTree, holder: str) -> Optional[Bead]:
    return max((b for b in tree.by_id.values() if b.status == "closed" and b.assignee == holder),
               key=lambda b: b.closed_at or 0, default=None)


def brief(bead: Bead) -> dict:
    return {"id": bead.id, "title": bead.title, "status": bead.status, "description": bead.description[:TEXT_CHARS]}


def milestone_brief(tree: BeadTree, dod: dict, goal: dict) -> dict:
    milestone = tree.current_milestone()
    if milestone is None:
        return {}
    done_ids = ((dod or {}).get("milestones") or {}).get(milestone.id, {}).get("dod") or []
    return {"title": milestone.title, "description": milestone.description[:TEXT_CHARS], "goal": (goal or {}).get("label", ""),
            "definition_of_done": [f"{i} {tree.by_id[i].title} ({tree.by_id[i].status})" for i in done_ids if i in tree.by_id]}


def last_task(row: dict, finished: Optional[Bead]) -> dict:
    task = {"id": finished.id, "title": finished.title} if finished else {}
    return dict(task, files=(row.get("task_files") or [])[:TASK_FILES])


def turns_of(world: World, name: str) -> List[dict]:
    return [{"who": who, "text": text} for _, who, text in world.turns.get(name, ())]


def session_state(row: dict, beads: List[Bead], finished: Optional[Bead], world: World, now: float) -> dict:
    idle = now - row["last_turn_at"] if row["state"] == "idle" and row.get("last_turn_at") else 0
    return {"session": {"name": session_name(row['name']), "role": world.roles.get(row["name"], ""),
                        "coordinates_the_team": row["name"] in world.coordinating,
                        "open_beads": [brief(b) for b in beads], "last_task": last_task(row, finished),
                        "last_turns": turns_of(world, row["name"]),
                        "reread_its_state_file_after_its_last_start": row.get("notes_reread")},
            "milestone": world.milestone,
            "cache": {"context_tokens": row.get("context"), "sweet_spot_tokens": row.get("spot"), "idle_minutes": round(idle / 60),
                      "cache_life_minutes": round(row["cache_ttl"] / 60) if row.get("cache_ttl") else None},
            "quota": world.quota.get(row.get("account") or "", {}),
            "owner_marked_wrong": world.wrongs.get(row["name"], [])}


def bead_state(row: dict, bead: Bead, finished: Optional[Bead], world: World) -> dict:
    return {"next_task": brief(bead),
            "session": {"name": session_name(row['name']), "role": world.roles.get(row["name"], ""),
                        "last_task": last_task(row, finished), "last_turns": turns_of(world, row["name"])},
            "milestone": world.milestone,
            "owner_marked_wrong": world.wrongs.get(row["name"], [])}


def session_version(row: dict, beads: List[Bead], world: World) -> str:
    """Jev is asked again when its role, its beads, the milestone or its wrong clicks change; its cache, quota and turns go along at
    that moment but do not trigger a call each (two calls per task start, design Risks)."""
    return digest([world.roles.get(row["name"], ""), [brief(b) for b in beads], world.milestone.get("title", ""),
                   world.wrongs.get(row["name"], [])])


def bead_version(bead: Bead, finished: Optional[Bead], wrongs: Optional[list] = None) -> str:
    return digest([brief(bead), finished.id if finished else "", wrongs])


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:16]
