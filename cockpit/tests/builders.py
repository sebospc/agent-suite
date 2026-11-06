import json
import os

from cockpit.board.bd_board import parse_beads
from cockpit.board.bead import Bead
from cockpit.compaction.price_table import PriceTable
from cockpit.project_config.project_config import load_config
from cockpit.team import Team
from cockpit.thresholds import Thresholds

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "fixtures")
HOUR = 3600.0
NOW = 1_792_123_540.0  # 2026-10-15 23:05:40 -05:00, the fixtures' board snapshot


def bead(id, status="open", parent=None, assignee="", labels=(), priority=1, issue_type="task", related=(),
         updated=NOW - HOUR, title=None, activity=()):
    return Bead(id=id, title=title or f"title of {id}", status=status, priority=priority, issue_type=issue_type,
                assignee=assignee, labels=list(labels), parent=parent, related=list(related), updated_at=updated,
                started_at=None, activity=list(activity))


def milestone(id="pg-m4", number=4, status="open"):
    return bead(id, status=status, issue_type="milestone", title=f"M{number}: test milestone", assignee="agent-brain")


def team():
    raw = load_config(ROOT)["team"]
    return Team(raw["roles"], raw["coordinating"], raw["known_holders"])


def thresholds(**overrides):
    with open(os.path.join(ROOT, "config", "thresholds.json")) as handle:
        raw = json.load(handle)
    for key, value in overrides.items():
        raw[key] = dict(raw[key], value=value)
    return Thresholds(raw)


def prices():
    with open(os.path.join(ROOT, "config", "prices.json")) as handle:
        return PriceTable(json.load(handle))


def fixture_beads():
    with open(os.path.join(FIXTURES, "beads.sample.jsonl")) as handle:
        return parse_beads(handle.read())


def fixture_json(name):
    with open(os.path.join(FIXTURES, name)) as handle:
        return json.load(handle)
