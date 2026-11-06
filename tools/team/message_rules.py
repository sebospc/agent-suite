# What a SendMessage body must hold, for send_guard.py: docs/PROTOCOL.md (real counts, never "tests pass") and
# relays word for word (the coordinator summarised a peer on 2026-11-05).
import json
import re

from transcript_tail import tail_lines

SUBJECT = r"\b(?:tests?|suites?|checks?|builds?|lint|gate|runs?|all|it|everything)"
# "make the gate pass" asks for a result; "tests pass", "it passed" and "is green" report one.
CLAIM = re.compile(rf"{SUBJECT}\s+pass(?:es|ed)\b|\b(?:tests|suites|checks|builds|runs|all|everything)\s+pass"
                   r"(?=\s*(?:$|[.,;:)]|\s(?:on|in|with|again|now|and|here)\b))"
                   rf"|(?:{SUBJECT}|\b(?:is|are|was|were|stays?|still|now))\s+green\b", re.IGNORECASE)
CONDITION = re.compile(r"\b(?:if|once|until|unless|when|whether)\s+(?:\S+\s+){0,3}$", re.IGNORECASE)
# The scanner prints this and nothing else; step_log.py counts it as one check.
COUNTLESS_TOOL_LINE = "check_security: all green"
RELAY_HEADER = re.compile(r"^coordinator relay from ([\w.-]+):[ \t]*(.*)$", re.IGNORECASE)
RECEIVED = re.compile(r'<cross-session-message[^>]*\bfrom-name="([^"]+)"[^>]*>(.*?)</cross-session-message>', re.DOTALL)
OWN_NOTE = re.compile(r"^\(?coordinator\b", re.IGNORECASE)
# A relay quotes recent messages.
TAIL_BYTES = 30_000_000


def normalized(text: str) -> str:
    return " ".join(text.split())


def relay_sections(message: str) -> list[tuple[str, list[str]]]:
    sections = []
    for line in message.splitlines():
        header = RELAY_HEADER.match(line.strip())
        if header:
            sections.append((header[1], [header[2]] if header[2] else []))
        elif sections:
            sections[-1][1].append(line)
    return sections


def reports_a_result(line: str) -> bool:
    if COUNTLESS_TOOL_LINE in line or re.search(r"\d", line):
        return False
    return any(not CONDITION.search(line[:claim.start()]) for claim in CLAIM.finditer(line))


def count_problem(message: str) -> str | None:
    relayed = {line for _, body in relay_sections(message) for line in body}
    # A relayed line is its author's report: their own guard checked it when they sent it.
    claims = [line for line in message.splitlines() if line not in relayed and reports_a_result(line)]
    if not claims:
        return None
    return (f"send_guard: this line reports a result with no count: {claims[0].strip()[:120]!r}. Give the numbers "
            "(N passed, M failed, K skipped), docs/PROTOCOL.md.")


def strings_in(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings_in(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings_in(item)


def received_by_sender(transcript_path: str) -> dict[str, str]:
    lines = tail_lines(transcript_path, TAIL_BYTES)
    received: dict[str, list[str]] = {}
    for line in lines:
        if "cross-session-message" not in line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        for text in strings_in(entry):
            for sender, body in RECEIVED.findall(text):
                received.setdefault(sender, []).append(normalized(body))
    return {sender: " ".join(bodies) for sender, bodies in received.items()}


def quoted(line: str, author_text: str) -> bool:
    after_label = line.partition(": ")[2]
    return line in author_text or bool(after_label) and after_label in author_text


def relay_problem(message: str, transcript_path) -> str | None:
    sections = relay_sections(message)
    if not sections or not isinstance(transcript_path, str):
        return None
    received = received_by_sender(transcript_path)
    for author, body in sections:
        # Nothing from the author in the tail: there is nothing to check against, so the relay goes through.
        if author not in received:
            continue
        lines = [normalized(line) for line in body if line.strip() and not OWN_NOTE.match(line.strip())]
        # A relay may put its own label before a quoted line ("part for agent-ios: GRANT ..."); the quote must match.
        missing = next((line for line in lines if not quoted(line, received[author])), None)
        if missing:
            return (f"send_guard: this relayed line is not in any message from {author}: {missing[:120]!r}. Relay "
                    "the author's words unchanged, or point to the author's file instead of retelling it.")
    return None


def content_problem(message, transcript_path) -> str | None:
    if not isinstance(message, str):
        return None
    return count_problem(message) or relay_problem(message, transcript_path)
