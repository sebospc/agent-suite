# Calibration (phase 0)

Numbers measured from the owner's data. Each section names the script, the data and the date. The
owner sets each threshold in `config/thresholds.json` from these numbers; until then the cockpit shows
the starting value as provisional.

## Board thresholds (from the board snapshot, agent-board 3dd1d84, Oct 15 23:05)

`python3 research/scripts/measure_thresholds.py --board <snapshot>/board --beads <snapshot>/beads/issues.jsonl`

Asks, asked to answered (74 answered asks with both times):

| Kind | n | p50 | p90 | p95 | max | over 15 min | over 1 h | over 4 h |
|---|---|---|---|---|---|---|---|---|
| blocker | 17 | 0.15 h | 2.32 h | 7.73 h | 12.18 h | 41% | 24% | 12% |
| design | 57 | 0.90 h | 7.35 h | 10.70 h | 17.69 h | 63% | 40% | 30% |

Reading for the "Blocker ask waiting" light (starting value 1 h): half the blocker asks were answered
within 9 minutes; 24% waited over 1 h. At 1 h the light would have lit for about one blocker in four.

Beads in progress (436 claimed at least once):

| Measure | p50 | p90 | p95 | over 6 h | over 12 h | over 24 h |
|---|---|---|---|---|---|---|
| Longest gap between visible updates (upper bound) | 3.29 h | 18.38 h | 37.02 h | 30% | 18% | 7% |
| Claim to close | 3.29 h | 17.63 h | 35.42 h | 29% | | 7% |

Limits of this measure: only started_at, comments and closed_at carry a time (notes edits do not), and
only 91 of the 436 beads got a comment while in progress, so the gap is close to the claim-to-close
time. A bead that simply takes a day looks silent. The "Silent bead" light (starting value 6 h) would
have lit on about 30% of beads. A truer signal needs a timestamped update the team writes while
working (a comment or a heartbeat); the cockpit can also use the holder's transcript activity on
the bead.

Beads held in progress at once (upper bound, a bead set back to open keeps its started_at): peaks of
12 (agent-ai, agent-android), 9 (agent-ios), 8 (agent-design, agent-format). The
one-bead rule (check 4) is far from how the team has worked.

Found on the way: assignees `agent-investigator` and `shaping-lead` hold beads; neither is in the
cockpit's session list yet (check 5).

## Live board (brain on the Mac, Oct 15 21:50, 734 beads)

`measure_thresholds.py` on ~/.agent-beads. It confirms the snapshot within a few points:

| Measure | n | p50 | p90 | p95 | over 1 h | over 6 h | over 12 h | over 24 h |
|---|---|---|---|---|---|---|---|---|
| Blocker ask, asked to answered | 17 | 0.15 h | 2.32 h | 7.73 h | 24% | | | 0% |
| Design ask, asked to answered | 62 | 0.82 h | 7.35 h | 10.70 h | 37% | | | 0% |
| Longest silence while in progress (upper bound) | 436 | 3.33 h | 18.38 h | 35.50 h | | 31% | 18% | 7% |

