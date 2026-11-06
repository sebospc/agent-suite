from typing import List

from cockpit.live_sessions.live_session import LiveSession
from cockpit.live_sessions.live_sessions import LiveSessions


class FakeLiveSessions(LiveSessions):
    def __init__(self, sessions: List[LiveSession]):
        self.sessions = sessions

    def list(self) -> List[LiveSession]:
        return list(self.sessions)
