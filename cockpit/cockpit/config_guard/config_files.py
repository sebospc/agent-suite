from abc import ABC, abstractmethod


class ConfigFiles(ABC):
    """The settings and .mcp.json files the token tools can change (the owner, ask 8ccee2: "por si daña la config de alguna
    agente"), read only, against a baseline the cockpit keeps in its own folder."""

    @abstractmethod
    def read(self) -> dict:
        """{current, baseline, since}: each a map of path -> the watched keys of that file (None when it is missing), secrets
        left out; the first read saves current as the baseline. Raises SourceUnavailable."""
