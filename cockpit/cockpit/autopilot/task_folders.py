import os
import re
from typing import Iterable, Set

# A path a bead names: its scope line, or a token that looks like a path (starts at ~ or /, ends in / or a file
# extension), so "rtk/caveman/ponytail" in prose is not taken for a folder.
SCOPE = re.compile(r"^\s*scope:(.*)$", re.MULTILINE | re.IGNORECASE)
PATH = re.compile(r"(?<![\w:/])(~?/[\w.@-]+(?:/[\w.@-]+)*/?|[\w.@-]+(?:/[\w.@-]+)+(?:/|\.\w{1,5}))(?![\w/])")


def named_folders(text: str) -> Set[str]:
    """The folders a bead's text names; a file stands for its folder."""
    found = set()
    for scope in SCOPE.findall(text or ""):
        found |= {folder(p) for p in PATH.findall(scope)}
    for path in PATH.findall(text or ""):
        found.add(folder(path))
    return {f for f in found if f}


def folder(path: str) -> str:
    path = os.path.expanduser(path)
    return path.rstrip("/") if path.endswith("/") or not os.path.splitext(path)[1] else os.path.dirname(path)


def folders_of(files: Iterable[str]) -> Set[str]:
    return {os.path.dirname(f) for f in files if f}


def overlaps(a: str, b: str) -> bool:
    """One folder holds the other. A relative path (cockpit/autopilot) matches wherever it sits in an absolute one."""
    def parts(p):
        return [x for x in p.split("/") if x]
    pa, pb = parts(a), parts(b)
    if a.startswith("/") and b.startswith("/"):
        short, long = sorted((pa, pb), key=len)
        return long[:len(short)] == short
    short, long = sorted((pa, pb), key=len)
    return any(long[i:i + len(short)] == short for i in range(len(long) - len(short) + 1))


def shares_folder(next_folders: Iterable[str], done_folders: Iterable[str]) -> bool:
    done = list(done_folders)
    return any(overlaps(n, d) for n in next_folders for d in done)
