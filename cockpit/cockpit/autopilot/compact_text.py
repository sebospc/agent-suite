from cockpit.autopilot.turn_end import is_haiku

# The coordinator (the team's Haiku session) re-reads about 54k after every compaction, 82k with its system and tools,
# against Claude Code's ~98k window: each token of summary is a token it has less to work in before the next one. Its
# summary was 8k of that (2026-10-22 measure, panels f68cd6 to b31e2b).
SHORT_SUMMARY = ("/compact Keep the summary under 400 words: open work and who holds it, messages still waiting for an "
                 "answer, and the next step. Leave out finished work, file contents and message text already acted on.")


def compact_text(row: dict) -> str:
    return SHORT_SUMMARY if is_haiku(row) else "/compact"
