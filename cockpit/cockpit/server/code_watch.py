import hashlib
import os
from typing import Iterable


def fingerprint(folders: Iterable[str], suffixes: tuple) -> str:
    """One short id for every file with these suffixes under the folders: changes when one is added, removed or
    saved again. Each call walks the folders (a few hundred files; cheap at one call every few seconds)."""
    stamps = [stamp(path) for path in folders if os.path.isfile(path)]  # a config file watched on its own
    for folder in folders:
        for root, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in files:
                if name.endswith(suffixes):
                    stamps.append(stamp(os.path.join(root, name)))
    return hashlib.sha256("\n".join(sorted(s for s in stamps if s)).encode()).hexdigest()[:12]


def stamp(path: str) -> str:
    try:
        return f"{path}:{os.stat(path).st_mtime_ns}"
    except OSError:
        return ""
