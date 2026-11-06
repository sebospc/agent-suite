from typing import List

from cockpit.display_time import when
from cockpit.snapshot.health_tables import table
from cockpit.snapshot.lights import light

RULE = "WATCH when a fit fell outside its range: it changed nothing and waits in Your tasks as a proposal"
SOURCE = "config/thresholds.json ranges, ~/.cockpit/learned.jsonl, actions.jsonl"


def learned_light(status: dict, now: float) -> dict:
    """Team health (design pg-o1sq Q14): each learned number, its range, whether a fitter has its data yet, and every
    change it made by itself."""
    if status["error"]:
        return light("learned", "Learned numbers", "unknown", "unknown", "", status["error"], RULE, SOURCE)
    rows = [{"id": n["name"], "name": n["name"], "value": str(n["value"]),
             "range": f"{n['range']['min']:g} to {n['range']['max']:g}, at most {n['range']['max_weekly_change_pct']:g}% a week",
             "last": (f"{n['last']['from']:g} to {n['last']['to']:g} {when(n['last']['t'], now)} from {n['last']['n']} samples"
                      if n["last"] else "no change this week" if n["fitter"] else "no fitter yet")} for n in status["numbers"]]
    proposals = status["proposals"]
    why = [f"{len(rows)} number{' learns by itself within its' if len(rows) == 1 else 's learn by themselves within their'} range; "
           f"a fitter waits for its sample minimum ({status['min_samples']}; {status['min_labels']} labelled TASK starts for Jev's cut-off)"]
    labels = status.get("labels")
    if labels is not None:
        why.append(f"Jev's cut-off: {labels['measured']} measured and {labels['confounded']} confounded TASK starts in two weeks; "
                   f"a confounded one, whose model, effort, plugins or task changed before its outcome, is left out")
    why += [f"Proposal: {p['name']} {p['why']}" for p in proposals]
    columns = [("name", "Number", "text"), ("value", "Now", "text"), ("range", "Range", "text"), ("last", "Last change", "text")]
    return light("learned", "Learned numbers", f"{len(proposals)} proposal{'' if len(proposals) == 1 else 's'}" if proposals else f"{len(rows)} learned",
                 "watch" if proposals else "ok", "", ". ".join(why) + ".", RULE, SOURCE, table("Learned numbers and their ranges", columns, rows))


def proposal_needs(status: dict) -> List[dict]:
    """A fit outside its range is the owner's call (Q14): a Your tasks row, and nothing changes until they do."""
    return [{"id": f"refit-{p['name']}", "level": "caution", "action_label": "Owner's call", "action_kind": "none", "action_payload": "",
             "target": "", "source": "learned.jsonl proposal",
             "text": f"{p['name']} is {p['from']:g}; its fit says {p['fitted']:g}, outside its range. Change its range or value in "
                     f"config/thresholds.json, or leave it ({p['why']})."} for p in status["proposals"]]
