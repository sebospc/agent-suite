#!/usr/bin/env python3
"""Named resource slots, granted one holder at a time: a simulator, a heavy build, a test database.

The slots come from the project config (`slots`: name -> {"minutes": usual hold}); an unknown name is refused, so a
typo never makes a new resource. A request on a busy slot joins its waiting line; `free` grants the next one and
prints who to tell (the coordinator sends that session SLOT-FREE). State: slots.json in the board folder.

  slots.py show
  slots.py request SLOT SESSION [--minutes N] [--run TEXT]
  slots.py free SLOT SESSION
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import suite_config  # noqa: E402
from task_queue import Refused, locked, read  # noqa: E402


def slots_path(config: dict) -> Path:
    return suite_config.board_path(config, "slots.json")


def request(board: dict, known: dict, slot: str, session: str, minutes: int, run: str, now: float) -> str:
    if slot not in known:
        raise Refused(f"no slot named {slot}; the config has {', '.join(sorted(known)) or 'none'}")
    state = board.setdefault(slot, {"holder": None, "waiting": []})
    ask = {"session": session, "minutes": minutes or known[slot].get("minutes", 30), "run": run}
    if state["holder"] and state["holder"]["session"] == session:
        return f"{session} already holds {slot}"
    if state["holder"] is None:
        state["holder"] = {**ask, "since": now}
        return f"granted {slot} to {session}"
    if all(w["session"] != session for w in state["waiting"]):
        state["waiting"].append(ask)
    position = [w["session"] for w in state["waiting"]].index(session) + 1
    return f"{slot} is held by {state['holder']['session']}; {session} waits, number {position}"


def free(board: dict, slot: str, session: str, now: float) -> str:
    state = board.get(slot)
    if not state or not state["holder"] or state["holder"]["session"] != session:
        raise Refused(f"{session} does not hold {slot}")
    state["holder"] = None
    if not state["waiting"]:
        return f"{slot} is free"
    nxt = state["waiting"].pop(0)
    state["holder"] = {**nxt, "since": now}
    return f"{slot} granted to {nxt['session']}: tell it SLOT-FREE"


def overdue(board: dict, now: float) -> list:
    # Twice the asked minutes, so a slow run is not flagged but a forgotten SLOT-FREE is.
    return [f"{slot} held by {s['holder']['session']} for {round((now - s['holder']['since']) / 60)} min"
            for slot, s in sorted(board.items())
            if s.get("holder") and now - s["holder"]["since"] > 2 * 60 * s["holder"]["minutes"]]


def main(argv) -> int:
    parser = argparse.ArgumentParser(description="Named resource slots, one holder at a time.")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("show")
    p = sub.add_parser("request"); p.add_argument("slot"); p.add_argument("session")
    p.add_argument("--minutes", type=int, default=0); p.add_argument("--run", default="")
    p = sub.add_parser("free"); p.add_argument("slot"); p.add_argument("session")
    args = parser.parse_args(argv)
    config = suite_config.load()
    path = slots_path(config)
    now = time.time()
    if args.action == "show":
        board = read(path, {})
        for slot in sorted(config["slots"]):
            state = board.get(slot) or {"holder": None, "waiting": []}
            holder = state["holder"]["session"] if state["holder"] else "free"
            print(f"{slot}: {holder}; waiting {', '.join(w['session'] for w in state['waiting']) or 'none'}")
        for line in overdue(board, now):
            print("overdue:", line)
        return 0
    try:
        with locked(path, {}) as board:
            if args.action == "request":
                print(request(board, config["slots"], args.slot, args.session, args.minutes, args.run, now))
            else:
                print(free(board, args.slot, args.session, now))
    except Refused as error:
        print(f"refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
