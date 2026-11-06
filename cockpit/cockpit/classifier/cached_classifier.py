import hashlib
import json
import os
from typing import Dict, List, Optional

from cockpit.classifier.task_classifier import TaskClassifier


class CachedClassifier(TaskClassifier):
    """Decorator: each thing is judged once per version, not on every 30 s read (each call costs).
    With a store path the answers survive a cockpit restart, which otherwise asks Jev again for every session."""

    def __init__(self, inner: TaskClassifier, store_path: Optional[str] = None):
        self.inner = inner
        self.store_path = os.path.expanduser(store_path) if store_path else None
        stored = self._load()
        self.answers: Dict[str, dict] = stored.get("answers", {})
        self.judged: Dict[str, List] = stored.get("judged", {})  # key -> [its last version, answer]

    def classify(self, bead_id: str, title: str, description: str) -> dict:
        # sha256, not hash(): str hashes change per process, so a stored key would never match again.
        key = bead_id + " " + hashlib.sha256(json.dumps([title, description]).encode()).hexdigest()
        if key not in self.answers:
            self.answers[key] = self.inner.classify(bead_id, title, description)
            self._save()
        return self.answers[key]

    def judge(self, key: str, version: str, questions: dict, state: dict) -> Dict[str, float]:
        # Only the last version per key is kept: an old version is never asked about again.
        last = self.judged.get(key)
        if last is None or last[0] != version:
            self.judged[key] = [version, self.inner.judge(key, version, questions, state)]
            self._save()
        return self.judged[key][1]

    def _load(self) -> dict:
        if not self.store_path:
            return {}
        try:
            with open(self.store_path, encoding="utf-8") as handle:
                stored = json.load(handle)
            return stored if isinstance(stored, dict) else {}
        except (OSError, ValueError):
            return {}  # a missing or torn file only costs the calls a restart cost before

    def _save(self) -> None:
        if not self.store_path:
            return
        os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
        partial = self.store_path + ".tmp"
        with open(partial, "w", encoding="utf-8") as handle:
            json.dump({"answers": self.answers, "judged": self.judged}, handle)
        os.replace(partial, self.store_path)
