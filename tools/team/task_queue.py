#!/usr/bin/env python3
"""The task queue: in_flight.json in the board folder holds the tickets in flight, the ones waiting on the owner,
and each session's next tickets in order.

Mutual exclusion: a session holds one ticket in flight at a time, so `start` refuses a session that already holds
one. Tickets run together only when their sessions are disjoint. A ticket waiting on the owner does not hold its
session.

  task_queue.py show
  task_queue.py start BEAD SESSION [SESSION ...] [--what TEXT]
  task_queue.py wait BEAD [--ask ID] [--what TEXT]      move a ticket in flight to waiting on the owner
  task_queue.py done BEAD                                take a ticket off the board
  task_queue.py add SESSION BEAD [BEAD ...]              queue next tickets for a session
  task_queue.py hand SESSION                             start the session's next queued ticket, print its id
"""
import argparse
import contextlib
import fcntl
import json
import os
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
import suite_config  # noqa: E402

EMPTY = {"tasks": [], "waiting_owner": [], "queue": []}


class Refused(Exception):
    pass


def in_flight_path(config: dict) -> Path:
    return Path(os.environ.get("AGENT_IN_FLIGHT") or suite_config.board_path(config, "in_flight.json"))


@contextlib.contextmanager
def locked(path: Path, empty: dict = EMPTY):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path) + ".lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        board = read(path, empty)
        yield board
        path.with_suffix(".tmp").write_text(json.dumps(board, indent=2, ensure_ascii=False) + "\n")
        os.replace(path.with_suffix(".tmp"), path)


def read(path: Path, empty: dict = EMPTY) -> dict:
    try:
        board = json.loads(path.read_text())
    except FileNotFoundError:
        board = {}
    return {**{key: list(value) for key, value in empty.items()}, **board}


def holder(board: dict, session: str) -> Optional[str]:
    return next((task["bead"] for task in board["tasks"] if session in task.get("sessions", [])), None)


def start(board: dict, bead: str, sessions: list, what: str = "") -> None:
    if any(task["bead"] == bead for task in board["tasks"]):
        raise Refused(f"{bead} is already in flight")
    for session in sessions:
        held = holder(board, session)
        if held:
            raise Refused(f"{session} already holds {held}; one ticket in flight per session")
    board["tasks"].append({"bead": bead, "sessions": list(sessions), **({"what": what} if what else {})})
    for entry in board["queue"]:
        if entry["agent"] in sessions and bead in entry["next"]:
            entry["next"].remove(bead)


def take(board: dict, bead: str) -> Optional[dict]:
    for key in ("tasks", "waiting_owner"):
        for entry in board[key]:
            if isinstance(entry, dict) and entry.get("bead") == bead:
                board[key].remove(entry)
                return entry
    return None


def wait(board: dict, bead: str, ask: str = "", what: str = "") -> None:
    task = take(board, bead)
    if task is None:
        raise Refused(f"{bead} is not in flight")
    board["waiting_owner"].append({**task, **({"ask": ask} if ask else {}), **({"what": what} if what else {})})


def add(board: dict, session: str, beads: list) -> None:
    entry = next((e for e in board["queue"] if e["agent"] == session), None)
    if entry is None:
        entry = {"agent": session, "next": []}
        board["queue"].append(entry)
    entry["next"].extend(bead for bead in beads if bead not in entry["next"])


def hand(board: dict, session: str) -> Optional[str]:
    if holder(board, session):
        return None
    entry = next((e for e in board["queue"] if e["agent"] == session and e["next"]), None)
    if entry is None:
        return None
    bead = entry["next"][0]
    start(board, bead, [session])
    return bead


def main(argv) -> int:
    parser = argparse.ArgumentParser(description="The team's task queue (in_flight.json).")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("show")
    p = sub.add_parser("start"); p.add_argument("bead"); p.add_argument("sessions", nargs="+"); p.add_argument("--what", default="")
    p = sub.add_parser("wait"); p.add_argument("bead"); p.add_argument("--ask", default=""); p.add_argument("--what", default="")
    p = sub.add_parser("done"); p.add_argument("bead")
    p = sub.add_parser("add"); p.add_argument("session"); p.add_argument("beads", nargs="+")
    p = sub.add_parser("hand"); p.add_argument("session")
    args = parser.parse_args(argv)
    path = in_flight_path(suite_config.load())
    if args.action == "show":
        print(json.dumps(read(path), indent=2, ensure_ascii=False))
        return 0
    try:
        with locked(path) as board:
            if args.action == "start":
                start(board, args.bead, args.sessions, args.what)
                print(f"started {args.bead} for {', '.join(args.sessions)}")
            elif args.action == "wait":
                wait(board, args.bead, args.ask, args.what)
                print(f"{args.bead} waits on the owner")
            elif args.action == "done":
                print(f"{args.bead} off the board" if take(board, args.bead) else f"{args.bead} was not on the board")
            elif args.action == "add":
                add(board, args.session, args.beads)
                print(f"queued for {args.session}: {', '.join(args.beads)}")
            else:
                bead = hand(board, args.session)
                print(bead or f"nothing to hand {args.session}")
    except Refused as error:
        print(f"refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
