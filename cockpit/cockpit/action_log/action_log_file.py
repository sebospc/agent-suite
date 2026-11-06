import json
import os
import threading
from typing import List

from cockpit.action_log.action_log import ActionLog
from cockpit.source_unavailable import SourceUnavailable


class ActionLogFile(ActionLog):
    """A JSONL file in the cockpit's own folder; the cockpit is its only writer."""

    def __init__(self, path: str):
        self.path = os.path.expanduser(path)
        self.lock = threading.Lock()

    def append(self, record: dict) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with self.lock, open(self.path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record) + "\n")
        except OSError as error:
            raise SourceUnavailable(f"{self.path}: {error}")

    def since(self, start: float) -> List[dict]:
        if not os.path.exists(self.path):
            return []
        records = []
        with self.lock, open(self.path, encoding="utf-8") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if isinstance(record, dict) and (record.get("t") or 0) >= start:
                    records.append(record)
        return records
