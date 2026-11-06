from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class LiveSession:
    name: str          # <prefix><role> when launched with --name
    session_id: str
    pid: int
    pane: str
    account: str       # cswap account number, or "default"
    state: str         # busy | idle | waits (asks in its window) | unknown
    flags: Tuple[str, ...] = ()  # its command line's flags with their values, never the prompt
    flags_known: bool = False    # False: only the --settings and --plugin-dir ps showed
    started_at: float = 0.0      # its process start (the live record's startedAt); 0 when not known
    status_model: str = ""       # the model its pane's status bar shows, e.g. Sonnet 5.5; a /model shows here at once
    background: str = ""         # the background tasks its status bar shows ("1 shell"); "" when none
