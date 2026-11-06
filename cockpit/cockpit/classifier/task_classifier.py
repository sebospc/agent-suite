from abc import ABC, abstractmethod
from typing import Dict


class TaskClassifier(ABC):
    """Jev's judgments (design pg-o1sq Q12): raw yes probabilities that plain code turns into settings. The owner chose
    Jev (the owner's choice), which is their yes to sending bead text, and with the design's Q4, a session's last turns."""

    @abstractmethod
    def classify(self, bead_id: str, title: str, description: str) -> dict:
        """{"probabilities": {"mechanical", "deep_reasoning", "needs_history", "wide_reading": 0..1}} for one bead's text
        (its task kind for the sweet spot); raises SourceUnavailable."""

    @abstractmethod
    def judge(self, key: str, version: str, questions: dict, state: dict) -> Dict[str, float]:
        """The yes probability of each question about state. key names what is judged (a session, a bead), version
        what of it Jev must see again when it changes; raises SourceUnavailable."""
