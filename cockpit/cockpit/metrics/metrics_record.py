from typing import Dict, List, Optional

from cockpit.action_log.action_log import ActionLog

TOTALS = "_totals"  # the row id of an area's own figures


def cells_of(health: List[dict]) -> Dict[str, Dict[str, dict]]:
    """Every Team health table as {area: {row id: {column: value}}}, its totals under TOTALS; a light's extra tables
    (Tokens: per landed bead, HOLD rate) under their own ids."""
    areas = {}
    grids = [(area["id"], area.get("table")) for area in health] + [(more["id"], more) for area in health for more in area.get("more", [])]
    for area_id, grid in grids:
        if not grid:
            continue
        rows = {str(r["id"]): {k: v for k, v in r.items() if k != "id"} for r in grid["rows"]}
        if grid["totals"]:
            rows[TOTALS] = {t["key"]: t["value"] for t in grid["totals"]}
        areas[area_id] = rows
    return areas


class MetricsRecord:
    """metrics.jsonl (the owner, ask 834b86: "(the owner\'s words)"): one
    line per read, holding only the rows that changed since the line before, a gone row as null. The first line after a
    start holds every row, so a history never depends on a line written by another run."""

    def __init__(self, log: ActionLog):
        self.log = log
        self.last: Dict[str, Dict[str, dict]] = {}

    def record(self, health: List[dict], now: float) -> None:
        """Raises SourceUnavailable when the line could not be written; the next read then writes it whole again."""
        cells = cells_of(health)
        changed = {}
        for area in set(cells) | set(self.last):
            now_rows, before = cells.get(area, {}), self.last.get(area, {})
            diff = {row: values for row, values in now_rows.items() if before.get(row) != values}
            diff.update({row: None for row in before if row not in now_rows})
            if diff:
                changed[area] = diff
        self.last = {}
        self.log.append({"t": now, "areas": changed})
        self.last = cells

    def history(self, area: str, row: str, key: str, start: float) -> List[list]:
        """[time, value] each time one measure changed since start; the value it held at start comes first, at start."""
        # ponytail: reads the whole file per call; rotate metrics.jsonl by month when a history takes over a second.
        points, before = [], None
        for line in self.log.since(0):
            rows = (line.get("areas") or {}).get(area)
            if rows is None or row not in rows:
                continue
            value: Optional[object] = (rows[row] or {}).get(key)
            if line["t"] < start:
                before = [start, value]
            elif not points or value != points[-1][1]:
                points.append([line["t"], value])
        return ([before] if before and (not points or points[0][0] > start) else []) + points
