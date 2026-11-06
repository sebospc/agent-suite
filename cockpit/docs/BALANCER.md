# The cswap balancer

Code: `reference/balancer/` (lives on the Mac in `~/.claude/handoff`, with shell wrappers in fish and
zsh). Read `reference/balancer/README.md` and `pick_account.py`. The cockpit only reads it; changes to
it go through brain.

## What it does

- Picks the cswap account for each Claude session at launch (`claude` wrapper runs
  `cswap run <n> --share-history -- <args>`), and re-checks on every prompt (UserPromptSubmit hook)
  and on a usage-limit failure (StopFailure hook).
- Score per account (`capacity_score`): free 5h quota weighted by plan (Pro 1, Max 5x 5, Max 20x 20),
  capped by free weekly quota (weights 1, 3.5, 6), plus credit for 5h quota about to reset and weekly
  quota that would be lost at the weekly reset. Minus `LIVE_SESSION_PENALTY = 25` per live session.
  Plus `account-limits.json` priority.
- A session with a warm prompt cache stays on its account unless that account can no longer serve
  it; a cold one moves only when another account beats it by `MOVE_MARGIN = 15`. Moving is a
  relaunch: the hook blocks the prompt, writes a relaunch file, stops Claude Code, and the wrapper
  resumes the session on the new account.
- Usage limits: 85% of 5h, 95% of 7d (env overridable).

It already handles the cache cost of moving accounts (the prompt cache is per account).

## What the cockpit shows from it

- Per account: 5h and 7d use, reset times, the 85% tick, sessions on it (from live session records).
- "Why the balancer chose": each decision with time, session, chosen account, the score of each
  account and the reason (warm cache kept, best capacity, barred after a limit). This needs the
  decision log below.
- Moves today and what each cost (the turns rebuilding the cache).

## Improvements found (for the team, not the cockpit)

1. Every session counts the same (`LIVE_SESSION_PENALTY`). An Opus worker at 300k and the Haiku
   coordinator spend very differently. Better: subtract each session's measured spend (quota % per
   hour) from its transcripts and `usage-samples.jsonl`.
2. Its constants come from one sample: `WEEKLY_PCT_IN_5H_PCT = 6.5` ("one coarse sample …
   recalibrate from usage-samples.jsonl") and `COLD_TURN_PRO_PCT_PER_1K_TOKENS = 0.054`. The cockpit's
   calibration (`COMPACTION.md`, unknown 1) uses the same samples and can feed both.
3. Its tests assume `~/.claude/handoff/state/` exists, so they fail on a clean machine.
