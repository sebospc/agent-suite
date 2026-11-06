from typing import Callable, Dict, List

from cockpit.live_sessions.live_session import LiveSession


def live_by_role(live: List[LiveSession], role_of: Callable[[str], str]) -> Dict[str, LiveSession]:
    """One live session per role. When two map to the same role (an old process still alive, a relaunch), the one
    herdr sees in a pane wins: its state is herdr's, while a paneless one falls back to its record, which reads idle
    between tool calls (brain's report F13)."""
    chosen: Dict[str, LiveSession] = {}
    for session in live:
        role = role_of(session.name)
        if role not in chosen or (session.pane and not chosen[role].pane):
            chosen[role] = session
    return chosen
