#!/usr/bin/env python3
"""The only way to put a question to the owner: it lands on the panel at once, and an answer
moves it to `answered` with the owner's words, so no question is ever lost or deleted.

  ask_owner.py add "<text, at most 2 lines>" --kind blocker|design --by <session> \
      --option "A" --option "B" [--bead t-12] [--reply "<context>"] [--image <png>] \
      [--covered "key: value (default)"]... [--fixed "reason: what"]... [--not-covered "what: reason"]...

A bead left blocked or pending because it needs the owner names its unblocking action here with --bead
(the owner, 2026-10-12); team_check.py flags a blocked bead with no open ask.
  ask_owner.py answer <id> "<the owner's words>" [--by <session that recorded it>]
  ask_owner.py list
"""
import argparse
import fcntl
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import suite_config  # noqa: E402

PANEL = suite_config.board_file("AGENT_PANEL", "panel.json")
LOCK = PANEL + ".lock"
KINDS = ("blocker", "design")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ask_id(text):
    return hashlib.sha256(text.encode()).hexdigest()[:6]


def edit(change):
    with open(LOCK, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with open(PANEL) as f:
            panel = json.load(f)
        result = change(panel)
        tmp = PANEL + ".tmp"
        with open(tmp, "w") as f:
            json.dump(panel, f, indent=1)
        os.replace(tmp, PANEL)
        return result


def recommendation(rec, why, options):
    # the cockpit shows each ask as a grill round, which always carries one pick and its why (owner 2026-10-15)
    if not any(option == rec or option.startswith(rec + ":") for option in options):
        sys.exit(f"--rec {rec!r} names no --option (give the option's letter, e.g. A)")
    if not why.strip() or "\n\n" in why:
        sys.exit("--why is one paragraph")
    return {"option": rec, "why": why.strip()}


def add(args):
    if args.text.count("\n") > 1:
        sys.exit("at most 2 lines")
    if len(args.option) < 2:
        sys.exit("give at least 2 --option")
    new = {"id": ask_id(args.text), "text": args.text, "options": args.option, "kind": args.kind,
           "by": args.by, "asked": now(), "updated": now(), "reply": args.reply,
           "rec": recommendation(args.rec, args.why, args.option)}
    if args.covered or args.fixed or args.not_covered:
        # the panel draws coverage as three lists; a single string blanked the design screen (26eba5)
        new["coverage"] = {"covered": args.covered, "fixed": args.fixed, "notCovered": args.not_covered}
    if args.image:
        new["image"] = os.path.abspath(args.image)
    if args.bead:
        new["bead"] = args.bead

    def put(panel):
        if any(a["text"] == args.text for a in panel["asks"]):
            return "already on the panel"
        panel["asks"].append(new)
        return f"asked {new['id']}"
    print(edit(put))


def answer(args):
    def move(panel):
        match = [a for a in panel["asks"] if a.get("id", ask_id(a["text"])) == args.id]
        if not match:
            sys.exit(f"no open ask {args.id}")
        panel["asks"].remove(match[0])
        recorded = {"answered_by": args.by} if args.by else {}  # the cockpit sends its answer notice to everyone else
        panel.setdefault("answered", []).append({**match[0], "answer": args.words, "answeredAt": now(), **recorded})
        bead = match[0].get("bead")
        return f"answered {args.id}" + (f"; now unblock {bead}" if bead else "")
    print(edit(move))


def show(_):
    with open(PANEL) as f:
        panel = json.load(f)
    for a in panel["asks"]:
        print(a.get("id", ask_id(a["text"])), a.get("kind", "blocker"), a.get("by", "?"), a["text"][:90])
    print(f"{len(panel.get('answered', []))} answered on record")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(required=True)
    p_add = sub.add_parser("add")
    p_add.add_argument("text")
    p_add.add_argument("--kind", choices=KINDS, required=True)
    p_add.add_argument("--by", required=True)
    p_add.add_argument("--option", action="append", default=[])
    p_add.add_argument("--reply", default="")
    p_add.add_argument("--covered", action="append", default=[])
    p_add.add_argument("--fixed", action="append", default=[])
    p_add.add_argument("--not-covered", action="append", default=[])
    p_add.add_argument("--image", default="")
    p_add.add_argument("--bead", default="")
    p_add.add_argument("--rec", required=True)
    p_add.add_argument("--why", required=True)
    p_add.set_defaults(run=add)
    p_answer = sub.add_parser("answer")
    p_answer.add_argument("id")
    p_answer.add_argument("words")
    p_answer.add_argument("--by", default="")
    p_answer.set_defaults(run=answer)
    sub.add_parser("list").set_defaults(run=show)
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
