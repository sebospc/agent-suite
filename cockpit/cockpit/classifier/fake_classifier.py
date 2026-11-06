from typing import Dict, List

from cockpit.classifier.task_classifier import TaskClassifier


class FakeClassifier(TaskClassifier):
    def __init__(self, answers: Dict[str, dict]):
        self.answers = answers
        self.asked: List[str] = []
        self.states: Dict[str, dict] = {}

    def classify(self, bead_id: str, title: str, description: str) -> dict:
        self.asked.append(bead_id)
        return self.answers[bead_id]

    def judge(self, key: str, version: str, questions: dict, state: dict) -> Dict[str, float]:
        self.asked.append(key)
        self.states[key] = state
        return {name: self.answers[key].get(name, 0.0) for name in questions}
