#!/usr/bin/env python3
"""Builds one Engram import file (format 0.2.0) from a folder of markdown memory files with a front matter
(name, description, type) and a MEMORY.md index. Reads only; the old folder is never changed.

  migrate_md_memory.py MEMORY_DIR OUT.json --project NAME [--pin-section TITLE ...] [--archive-role ROLE ...]
                       [--merge EXTRA.md=KEEPER.md ...]
  engram import OUT.json

Each file becomes one observation: type from the file's kind, topic_key `rule/...`, `project/...`, `ref/...`,
`owner/...`, or `role/<role>/state` for a `project_<role>_state.md` file (`archive/role/...` for a paused role).
Files the index lists under a --pin-section heading are pinned, so they load at every session start.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SESSION = "memory-migration"
TYPE_BY_KIND = {"feedback": "learning", "topic": "learning", "project": "decision", "reference": "config", "user": "decision"}
KEY_BY_KIND = {"feedback": "rule", "topic": "rule", "project": "project", "reference": "ref", "user": "owner"}
LINK = re.compile(r"\(([\w.-]+\.md)\)")


def frontmatter(text: str) -> tuple:
    if not text.startswith("---"):
        return {}, text
    head, _, body = text[3:].partition("\n---")
    fields = dict(re.findall(r"^\s*(name|description|type):\s*(.+?)\s*$", head, re.MULTILINE))
    return fields, body.lstrip("\n")


def index_sections(index: str) -> dict:
    section, by_file = "", {}
    for line in index.splitlines():
        if line and not line.startswith(("-", " ")):
            section = line.strip().lstrip("#").strip()
        for name in LINK.findall(line):
            by_file.setdefault(name, section)
    return by_file


def topic_key(stem: str, kind: str, archived: tuple) -> str:
    rest = stem.split("_", 1)[1] if "_" in stem else stem
    role = re.fullmatch(r"(\w+?)_state", rest)
    if kind == "project" and role:
        return f"{'archive/role' if role[1].startswith(archived) else 'role'}/{role[1]}/state"
    return KEY_BY_KIND.get(kind, "misc") + "/" + rest.replace("_", "-")


def observations(memory: Path, project: str, pinned_sections: tuple, archived: tuple, merged: dict, now: str) -> list:
    index = memory / "MEMORY.md"
    sections = index_sections(index.read_text()) if index.exists() else {}
    merged_into = {}
    for extra, keeper in merged.items():
        merged_into.setdefault(keeper, []).append((memory / extra).read_text())
    found = []
    for path in sorted(memory.glob("*.md")):
        if path.name == "MEMORY.md" or path.name in merged:
            continue
        fields, body = frontmatter(path.read_text())
        kind = fields.get("type") or path.stem.split("_", 1)[0]
        key = topic_key(path.stem, kind, archived)
        description = fields.get("description", "").strip().strip('"')
        extra_bodies = [frontmatter(text)[1].strip() for text in merged_into.get(path.name, [])]
        found.append({
            "session_id": SESSION, "type": TYPE_BY_KIND.get(kind, "discovery"), "title": (description or path.stem)[:120],
            "project": project, "scope": "project", "topic_key": key,
            "content": "\n\n".join([f"**What** {description}", body.strip(), *extra_bodies, f"**Where** memory/{path.name}"]),
            "pinned": sections.get(path.name) in pinned_sections and not key.startswith(("role/", "archive/")),
            "created_at": now, "updated_at": now,
        })
    return found


def main(argv) -> int:
    parser = argparse.ArgumentParser(description="Markdown memory files to one Engram import file.")
    parser.add_argument("memory_dir", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--project", required=True)
    parser.add_argument("--pin-section", action="append", default=[])
    parser.add_argument("--archive-role", action="append", default=[])
    parser.add_argument("--merge", action="append", default=[], help="EXTRA.md=KEEPER.md: two files for one rule")
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    merged = dict(pair.split("=", 1) for pair in args.merge)
    found = observations(args.memory_dir, args.project, tuple(args.pin_section), tuple(args.archive_role), merged, now)
    export = {"version": "0.2.0", "exported_at": now,
              "sessions": [{"id": SESSION, "project": args.project, "directory": str(args.memory_dir), "started_at": now}],
              "observations": found, "prompts": []}
    args.out.write_text(json.dumps(export, indent=1, ensure_ascii=False))
    print(f"{len(found)} observations, {sum(item['pinned'] for item in found)} pinned, {len(merged)} merged -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
