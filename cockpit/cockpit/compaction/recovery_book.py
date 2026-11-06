from typing import Dict, List, Optional, Tuple

from cockpit.board.bead import Bead
from cockpit.classifier.suggestion_table import from_fields
from cockpit.classifier.task_classifier import TaskClassifier
from cockpit.compaction.recovery_mix import RecoveryMix
from cockpit.compaction.task_kind import NO_BEAD, jev_category, kind_from_labels
from cockpit.transcripts.recovery_span import RecoverySpan

LAST_COMPACTIONS = 20
# Jev is paid per call, so a first read of weeks of compactions is spread over many reads.
JEV_PER_READ = 5
FLEET = "fleet"


def mean_mix(spans: List[RecoverySpan], kind: str, provisional: bool) -> RecoveryMix:
    n = len(spans)
    return RecoveryMix(fresh=sum(s.fresh for s in spans) / n, write=sum(s.write for s in spans) / n,
                       read=sum(s.read for s in spans) / n, out=sum(s.out for s in spans) / n,
                       compactions=n, kind=kind, provisional=provisional)


def recovery_by_kind(entries: List[Tuple[float, Optional[str], RecoverySpan]]) -> Tuple[Dict[str, List[RecoverySpan]], List[RecoverySpan]]:
    """Each kind's last 20 spans and the fleet's last 20, newest last. A compaction whose kind is not known yet counts
    for the fleet only."""
    ordered = sorted(entries, key=lambda e: e[0])
    by_kind: Dict[str, List[RecoverySpan]] = {}
    for _, kind, span in ordered:
        if kind:
            by_kind.setdefault(kind, []).append(span)
    return ({kind: spans[-LAST_COMPACTIONS:] for kind, spans in by_kind.items()},
            [span for _, _, span in ordered][-LAST_COMPACTIONS:])


def recovery_for(kind: Optional[str], by_kind: Dict[str, List[RecoverySpan]], fleet: List[RecoverySpan],
                 min_compactions: int) -> Optional[RecoveryMix]:
    own = by_kind.get(kind or "", [])
    if len(own) >= min_compactions:
        return mean_mix(own, kind, provisional=False)
    return mean_mix(fleet, FLEET, provisional=True) if fleet else None


class RecoveryBook:
    """The task kind of each bead: its labels, else Jev's category, kept so a bead is asked once."""

    def __init__(self):
        self.categories: Dict[str, str] = {}

    def kind_of(self, bead: Optional[Bead]) -> Optional[str]:
        if bead is None:
            return NO_BEAD
        return kind_from_labels(bead) or self.categories.get(bead.id)

    def source_of(self, bead: Optional[Bead]) -> str:
        if bead is None:
            return "it holds no bead"
        if kind_from_labels(bead):
            return f"labels of {bead.id}"
        return f"Jev's category for {bead.id}" if bead.id in self.categories else f"Jev has not classified {bead.id} yet"

    def learn(self, beads: List[Bead], classifier: TaskClassifier, yes: float) -> int:
        """Asks Jev for the beads that have no kind yet, in the order given, at most JEV_PER_READ. Raises
        SourceUnavailable from the classifier; what was learned before it stays."""
        asked = 0
        for bead in beads:
            if asked == JEV_PER_READ:
                break
            if self.kind_of(bead) is not None:
                continue
            known = from_fields(bead)  # a chore is mechanical by its own type, no call needed
            if known == {}:  # a milestone or an epic is no task for Jev
                self.categories[bead.id] = bead.issue_type
                continue
            probabilities = known or classifier.classify(bead.id, bead.title, bead.description)["probabilities"]
            asked += 0 if known else 1
            self.categories[bead.id] = jev_category(probabilities, yes)
        return asked
