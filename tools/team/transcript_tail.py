# Transcripts reach a gigabyte and hooks run on every send or stop, so they read only the recent end.
import os


def tail_lines(path: str, max_bytes: int) -> list[str]:
    size = os.path.getsize(path)
    with open(path, "rb") as transcript:
        transcript.seek(max(0, size - max_bytes))
        lines = transcript.read().decode(errors="replace").splitlines()
    # A seek lands mid-line, so its first line is a fragment; from the file's start, every line is whole.
    return lines[1:] if size > max_bytes else lines
