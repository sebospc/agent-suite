import json
from typing import Dict, List, Optional

# The words that name a token tool in a hook command, a plugin key or an MCP server.
TOOL_WORDS = {"rtk": "rtk", "context-mode": "context-mode", "caveman": "caveman", "ponytail": "ponytail"}


def config_lines(part: Optional[dict]) -> List[str]:
    """One line per hook (event, matcher, command) and per other watched key, so a diff names what changed, not where."""
    if part is None:
        return []
    lines = []
    for event, groups in (part.get("hooks") or {}).items():
        for group in groups or []:
            for hook in group.get("hooks") or []:
                lines.append(f"hook {event} {group.get('matcher') or '*'}: {hook.get('command') or hook.get('type')}")
    for key, value in part.items():
        if key == "hooks":
            continue
        entries = value.items() if isinstance(value, dict) else [("", value)]
        lines += [f"{key} {name}: {json.dumps(item, sort_keys=True)}".replace("  ", " ") for name, item in entries]
    return lines


def tools_in(line: str) -> List[str]:
    return [tool for tool, word in TOOL_WORDS.items() if word in line]


def config_drift(baseline: Dict[str, Optional[dict]], current: Dict[str, Optional[dict]]) -> List[dict]:
    """Per file, the lines that name a token tool and were added or removed since the baseline: a tool that rewrites
    hooks can also drop another tool's line, so removals count as much as additions."""
    changes = []
    for path in sorted(set(baseline) | set(current)):
        before, after = config_lines(baseline.get(path)), config_lines(current.get(path))
        added = [l for l in after if l not in before and tools_in(l)]
        removed = [l for l in before if l not in after and tools_in(l)]
        if added or removed:
            changes.append({"path": path, "added": added, "removed": removed,
                            "tools": sorted({t for l in added + removed for t in tools_in(l)})})
    return changes