In progress at the read: pg-a18q.69, .67, .64 (about 15 h), .50.1 (16 h), .53, .50, .49 (21 h), .35 (40 h), all
during the pause. `bd export --all` prints one bead per line on stdout (the cockpit's default works).
`agent-investigator` is an on-demand role in the first project's workflow doc; it is now in .cockpit.json team.

## Sessions (brain on the Mac, Oct 15, `calibrate_sessions.py --days 14`)

616 main-thread transcripts, 161 with requests in 14 days, 585 compactions recorded. Growth and output per
turn, medians over sessions, tokens in k:

| Model | Effort | Sessions | g | y |
|---|---|---|---|---|
| Opus 5.5 | medium | 94 | 1.3 | 0.41 |
| Opus 5.5 | max | 37 | 1.5 | 0.61 |
| Opus 5.5 | high | 13 | 1.2 | 0.35 |
| Sonnet 5.5 | medium | 11 | 1.3 | 0.45 |
| Fable 5.1 | high | 1 | 1.5 | 0.59 |
| Haiku 5.5 | high | 1 | 0.8 | 0.22 |

Fable 5.1 now has a price card ($10 / $12.50 / $20 / $0.25 / $50 per M, from the pricing lane in
the first project's research data).

Compactions (`--summary`, 26 team sessions): Opus 5.5 medium, 535 compactions, 472 automatic, medians
pre 268k, P 63k, F_s 23k. The team's sessions compact at about 267k, a window near 300k. Rework (k_R, D) came
out 0 everywhere: the re-read heuristic finds none, so rework shows up only inside P. The first run printed
S < 0 because it took post minus the first request (a transcript that starts with a resume begins above the
floor); S is now post minus F_s.

What that means at list price (g 1.2k, y 0.45k, P 63k, F_s 23k, S 25k to 40k): Opus 5.5 sweet spot about
165k to 180k (window 195k to 215k), about 7% to 9% less per turn than compacting at 267k. Weighting by quota
may move it (unknown 1 below).

Coordinator (Haiku 5.5): 2,237 requests above 100k in 14 days, compacting at 267k. At list price a turn there
costs about 5 times a turn under 100k ($0.0095 vs $0.0019); its sweet spot keeps every prompt under 100k
(window about 130k). This is the clearest token saving found; it needs team.json (dependency 8).

Idle gaps of 1 min or more over all sessions: n 12,768, p50 2.7 m, p90 30.7 m; 22% over 10 m, 6% over 60 m.

Sessions named agent-security (Fable 5.1) and agent-ultrareview exist in transcripts but not in
the first project's workflow table; they are not in .cockpit.json team until brain says what they are.

## Quota weighting (brain on the Mac, Oct 15)

Run 2: 23 distinct account emails in transcripts and 0 match the 7 cswap lists exactly, so every token is
"not listed". Run 3 found the cause (brain): attachment.context.userEmail holds a sentence ("The user's email
address is X. Use it only ..."), not an address. transcript_requests.py now takes the address out of it.

Run 4: emails match (22 of 23 transcript emails share a domain with cswap; tokens land on accounts 1, 2, 3 and
18 to 21), but the fit was all zeros: the 17 usable 20-minute spans showed no 5h % change, and 1,482 had no
tokens. cswap's usage value lags and reports the reset time with jitter (1,315 distinct values for account 1).
The script now takes one point per 5h window per account (resets within 15 min count as one window), from
its first to its last sample, and prints how many windows moved.

Run 5 (139 windows on accounts 1, 2, 3, 18 to 21; median move 72 points): list dollars explain the 5h %
better than raw tokens (R2 0.637 against 0.586), 2.771 Pro-% per list dollar. Unconstrained per-kind weights
went negative (fresh -52.4, read -0.0004), which a token cannot do; the script now keeps every weight at 0 or
above and drops windows that reach the limit (use past 100% does not show). Weekly: one weekly point costs
7.55 five-hour points on Pro and 8.81 on Max 5x, against the balancer's 6.5 for every plan.

Decision for the cockpit: sweet spots stay on list prices, which the data supports better than raw tokens; the
screen keeps calling them list-price estimates. The weekly ratios and the 1h-write cost go to brain for the
balancer (BALANCER.md improvement 2).

Balancer patch (brain, panel a5749e, not applied): weekly ratios per plan from run 5 (Pro 7.55, Max 5x 8.81,
Max 20x 1.95, which keeps its old weight because no 20x account exists); the cold-turn cost stays 0.054 until a
non-negative fit over about 300 windows agrees.

Run 6 (2026-10-18, plans from the owner, fc58d4: "acc 1 is max all the rest are pro"; calibrate_quota.py now
uses account 1 Max 5x and every other account Pro when cswap's config shows no tier): 73 windows, the same as
with plans only for accounts 1, 2, 3 and 18, because accounts 4 to 17 and 19 to 21 have usage samples but no
tokens in the transcripts. One weekly point costs 7.16 five-hour points on Pro (36 intervals) and 7.70 on Max 5x
(28), against run 5's 7.55 and 8.81 and the balancer's 6.5. List dollars explain the 5h % with R2 0.970 (2.465
Pro-% per dollar); the 1h-write cold-turn cost is 0.0289 per 1k tokens by category, 0.0197 from list dollars,
against the balancer's 0.054.

## To fill from the owner's Mac

| Section | Script |
|---|---|
| Compaction medians per model and effort, team sessions, idle gaps | `calibrate_sessions.py --summary` |
| Per-kind weights with no negatives, limit windows dropped (optional) | `calibrate_quota.py` (rerun) |
| Board thresholds on the live board | done above |

## Provisional thresholds: the builder sets them from the logs (the owner, 2026-10-16)

The owner: "yo no se por eso te pido a ti que te encargues ... es muy de probar ... los logs son super importantes para
calibrar estos datos". No public number exists for these; each is set from what the cockpit logs on the Mac, and its
`source` in `config/thresholds.json` says when and from what it was last set.

| Threshold | Log that calibrates it | How |
|---|---|---|
| `autopilot_idle_minutes` | actions.jsonl `sent` and `skipped` (idle minutes in the reason) | lowest idle time after which the session took no new turn within the next 10 min, in 90% of cases |
| `haiku_guard_pct` | transcripts: Haiku turn growth | 100k minus the 90th percentile growth per turn, as a share of 100k |
| `recovery_idle_gap_minutes` | transcripts: gaps between a session's requests with no prompt between them, 24 h | learned (pg-o1sq): their 99th percentile in whole minutes, from 100 gaps; `cockpit/refit/fitters.py` |
| `cache_expiry_margin_minutes` | actions.jsonl autopilot `sent` compactions and their `done` records' `proved_at` | learned (pg-o1sq step 7): 95th percentile of send to compact_boundary, plus one read, rounded up; `cockpit/refit/fitters.py` |
| `jev_yes_probability` | actions.jsonl `task_start` with Jev's bead scores, the cut-off and the control id, joined to `wrong` and `wrong_clear` | learned once 20 TASK starts are labelled (pg-o1sq): the cut-off from 0.30 to 0.90 that gets most of them right, nearest the current on a tie; a start is left out as confounded (pg-6inz, owner b289d0 C) when, between it and its session's next TASK start or a day, a model, effort or plugin relaunch control was sent, a TASK came by fallback, its process started again or Claude Code auto-compacted it (`process_started`, `auto_compacted` records); `cockpit/refit/fitters.py` |
| `high_context_tokens`, `tokens_day_over_avg_pct`, `tokens_per_bead_rise_pct` | transcripts, 14 days | the spread of a normal week, so the mark lights about once a week |
| `duplicate_window_minutes` | transcripts: peer messages with the same body | the gap between repeats of the same event |
| `price_max_age_days`, `relaunch_min_saving_pct`, `messages_per_bead_floor` | transcripts, prices.json | as their sources in `config/thresholds.json` say |
