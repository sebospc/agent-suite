import re
from typing import List, Optional

PROMPT = "❯"
RULE = "─"
# Claude Code draws its prompt suggestion dim (ESC[2m) in the empty box; nobody typed it (brain, pg-jzva).
DIM_SPAN = re.compile(r"\x1b\[2m.*?(?:\x1b\[(?:0|22)?m|$)", re.M)
ESCAPE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def input_text(screen: str) -> Optional[str]:
    """What sits typed and unsent in Claude Code's input box: the lines from its last ❯ line down to the rule under it.
    None when the screen shows no input box, so nothing is typed on a guess. The screen is read with --ansi so the
    dim suggestion can be told from typed text."""
    lines = ESCAPE.sub("", DIM_SPAN.sub("", screen)).splitlines()
    prompt = next((i for i in range(len(lines) - 1, -1, -1) if lines[i].lstrip().startswith(PROMPT)), None)
    if prompt is None or prompt == 0 or not is_rule(lines[prompt - 1]):
        return None
    box: List[str] = []
    for line in lines[prompt:]:
        if box and is_rule(line):
            return "\n".join(box).replace(PROMPT, "", 1).replace("\xa0", " ").strip()
        box.append(line)
    return None


def is_rule(line: str) -> bool:
    return line.strip().startswith(RULE * 3)
