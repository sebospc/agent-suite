import re

FENCE = re.compile(r"```.*?(?:```|$)", re.S)
QUOTED = re.compile(r'"[^"\n]*"|“[^”\n]*”')
EXCERPT_CHARS = 140


def blank(match) -> str:
    return re.sub(r"[^\n]", " ", match.group())


def own_words(text: str) -> str:
    """The text with what a reply quotes blanked out (fenced code, `>` lines, double-quoted spans), same length so a
    match's position still points into the original. A quoted 'saved' or id is somebody else's claim, not the session's."""
    text = QUOTED.sub(blank, FENCE.sub(blank, text))
    return "\n".join(" " * len(line) if line.lstrip().startswith(">") else line for line in text.split("\n"))


def excerpt(text: str, position: int) -> str:
    """The line of the reply a match sits in, cut to a window around it when long."""
    start = text.rfind("\n", 0, position) + 1
    end = text.find("\n", position)
    line = text[start:end if end >= 0 else len(text)]
    at = position - start
    if len(line) > EXCERPT_CHARS:
        lo = max(0, min(at - EXCERPT_CHARS // 2, len(line) - EXCERPT_CHARS))
        line = ("…" if lo else "") + line[lo:lo + EXCERPT_CHARS] + ("…" if lo + EXCERPT_CHARS < len(line) else "")
    return line.strip()
