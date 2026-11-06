#!/usr/bin/env python3
"""Copies the board folder, an export of the beads and the team memory folders to a private git repo, so a cloud
session or a new machine starts from the same state. Run it after every push.

This sends the board off the machine: the remote is the project's own private repo, set by the owner in the config
(`snapshot.remote`). A secret scan (gitleaks) runs on the copy first; a finding, or no gitleaks, pushes nothing.

Config, `snapshot`: remote (required), clone (default ~/.agent-board-snapshot), memory_dirs (name -> folder),
exclude (extra rsync patterns), bd_actor (default the lead's session name).
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import suite_config  # noqa: E402

# Backups, the beads store and caches stay local; the export carries the beads.
EXCLUDE = ("*.bak*", "__pycache__/", ".dolt/", ".beads/", ".git/", "*.db", ".beads-credential-key", "*.lock",
           ".agents/", ".codex/", ".cursor/", ".claude/")


def plan(config: dict) -> list:
    """The steps as (label, argv, cwd) so a test can read them without running anything."""
    snap = config["snapshot"]
    if not snap.get("remote"):
        raise suite_config.ConfigError("snapshot.remote is not set: no private repo to push to")
    board = os.path.expanduser(config["board_dir"]).rstrip("/") + "/"
    clone = os.path.expanduser(snap.get("clone", "~/.agent-board-snapshot"))
    actor = snap.get("bd_actor") or suite_config.session_name(config, config["lead"])
    excludes = [f"--exclude={pattern}" for pattern in (*EXCLUDE, *snap.get("exclude", []))]
    steps = []
    if not os.path.isdir(os.path.join(clone, ".git")):
        steps.append(("clone", ["git", "clone", "-q", snap["remote"], clone], None))
    steps += [("pull", ["git", "-C", clone, "pull", "-q", "--ff-only"], None),
              ("board", ["rsync", "-a", "--delete", *excludes, board, f"{clone}/board/"], None)]
    if os.path.isdir(os.path.join(board, ".beads")):
        steps.append(("beads", ["sh", "-c", f'mkdir -p "{clone}/beads" && BEADS_ACTOR="{actor}" bd export --all '
                                            f'> "{clone}/beads/issues.jsonl"'], board))
    for name, folder in sorted(snap.get("memory_dirs", {}).items()):
        steps.append((f"memory {name}", ["rsync", "-a", "--delete", "--exclude=*.bak*",
                                         os.path.expanduser(folder).rstrip("/") + "/", f"{clone}/{name}/"], None))
    steps += [("secret scan", ["gitleaks", "detect", "--no-git", "--no-banner", "--redact", "-s", clone], None),
              ("stage", ["git", "-C", clone, "add", "-A"], None)]
    return steps


def run(config: dict) -> str:
    if shutil.which("gitleaks") is None:
        raise suite_config.ConfigError("gitleaks is not installed; nothing pushed")
    clone = os.path.expanduser(config["snapshot"].get("clone", "~/.agent-board-snapshot"))
    for label, argv, cwd in plan(config):
        if subprocess.run(argv, cwd=cwd, capture_output=label == "secret scan").returncode != 0:
            raise suite_config.ConfigError(f"{label} failed; nothing pushed")
    if subprocess.run(["git", "-C", clone, "diff", "--cached", "--quiet"]).returncode == 0:
        return "board snapshot: no change"
    # The clone's own git identity signs the commit; the suite never writes a name.
    subprocess.run(["git", "-C", clone, "commit", "-q", "-m", f"Snapshot of the board on {time.strftime('%F')}"], check=True)
    subprocess.run(["git", "-C", clone, "push", "-q", "origin", "HEAD"], check=True)
    head = subprocess.run(["git", "-C", clone, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout
    return f"board snapshot: pushed {head.strip()}"


if __name__ == "__main__":
    try:
        print(run(suite_config.load()))
    except (suite_config.ConfigError, subprocess.CalledProcessError) as error:
        print(f"board_snapshot: {error}", file=sys.stderr)
        sys.exit(1)
