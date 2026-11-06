#!/usr/bin/env python3
"""Blocks until the owner answers an ask on the panel, prints each new answer, exits.

Brain runs it in the background, like the grill page's `wait`: the owner's answer ends the process and the
harness wakes brain at once (owner 2026-10-19: "exactly as grill me page the message comes to you").
No timer: it sleeps on a kqueue event for the folder, because ask_owner.py swaps panel.json in with os.replace.
"""
import argparse
import fcntl
import json
import os
import select
import sys
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import suite_config  # noqa: E402

PANEL = suite_config.board_file("AGENT_PANEL", "panel.json")
# Answers brain has been told about; read at start so one that lands between two waiters is not taken as seen.
SEEN = os.path.join(os.path.dirname(PANEL), "state", "brain_seen_answers.json")


def answered_ids() -> set:
    try:
        with open(PANEL) as f:
            return {a.get("id") for a in json.load(f).get("answered", [])}
    except (OSError, ValueError):
        return set()  # mid-swap or unreadable: the next folder event reads it again


def new_answers(known: set) -> list:
    with open(PANEL) as f:
        return [a for a in json.load(f).get("answered", []) if a.get("id") not in known]


def seen_ids() -> set:
    try:
        with open(SEEN) as f:
            return set(json.load(f))
    except (OSError, ValueError):
        return answered_ids()  # first run: everything answered so far counts as told


def remember(ids: set) -> None:
    os.makedirs(os.path.dirname(SEEN), exist_ok=True)
    with open(f"{SEEN}.{os.getpid()}.tmp", "w") as f:
        json.dump(sorted(ids), f)
    os.replace(f"{SEEN}.{os.getpid()}.tmp", SEEN)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--known", default="", help="answered ids already handled, comma separated; default: all now")
    args = parser.parse_args()
    # Two waiters share the seen file: one reports an answer, the other marks it seen and its output is lost
    # (2026-10-22 four keep-warm answers went unreported). Only one may run.
    lock = open(SEEN + ".lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit("panel_wait: another waiter is running; stop it first")
    known = set(filter(None, args.known.split(","))) or seen_ids()
    folder = os.open(os.path.dirname(PANEL), os.O_RDONLY)
    queue = select.kqueue()
    watch = select.kevent(folder, filter=select.KQ_FILTER_VNODE, flags=select.KQ_EV_ADD | select.KQ_EV_CLEAR,
                          fflags=select.KQ_NOTE_WRITE)
    while True:
        if answered_ids() - known:
            # The owner answers several asks in a burst (9 in one second on 2026-10-31); wait for the rest.
            time.sleep(3)
        fresh = [a for a in new_answers(known) if a.get("id")] if answered_ids() - known else []
        if fresh:
            # Count first: brain once read only the tail of this output and missed 5 of 8 answers (2026-10-31).
            print(f"{len(fresh)} NEW ANSWERS: {' '.join(a['id'] for a in fresh)}")
            for answer in fresh:
                print(f"ANSWER {answer['id']} | {answer.get('text', '')[:160]} | owner: {answer.get('answer')}")
            remember(known | {a["id"] for a in fresh})
            sys.exit(0)
        queue.control([watch], 1, None)


if __name__ == "__main__":
    main()
