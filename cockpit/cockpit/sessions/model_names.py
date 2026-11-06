import re


def model_label(model: str) -> str:
    """claude-opus-5-5 -> Opus 5.5"""
    match = re.match(r"claude-([a-z]+)-(\d+)-(\d+)", model or "")
    return f"{match.group(1).capitalize()} {match.group(2)}.{match.group(3)}" if match else (model or "unknown")
