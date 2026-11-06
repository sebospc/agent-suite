from abc import ABC, abstractmethod


class Disk(ABC):
    """Free space on the Mac's data volume, and the size of the folders the team fills (transcripts, board, cockpit)."""

    @abstractmethod
    def read(self) -> dict:
        """{volume, free, total, folders: {name: bytes or None}}; raises SourceUnavailable."""
