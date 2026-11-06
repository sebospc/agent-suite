from cockpit.classifier.task_classifier import TaskClassifier
from cockpit.not_set_up_yet import NotSetUpYet

WHY = "Jev is not connected: TYPESAFE_API_KEY holds no key in the cockpit's environment"


class NotConnectedClassifier(TaskClassifier):
    """While TYPESAFE_API_KEY holds no key (and in the demo): an expected gap, shown quietly."""

    def classify(self, bead_id: str, title: str, description: str) -> dict:
        raise NotSetUpYet(WHY)

    def judge(self, key: str, version: str, questions: dict, state: dict) -> dict:
        raise NotSetUpYet(WHY)
