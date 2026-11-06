from typing import Dict, List, Optional, Tuple

from cockpit.board.bead import Bead
from cockpit.compaction.recovery_book import RecoveryBook, recovery_by_kind, recovery_for
from cockpit.compaction.task_kind import bead_at
from cockpit.transcripts.session_stats import SessionStats


def recovery_by_role(book: RecoveryBook, sessions: Dict[str, Tuple[str, Optional[SessionStats]]], beads: List[Bead],
                     min_compactions: int, now: float) -> Tuple[Dict[str, dict], List[Bead]]:
    """Each role's task kind now and the recovery cost it is charged with, from every live session's measured spans;
    and the beads Jev should classify next (the ones held now first, then those of the newest compactions)."""
    entries, waiting = [], []
    for assignee, stats in sessions.values():
        for compaction in (stats.compactions if stats else []):
            if compaction.recovery is None:
                continue
            bead = bead_at(beads, assignee, compaction.at)
            kind = book.kind_of(bead)
            entries.append((compaction.at, kind, compaction.recovery))
            if kind is None:
                waiting.append((compaction.at, bead))
    by_kind, fleet = recovery_by_kind(entries)
    found, now_waiting = {}, []
    for role, (assignee, _) in sessions.items():
        bead = bead_at(beads, assignee, now)
        kind = book.kind_of(bead)
        if kind is None:
            now_waiting.append(bead)
        found[role] = {"recovery": recovery_for(kind, by_kind, fleet, min_compactions), "kind": kind or "",
                       "source": book.source_of(bead)}
    learn = now_waiting + [bead for _, bead in sorted(waiting, key=lambda w: w[0], reverse=True)]
    return found, list({bead.id: bead for bead in learn}.values())
