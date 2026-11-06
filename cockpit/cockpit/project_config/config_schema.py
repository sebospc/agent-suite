from typing import Dict, List

from cockpit.project_config.config_error import ConfigError

TEXT, NUMBER, TEXTS, NAMED_TEXTS = "a string", "a whole number", "a list of strings", "an object of strings"
CHECKS = {
    TEXT: lambda value: isinstance(value, str),
    NUMBER: lambda value: isinstance(value, int) and not isinstance(value, bool),
    TEXTS: lambda value: isinstance(value, list) and all(isinstance(item, str) for item in value),
    NAMED_TEXTS: lambda value: isinstance(value, dict) and all(isinstance(item, str) for item in value.values()),
}
JSON_KINDS = {str: "a string", int: "a number", float: "a number", bool: "true or false", list: "a list", dict: "an object",
              type(None): "null"}

PATHS = {
    **{key: TEXT for key in (
        "board_dir", "panel", "transcripts", "claude_bin", "engram_bin", "engram_db", "engram_project", "cswap_profiles", "default_sessions",
        "default_settings", "usage", "balancer_log", "repo", "landing_ref", "gate_logs", "team_json", "node", "grill_server",
        "grill_doc", "action_log", "learned_log", "metrics_log", "jev_record", "jev_calls", "jev_answers", "pause_file",
        "disk_volume", "saved_guard_log", "rtk_scratchpads", "context_mode_transcripts", "context_mode_sessions",
        "config_baseline", "prices_page", "milestone_dir", "decision_log")},
    **{key: TEXTS for key in (
        "bd_command", "ask_owner", "repos", "docs_not_describing_code", "herdr", "hook_settings", "rtk", "guarded_configs")},
    "disk_folders": NAMED_TEXTS,
    "hook_logs": NAMED_TEXTS,
}
TEAM = {"roles": TEXTS, "coordinating": TEXTS, "known_holders": TEXTS, "projects": NAMED_TEXTS, "session_prefix": TEXT,
        "legacy_prefixes": TEXTS, "lead": TEXT, "coordinator": TEXT}
SCHEMA = {"port": NUMBER, "paths": PATHS, "team": TEAM}
OPTIONAL = {"team.lead", "team.coordinator", "paths.decision_log", "team.projects", "team.session_prefix", "team.legacy_prefixes", "paths.claude_bin", "paths.board_dir", "paths.bd_command", "paths.panel", "paths.ask_owner", "paths.milestone_dir"}
# Each pair: the first key only works with the second one set.
NEEDS = [("paths.board_dir", "paths.bd_command"), ("paths.bd_command", "paths.board_dir"), ("paths.panel", "paths.ask_owner"),
         ("paths.ask_owner", "paths.panel"), ("paths.milestone_dir", "paths.board_dir")]


def check_layer(raw: dict, file_label: str) -> None:
    check_keys(raw, SCHEMA, "", file_label)


def check_complete(merged: dict, file_label: str) -> None:
    missing = [key for key in required_keys(SCHEMA, "") if not has_key(merged, key)]
    if missing:
        raise ConfigError(f"{file_label}: {missing[0]} is missing (set it here or in the global config)"
                          + (f", and {len(missing) - 1} more" if len(missing) > 1 else ""))
    for key, needed in NEEDS:
        if has_key(merged, key) and not has_key(merged, needed):
            raise ConfigError(f"{file_label}: {key} is set but {needed} is not")
    if merged["paths"]["gate_logs"] == "panel.json scratch" and not has_key(merged, "paths.panel"):
        raise ConfigError(f"{file_label}: paths.gate_logs reads the panel's scratch but paths.panel is not set")


def check_keys(raw: dict, schema: Dict[str, object], prefix: str, file_label: str) -> None:
    for key, value in raw.items():
        if key.startswith("_"):
            continue  # "_note": JSON has no comments, so the files carry their why in underscore keys
        name = prefix + key
        if key not in schema:
            raise ConfigError(f"{file_label}: {name} is not a known key")
        expected = schema[key]
        if isinstance(expected, dict):
            if not isinstance(value, dict):
                raise ConfigError(f"{file_label}: {name} must be an object, got {kind_of(value)}")
            check_keys(value, expected, name + ".", file_label)
        elif not CHECKS[expected](value):
            raise ConfigError(f"{file_label}: {name} must be {expected}, got {kind_of(value)}")


def required_keys(schema: Dict[str, object], prefix: str) -> List[str]:
    found = []
    for key, expected in schema.items():
        name = prefix + key
        found += required_keys(expected, name + ".") if isinstance(expected, dict) else [] if name in OPTIONAL else [name]
    return found


def has_key(merged: dict, dotted: str) -> bool:
    node = merged
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def kind_of(value) -> str:
    return JSON_KINDS.get(type(value), type(value).__name__)
