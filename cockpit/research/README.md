# Calibration scripts

The scripts behind the cockpit's numbers. Each prints numbers only, never message content. Run them on your own
transcripts and board to calibrate the thresholds for your team (`docs/CALIBRATION.md`); the raw research data they
were first run on belongs to the first project and is not in this repo.

| File | What |
|---|---|
| `scripts/measure_context.py` | Reads Claude Code transcripts and prints usage numbers: context per request, growth, token mix, TTL, cycle-cost model. `python3 -I measure_context.py ~/.claude/projects` |
| `scripts/calibrate_sessions.py` | Per-session sweet-spot inputs (g, y, F, P, F_s, S, rework, idle gaps, Haiku over 100k) |
| `scripts/calibrate_quota.py` | Fits how the 5h and 7d limits weigh each token kind, from usage samples |
| `scripts/measure_thresholds.py` | Ask waits, bead silences and beads held at once, from the board |
| `scripts/transcript_requests.py`, `scripts/least_squares.py`, `scripts/test_phase0.py` | Shared reader, the stdlib fit, and their tests (`python3 -m unittest test_phase0` from `scripts/`) |
| `scripts/m.py`, `scripts/idle.py` | A re-derivation of the sweet-spot math and the idle-compaction simulation |
