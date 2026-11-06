import os
import shutil
import threading
import time
from typing import Dict, Optional

from cockpit.disk.disk import Disk
from cockpit.source_unavailable import SourceUnavailable

FOLDERS_EVERY_S = 600  # walking a month of transcripts takes seconds; a folder's size moves slowly


def folder_size(path: str) -> Optional[int]:
    if not os.path.isdir(path):
        return None
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                continue
    return total


class DiskUsage(Disk):
    def __init__(self, volume: str, folders: Dict[str, str]):
        self.volume = volume
        self.folders = {name: os.path.expanduser(path) for name, path in folders.items()}
        self.sizes: Dict[str, Optional[int]] = {}
        self.sized_at = 0.0
        self.lock = threading.Lock()

    def read(self) -> dict:
        try:
            usage = shutil.disk_usage(self.volume if os.path.exists(self.volume) else os.path.expanduser("~"))
        except OSError as error:
            raise SourceUnavailable(f"disk usage of {self.volume}: {error}")
        with self.lock:
            if time.time() - self.sized_at > FOLDERS_EVERY_S:
                self.sizes = {name: folder_size(path) for name, path in self.folders.items()}
                self.sized_at = time.time()
            sizes = dict(self.sizes)
        return {"volume": self.volume, "free": usage.free, "total": usage.total, "folders": sizes}
