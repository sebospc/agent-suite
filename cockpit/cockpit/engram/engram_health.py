from abc import ABC, abstractmethod


class EngramHealth(ABC):
    """The team's memory store: its doctor, what sessions saved, and which session transcripts load its tools."""

    @abstractmethod
    def read(self) -> dict:
        """{doctor: {status, issues}, memories: {total, saved_by_sessions, saved_today}, sessions: {session_id: {loaded, searches, saves}}}."""
