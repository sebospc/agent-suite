#!/usr/bin/env python3
"""python3 tools/doctor.py DIR: read-only check of a project's adoption. For each part DIR chose: its bins, env keys
and the parts it needs, its config, and its hooks in DIR/.claude/settings.json. One line per problem, exit 1 if any;
`warn` lines (an optional need missing, so one feature stays off) never fail it.
"""
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install_team  # noqa: E402

sys.path.insert(0, str(install_team.TEAM))
import suite_config  # noqa: E402


def config_problems(name: str, config: dict) -> list:
    if name == "snapshot" and not config["snapshot"].get("remote"):
        return ["snapshot: snapshot.remote is not set"]
    if name == "slots" and not config["slots"]:
        return ["slots: no slots in the config"]
    if name == "memory" and os.environ.get("ENGRAM_CLOUD_AUTOSYNC"):
        return ["memory: ENGRAM_CLOUD_AUTOSYNC is set; memory would leave the machine"]
    return []


def check(project_dir: Path, which=shutil.which, environ=os.environ) -> list:
    parts = install_team.choices(project_dir)
    config = suite_config.load(str(project_dir))
    chosen = {name for name, choice in parts.items() if choice in install_team.CHOSEN}
    lines = []
    for name, part in install_team.manifest().items():
        if name not in chosen:
            continue
        needs = part["needs"]
        lines += [f"{name}: {bin_} is not on PATH" for bin_ in needs["bins"] if not which(bin_)]
        lines += [f"{name}: {key} is not set" for key in needs["env"] if not environ.get(key)]
        lines += [f"{name}: needs the {other} part" for other in needs["parts"] if other not in chosen]
        lines += [f"warn {name}: {bin_} is not on PATH (optional)" for bin_ in needs["optional_bins"] if not which(bin_)]
        lines += config_problems(name, config)
    status = install_team.status(project_dir)
    if not status.startswith("installed:"):
        lines += status.splitlines()
    return lines


def main(argv) -> int:
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        lines = check(Path(argv[0]).expanduser().resolve())
    except (install_team.InstallError, suite_config.ConfigError) as error:
        print(f"doctor: {error}")
        return 1
    for line in lines:
        print(line)
    problems = [line for line in lines if not line.startswith("warn ")]
    print("doctor: ok" if not problems else f"doctor: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
