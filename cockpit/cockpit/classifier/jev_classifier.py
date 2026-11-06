import http.client
import json
import urllib.error
import urllib.request
from typing import Callable, Dict

from cockpit.classifier.task_classifier import TaskClassifier
from cockpit.source_unavailable import SourceUnavailable

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"

def yes_no(question: str, yes: str, no: str) -> dict:
    return {"type": "choice", "instructions": question, "criteria": {"yes": yes, "no": no}}


# Design chat J1: four raw judgments, kept reusable; the fixed table in cockpit/classifier/suggestion_table.py turns
# them into model, effort, window and fresh-vs-carry, so a change of policy reruns no inference.
QUESTIONS = {
    "mechanical": yes_no("Is `task` mechanical work an AI coding agent can do from its description alone?",
                         "Fully specified: a rename, a copy or config change, a status update, a lookup, a small described edit.",
                         "It needs judgment, design or investigation."),
    "deep_reasoning": yes_no("Does `task` need deep reasoning from an AI coding agent?",
                             "Architecture or design choices, a subtle bug of unknown cause, security, many interacting constraints.",
                             "A known plan carried out carefully is enough."),
    "needs_history": yes_no("Does `task` depend on what the agent already worked out earlier in the same work?",
                            "It continues earlier work: findings, a half-done change, a review round on the agent's own patch.",
                            "It can start from the files and the description alone."),
    "wide_reading": yes_no("Does `task` need the agent to read widely across the codebase?",
                           "Many files or folders, a cross-cutting change, or a survey before acting.",
                           "A few known files."),
}


class JevClassifier(TaskClassifier):
    """TypeSafe's Jev over HTTP: yes or no Choice questions on one state, in one request. The key
    goes only into the Authorization header, never into an error or a log line."""

    def __init__(self, api_key: str, timeout_s: float, urlopen: Callable = urllib.request.urlopen,
                 on_usage: Callable[[str, int, dict], None] = lambda key, questions, usage: None):
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.urlopen = urlopen
        self.on_usage = on_usage  # Jev's own tokens per request (design pg-45v5)

    def classify(self, bead_id: str, title: str, description: str) -> dict:
        return {"probabilities": self.judge(bead_id, "", QUESTIONS, {"task": {"title": title, "description": description}})}

    def judge(self, key: str, version: str, questions: dict, state: dict) -> Dict[str, float]:
        body = json.dumps({"model": MODEL, "questions": questions, "state": state}).encode()
        request = urllib.request.Request(ENDPOINT, data=body, method="POST", headers={
            "Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        try:
            with self.urlopen(request, timeout=self.timeout_s) as response:
                answered = json.loads(response.read())
            self.on_usage(key, len(questions), answered.get("usage") or {})
            answers = answered["answers"]
            return {name: probability_of_yes(answers[name]) for name in questions}
        except urllib.error.HTTPError as error:
            raise SourceUnavailable(f"Jev answered {error.code} {error.reason} for {key}")
        except (urllib.error.URLError, OSError, http.client.HTTPException) as error:
            raise SourceUnavailable(f"Jev could not be reached for {key}: {getattr(error, 'reason', error)}")
        except (ValueError, KeyError, TypeError) as error:
            raise SourceUnavailable(f"Jev's answer for {key} had an unexpected shape: {type(error).__name__} {error}")


def probability_of_yes(answer: dict) -> float:
    probabilities = answer.get("probabilities") or {}
    if "yes" in probabilities:
        return float(probabilities["yes"])
    return float(answer["confidence"]) if answer["choice"] == "yes" else 1 - float(answer["confidence"])
