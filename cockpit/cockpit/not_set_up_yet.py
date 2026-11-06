from cockpit.source_unavailable import SourceUnavailable


class NotSetUpYet(SourceUnavailable):
    """A source that waits on a team change that has not landed yet: expected, so it is shown quietly and apart from
    a source that broke (the owner, 2026-10-16, asked why the cockpit warned about them)."""
