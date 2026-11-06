import re

from cockpit.panes.input_line import is_rule

# Claude Code's status bar names its running background tasks ("1 shell", "2 local agents", "3 background tasks" when
# mixed; the labels are read from its 2.1.318 binary). No transcript line says when one ends.
PILL = re.compile(r"\b\d+ (?:shells?|monitors?|local agents?|background tasks?|cloud sessions?|MCP tasks?|teams?|"
                  r"background dynamic workflows?)\b")


def background_of(screen: str) -> str:
    """The background pill under the input box, "" when none shows. Only the lines under the box's last rule are read,
    so a reply that mentions "2 shells" is not taken for one; with no rule on the screen, every line is."""
    lines = screen.splitlines()
    rule = next((i for i in range(len(lines) - 1, -1, -1) if is_rule(lines[i])), -1)
    return ", ".join(m.group() for line in lines[rule + 1:] for m in PILL.finditer(line))
