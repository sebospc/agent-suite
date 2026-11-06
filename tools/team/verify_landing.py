#!/usr/bin/env python3
# The after-landing check that replaced the reviewer's VERIFIED turn (owner panel 10400b: "a script does the after-landing check").
import argparse
import re
import subprocess
import sys
from pathlib import Path

AI_MENTION = re.compile(r"claude|co-authored", re.IGNORECASE)
# A short prefix would match almost any tree; 8 is the shortest a GO line quotes
GO_TREE = re.compile(r"[0-9a-f]{8,40}")


def git(*args: str, stdin: str = "") -> str:
    return subprocess.run(["git", *args], input=stdin, capture_output=True, text=True, check=True).stdout


def patch_id(diff: str) -> str:
    out = git("patch-id", "--stable", stdin=diff).split()
    return out[0] if out else ""


def problems(sha: str, go_tree: str, message: Path, patch: Path, branch: str) -> list:
    found = []
    tree = git("rev-parse", f"{sha}^{{tree}}").strip()
    if not GO_TREE.fullmatch(go_tree):
        found.append(f"GO tree {go_tree!r} is not 8 to 40 hex characters")
    elif not tree.startswith(go_tree):
        found.append(f"tree {tree[:8]} is not the GO tree {go_tree[:8]}")
    body = git("cat-file", "commit", sha).split("\n\n", 1)[1]
    if body != message.read_text():
        found.append(f"commit message differs from {message.name}")
    if AI_MENTION.search(body):
        found.append("commit message names claude or co-authored")
    landed = patch_id(git("show", "--format=", "--binary", sha))
    frozen = patch_id(patch.read_text())
    if not landed or not frozen:
        found.append("no patch-id: the frozen patch or the landed diff is empty")
    elif landed != frozen:
        found.append(f"patch-id {landed[:8]} differs from the frozen patch's {frozen[:8]}")
    if subprocess.run(["git", "merge-base", "--is-ancestor", sha, branch]).returncode != 0:
        found.append(f"{sha[:9]} is not on {branch}")
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a landed commit against its frozen patch, message and GO tree.")
    parser.add_argument("sha")
    parser.add_argument("--go-tree", required=True)
    parser.add_argument("--message", type=Path, required=True)
    parser.add_argument("--patch", type=Path, required=True)
    parser.add_argument("--branch", default="origin/develop")
    args = parser.parse_args()
    found = problems(args.sha, args.go_tree, args.message, args.patch, args.branch)
    for line in found:
        print(f"NOT VERIFIED {args.sha[:9]}: {line}")
    if not found:
        print(f"VERIFIED {args.sha[:9]}: tree = GO tree, message = frozen file, claude 0, patch-id = frozen patch, on {args.branch}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
