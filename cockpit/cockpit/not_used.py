from cockpit.source_unavailable import SourceUnavailable


class NotUsed(SourceUnavailable):
    # A source this project does not keep (no board, no panel): its section is left out, never shown as broken.
    pass
