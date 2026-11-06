# PreToolUse hook: while the pause file exists, the team commits, pushes, claims, messages and runs
# nothing. On 2026-10-16 the team kept working under a pause because only a file said so. Each denial is logged.
import json
import os
import re
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import suite_config  # noqa: E402

PAUSE_FILE = suite_config.board_file("AGENT_PAUSE_FILE", "paused")
DENIAL_LOG = suite_config.board_file("AGENT_PAUSE_LOG", "pause_denials.jsonl")
# One shell command per segment, so "git log; echo push" is not read as a push.
SEGMENT = re.compile(r"[^;&|\n]+")
BASH_RULES = (
    ("commit or push", re.compile(r"\bgit\b.*\b(commit|commit-tree|push|update-ref)\b")),
    ("bead claim", re.compile(r"\bbd\s+claim\b|\bbd\b.*--claim\b|\bbd\b.*\bupdate\b.*(--status|-s)[= ]in_progress\b")),
    ("device run", re.compile(r"\bxcodebuild\b.*\btest|\bgradlew\b.*\bconnected|\badb\b|\bsimctl\s+(boot|install|launch)"
                              r"|\bemulator\s+-avd\b")),
    ("model run", re.compile(r"\bclaude\s+(-p|--print)\b|\bkiro-cli\b|\bcursor-agent\b"
                             r"|\bpython3?\b(?!.*\b(unittest|pytest)\b).*\bevals[./]")),
)
# The gate runs the device suites unless VERIFY_STEPS leaves ios and android out.
GATE = re.compile(r"\bverify_commit\.sh\b")
HOST_STEPS = re.compile(r"VERIFY_STEPS=\S*\b(ios|android)\b|VERIFY_STEPS=[\"'][^\"']*\b(ios|android)\b")


def bash_rule(command: str) -> str | None:
    if GATE.search(command) and ("VERIFY_STEPS=" not in command or HOST_STEPS.search(command)):
        return "device run"
    for segment in SEGMENT.findall(command):
        for rule, pattern in BASH_RULES:
            if pattern.search(segment):
                return rule
    return None


def denied_rule(hook: dict) -> str | None:
    if hook.get("tool_name") == "SendMessage":
        return "cross-session message"
    if hook.get("tool_name") == "Bash":
        return bash_rule(str((hook.get("tool_input") or {}).get("command", "")))
    return None


def log_denial(hook: dict, rule: str) -> None:
    entry = {"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "session": hook.get("session_id", ""),
             "cwd": hook.get("cwd", ""), "tool": hook.get("tool_name", ""), "rule": rule,
             "input": json.dumps(hook.get("tool_input") or {}, ensure_ascii=False)[:300]}
    try:
        with open(DENIAL_LOG, "a", encoding="utf-8") as log:
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass  # a log that can't be written must not let the call through


def main() -> int:
    if not os.path.exists(PAUSE_FILE):
        return 0
    try:
        hook = json.load(sys.stdin)
        rule = denied_rule(hook)
    except Exception:  # noqa: BLE001 - only exit 2 blocks; a crash must never be how this hook blocks
        return 0
    if not rule:
        return 0
    log_denial(hook, rule)
    print(f"The team is paused ({PAUSE_FILE} exists): {rule} denied. Wait until the owner removes the pause.",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
