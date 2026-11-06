import bisect
from typing import List, Tuple

from cockpit.transcripts.history import PeerMessage, Request, ReviewRequest
from cockpit.transcripts.transcript_file import TranscriptFile
from cockpit.transcripts.transcript_stats import processed, start_load


def history_of_file(main: TranscriptFile, extra: List[TranscriptFile], start: float,
                    live_name: str = "") -> Tuple[List[Request], List[PeerMessage], List[tuple], List[ReviewRequest]]:
    """A session's requests since start, each tagged with the prompt that started its turn, and the peer messages it
    received with what their turns cost. A request before any prompt is the session's own work."""
    name = live_name or (main.titles[-1] if main.titles else "")
    if not name:
        return [], [], [], []
    prompts = sorted(main.prompts, key=lambda p: p["t"])
    stamps = [p["t"] for p in prompts]

    def prompt_index(t: float) -> int:
        return bisect.bisect_right(stamps, t) - 1

    requests, turn_tokens = [], {}
    for file, is_main in [(main, True)] + [(f, False) for f in extra]:
        for row in file.requests():
            t = row["t_first"] or 0
            if t < start or (is_main and row["sidechain"]):
                continue
            at = prompt_index(t)
            requests.append(Request(t=t, session=name, tokens=processed(row), context=row["context"] if is_main else 0,
                                    origin=prompts[at]["origin"] if at >= 0 else "own", turn=f"{main.path}#{at}",
                                    read=row["read"], out=row["out"], write=row["write"], model=row["model"] or "",
                                    effort=row.get("effort") or ""))
            turn_tokens[at] = turn_tokens.get(at, 0) + processed(row)
    messages = [PeerMessage(t=p["t"], to=name, type=p["type"], bead=p["bead"], in_format=p["in_format"], digest=p["digest"],
                            tokens=turn_tokens.get(i, 0), keys=p.get("keys") or {}, head=p.get("head") or "")
                for i, p in enumerate(prompts) if p["origin"] == "peer" and p["t"] >= start]
    mains = [r for r in main.requests() if not r["sidechain"]]
    load = start_load(mains, prompts)
    starts = [(name, mains[0]["t_first"], load)] if mains and load and (mains[0]["t_first"] or 0) >= start else []
    sent = [ReviewRequest(t=s["t"], sender=name, bead=s["bead"], sha256=s["sha256"], context=main.rows[s["row"]].get("context", 0),
                          model=main.rows[s["row"]]["model"] or "")
            for s in main.review_requests if s["t"] >= start and main.rows[s["row"]].get("context")]
    return requests, messages, starts, sent
