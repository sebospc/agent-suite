from cockpit.classifier.jev_classifier import yes_no

# Design pg-o1sq Q1 and Q12: Jev answers the judgments, plain code (suggestion_table.py) turns them into settings.
# The session verdict is about the session's work as a whole, never one bead alone: a mechanical bead held by brain
# once made Jev's bead answer put brain on Haiku (jev_record.jsonl, pg-z061).
SESSION_QUESTIONS = {
    "deep_reasoning": yes_no("Does the work of `session` (its role, its open beads, the milestone it serves) need deep reasoning from an AI coding agent?",
                             "Architecture or design choices, coordination of other agents, subtle bugs, security, many interacting constraints.",
                             "Known plans carried out carefully are enough."),
    "mechanical": yes_no("Is the work of `session` mostly mechanical, doable from each bead's description alone?",
                         "Fully specified small edits, renames, config changes, status updates, lookups.",
                         "It needs judgment, design, investigation or coordination."),
    "wide_reading": yes_no("Does the work of `session` need reading widely across the codebase?",
                           "Many files or folders, cross-cutting changes, surveys before acting.",
                           "A few known files at a time."),
    "mistake_costly": yes_no("Is a mistake by `session` costly?",
                             "It touches shared code other sessions build on, lands or pushes, is hard to undo, or is not reviewed by another session.",
                             "Its changes stay in its own folder, are easy to undo and are reviewed before they land."),
}

# The bead verdict decides only compact or clear before the next bead starts (Q1): what of the context it needs.
BEAD_QUESTIONS = {
    "needs_history": yes_no("Does `next_task` depend on what `session` already worked out in its current context?",
                            "It continues earlier work: findings, a half-done change, a review round on its own patch.",
                            "It can start from the files and the description alone."),
    "related": yes_no("Is `next_task` related to what `session` worked on last (`session.last_task`, `session.last_turns`)?",
                      "The same feature, the same files or folders, or work that follows from it.",
                      "Another area: what is in its context now would not help."),
    "long": yes_no("Is `next_task` long work for an AI coding agent?",
                   "Likely more than about 20 turns: several files, a design step, or review rounds.",
                   "A short change of a few turns."),
}
