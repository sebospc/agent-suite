from abc import ABC, abstractmethod


class TokenTools(ABC):
    """What the token tools measure about themselves (the owner, ask 8ccee2): rtk's saved tokens per repo, context-mode's
    bytes kept out of context per session. caveman and ponytail measure nothing of their own."""

    @abstractmethod
    def read(self, day: str) -> dict:
        """{rtk: {repo: tokens saved on day (YYYY-MM-DD)}, ctx: {session_id: {avoided, returned}} in bytes};
        a tool that cannot be read is {error} in place of its map. Never raises."""
