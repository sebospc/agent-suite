#!/usr/bin/env python3
# Fails when a name from the git-ignored .project-names file appears in suite code or docs.
# The project data folders are skipped: they belong to one project and carry its names by design.
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAMES_FILE = ROOT / ".project-names"
PROJECT_DATA = ("board/", "beads/", "memory/")


def project_names() -> list[str]:
    if not NAMES_FILE.exists():
        return []
    return [line.strip() for line in NAMES_FILE.read_text().splitlines() if line.strip()]


def suite_files() -> list[str]:
    tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True, check=True).stdout
    return [path for path in tracked.splitlines() if not path.startswith(PROJECT_DATA)]


def leaks(names: list[str]) -> list[str]:
    pattern = re.compile("|".join(re.escape(name) for name in names), re.IGNORECASE)
    found = []
    for path in suite_files():
        try:
            text = (ROOT / path).read_text(errors="ignore")
        except OSError:
            continue
        found += [f"{path}:{number}" for number, line in enumerate(text.splitlines(), 1) if pattern.search(line)]
    return found


def main() -> int:
    names = project_names()
    if not names:
        print("check_no_project_names: no .project-names file, nothing to check", file=sys.stderr)
        return 0
    found = leaks(names)
    for place in found:
        print(place)
    print(f"check_no_project_names: {len(found)} line(s) name a project")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
