import time
from typing import Optional

from cockpit.autopilot.wake_forecast import WakeForecast
from cockpit.classifier.task_classifier import TaskClassifier
from cockpit.classifier.verdict_state import digest
from cockpit.classifier.wake_questions import WAKE_QUESTIONS
from cockpit.team import session_name

HOUR = 3600


class JevWakeForecast(WakeForecast):
    """Adapter: Jev's two wake judgments. The cached classifier keeps the answer for the same version, so Jev is asked
    again only when the real last turn changes or another hour of the idle stretch has passed."""

    def __init__(self, classifier: TaskClassifier):
        self.classifier = classifier

    def forecast(self, row: dict, idle_since: float, now: float) -> Optional[dict]:
        idle_hours = int((now - idle_since) // HOUR)
        state = {"session": {"name": session_name(row['name']), "working_on": row.get("work_line") or row.get("bead") or "",
                             "holds_a_bead_in_progress": bool(row.get("holds")), "notes_saved": row.get("notes_saved")},
                 "idle": {"minutes_since_its_last_real_turn": round((now - idle_since) / 60), "local_hour": time.localtime(now).tm_hour},
                 "cache": {"context_tokens": row.get("context"), "sweet_spot_tokens": row.get("spot")}}
        p = self.classifier.judge(f"wake {row['name']}", digest([row["name"], idle_since, idle_hours]), WAKE_QUESTIONS, state)
        return {"within_hour": p["wakes_within_hour"], "never": p["never_wakes"]}
