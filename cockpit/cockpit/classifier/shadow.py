from typing import Dict, List, Optional

from cockpit.autopilot.task_folders import named_folders
from cockpit.classifier.suggestion_table import bead_start, session_settings, with_labels
from cockpit.classifier.task_classifier import TaskClassifier
from cockpit.classifier.verdict_questions import BEAD_QUESTIONS, SESSION_QUESTIONS
from cockpit.classifier.verdict_state import (World, bead_state, bead_version, last_finished, open_beads, session_state,
                                              session_version)
from cockpit.milestone.tree import BeadTree
from cockpit.sessions.model_names import model_label
from cockpit.source_unavailable import SourceUnavailable
from cockpit.team import session_name


def suggestions(rows: List[dict], tree: Optional[BeadTree], classifier: TaskClassifier, yes: float = 0.6,
                world: World = World(), now: float = 0.0, arriving: Optional[Dict[str, str]] = None) -> Dict[str, dict]:
    """For each running session, Jev's two verdicts (design pg-o1sq Q1): the session verdict sets its model, effort
    and window from its role and all its work; the bead verdict, only between tasks, says whether its next bead
    starts fresh. The autopilot applies them (cockpit/autopilot/rules.py). arriving: per session, the bead of the TASK
    it gets next; that bead is the one judged, else its next open bead."""
    if tree is None:
        return {}
    found, failed = {}, None
    for row in rows:
        # Not read yet (the first read after a start): Jev would judge without its turns or cache, and that answer
        # would stand until its beads change (brain's J7 for the rules).
        if row["state"] == "off" or row.get("last_turn_at") is None:
            continue
        holder = session_name(row['name'])
        beads = open_beads(tree, holder)
        held = (row["bead"] or "").split(" ")[0]
        between = not row["holds"] or held not in tree.by_id
        # Between tasks: its next bead decides clear or compact (the owner, 2026-10-16: "se lo dejamos a jev").
        upcoming = tree.by_id.get((arriving or {}).get(row["name"], "")) \
            or (next((b for b in beads if b.status == "open"), None) if between else None)
        finished = last_finished(tree, holder)
        try:
            session_p = with_labels(beads, classifier.judge(f"session {row['name']}", session_version(row, beads, world),
                                                            SESSION_QUESTIONS,
                                                            session_state(row, beads, finished, world, now)))
            bead_p = classifier.judge(f"bead {row['name']} {upcoming.id}", bead_version(upcoming, finished, world.wrongs.get(row["name"])), BEAD_QUESTIONS,
                                      bead_state(row, upcoming, finished, world)) if upcoming else None
        except SourceUnavailable as error:  # one refused session must not hide every other session's suggestion
            failed = error
            continue
        settings = session_settings(session_p, yes)
        model = model_label(settings["model"])
        found[row["name"]] = dict(settings, model=model, model_id=settings["model"], by="Jev", next=bool(upcoming),
                                  bead=upcoming.id if upcoming else held if held in tree.by_id else "",
                                  agrees=model == row["model"] and settings["effort"] == row["effort"],
                                  # Kept with each decision the autopilot takes from them, so outcomes label them (Q14).
                                  scores=rounded(session_p), bead_scores=rounded(bead_p) if bead_p else {},
                                  **(next_start(upcoming, finished, bead_p, yes) if upcoming else {}))
    if failed and not found:
        raise failed
    return found


def rounded(p: dict) -> Dict[str, float]:
    return {name: round(value, 3) for name, value in p.items()}


def next_start(upcoming, finished, bead_p: dict, yes: float) -> dict:
    # The task-end rule clears only for a next bead in other folders than the one it finished (pg-o6lk).
    return dict(bead_start(bead_p, yes), next_folders=sorted(named_folders(f"{upcoming.title}\n{upcoming.description}")),
                done_bead=finished.id if finished else "",
                done_folders=sorted(named_folders(f"{finished.title}\n{finished.description}")) if finished else [])
