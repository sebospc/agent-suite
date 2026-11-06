# Compaction: each session's sweet spot

The owner: "(the owner's words)". This doc turns that into a
model the cockpit computes per session from measured inputs.

Sources: the first project's research data, not in this repo (four research lanes, a modeller and two verifiers;
every price checked against platform.claude.com pricing on 2026-10-15). Measurement script:
`research/scripts/measure_context.py` (output `measure_context.run3.txt`, one Opus 5.5 session at
effort xhigh/high, 750 requests, no compactions). Verifier scripts: `research/scripts/m.py`, `idle.py`.

## Why a big context costs more

Every turn re-reads the whole context from cache. Cache reads are cheap per token but scale with
the context. Measured on Opus 5.5 with this session's inputs: about $0.063 per turn at 150k,
$0.093 at 300k, $0.226 at 967k. Opus 5.5 has a native 1M window and by default compacts only at
about 967k (docs: model-config, "Default auto-compact thresholds").

The real "costs double" sources:
- Rebuilding the cache costs 2x base input on the 1h TTL (40x a cache read on Opus and Sonnet 5.5):
  after every compaction, and after an idle gap over 1 h without idle compaction.
- Haiku 5.5 bills the whole request 5x (all categories, output included) when the prompt
  (input + cache reads + cache writes) exceeds 100,000 tokens. The coordinator runs on Haiku.
- Fast mode costs 2x.
- Opus 5.5, Sonnet 5.5 and Fable 5.1 have no long-context premium (no 200k step).

## Why a small window can cost more

Each compaction has a fixed cost: the summary request, rewriting the post-compaction prefix at the
2x write price, and rework (re-reading files the summary dropped). A small window means more
compactions. With heavy rework a 150k window cost 1.7x to 6.7x the sweet spot in the worked
examples; with a compaction at a natural break (little rework) 150k cost only 5% more.

## The model

Symbols (all measurable per session, see "Inputs"):
- c context of a request = input + cache_read + cache_creation tokens
- P context at the start of a cycle (after compaction and rework); F floor (system prompt, tools,
  CLAUDE.md, memory); F_s stable cached prefix that survives a compaction
- S summary tokens kept; T_s summary output beyond S; D rework tokens; k_R rework requests
- g context growth per turn (mean, not median: cost is linear); y output per turn (effort sets it)
- q share of turns after an idle gap over the TTL with no idle compaction
- r cache read, w cache write at the session's TTL (1h = 2x input), o output, i input ($/token)

Per turn with a warm cache: `cost(c) = r*c + w*g + o*y`.

One compaction: `C' = r*P + o*(S + T_s) + w*(P - F_s) + R` (cold cache: the summary read is `i*W`
instead of `r*W`).

R, the recovery cost, is measured (replacing `k_R*(r*P + o*y)`, whose re-read heuristic found 0
everywhere, CALIBRATION.md): from each `compact_boundary`, the tokens of the session's requests until
its first edit or new file (Edit, MultiEdit, NotebookEdit, Write), priced at the session's card, minus
one normal turn at P (`r*P + w*g + o*y`), never below 0. A span stops at the first of: that edit
(not counted, it is the work itself), 10 requests, the task end (`bd close` in a Bash call), or the next
compaction. A request after an idle gap over `recovery_idle_gap_minutes` is skipped (a new prompt or a
cold cache, not recovery). A span the transcript has not finished yet is not counted.

R is grouped by task kind: the labels of the bead the session held at the compaction (process labels
dod, nice and from:Mn left out), else Jev's category for the bead (the judgment with the highest
probability at or over `jev_yes_probability`, else "plain"), else "no bead". Each kind's R is the
mean of its last 20 compactions, as a token mix priced at the session's own card. A kind with fewer
than `recovery_min_compactions` uses the fleet's last 20, marked provisional. Jev is asked for at most
5 new beads per read, and not while the team is paused.

Flat-price models (Opus 5.5, Sonnet 5.5): the window that minimises cost per turn is

```
x* = sqrt(2 * g * C' / (r + q*(w - r)))      (q term only where idle compaction cannot fire)
trigger* = P + x*
window setting = trigger* + 33,000
```

The +33k is because Claude Code v2.1.301 triggers compaction at `W - min(maxOutputTokens, 20000) - 13000`
(read from the binary by the verifier; matches 1M - 33k = 967k). So a 100k setting compacts at about
67k and a 300k setting at about 267k. Confirm with `compact_boundary.compactMetadata.preTokens`.

The optimum depends only on price ratios, so Opus 5.5 and Sonnet 5.5 share it; Haiku's is smaller.

Haiku 5.5 (price step at 100k): evaluate the exact cost on a grid instead of the closed form.
Candidate 1 keeps every prompt (and the summary request) under 100k: a setting of about
133,000 - g_p90 - margin, never 100,000 (that compacts at 67k). Candidate 2 is the flat optimum on
the over-100k card. Keep the cheaper; check that no request exceeded 100k. With an expensive R the
grid can choose over 100k; then the Haiku guard (autopilot rule 1) steps aside and the session is
compacted at its sweet spot like any other.

Robust procedure for any model: evaluate the average cost per turn A(W) on a 5k grid from 100k to the
model window (renewal-reward per cycle, including idle compaction when it applies) and take the
argmin; the closed form seeds it. Clamp to at least `P + 2*g_p90` (Claude Code stops auto-compacting
after 3 consecutive refills) and at most the owner's quality cap W_q.

## Inputs, per session (from its main-thread transcript)

| Input | How to measure |
|---|---|
| model | `message.model` on main-thread assistant entries (`isSidechain` false) |
| TTL (sets w) | `usage.cache_creation.ephemeral_1h_input_tokens` vs `ephemeral_5m_input_tokens`; main thread on a subscription is 1h, subagents 5m, usage-credit traffic 5m |
| c per request | `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`; dedupe entries by `message.id` (one response is written as up to 4 entries repeating the same usage) |
| g, y | trimmed means over the last 50 main-thread turns, excluding the first turn after a compaction or cold miss and rework turns |
| F, F_s | first request's c; `cache_read_input_tokens` of the first request after a `compact_boundary` (separately: after a cold gap) |
| P, S | c of the first request after `compact_boundary` (P0 = F + S); `compactMetadata.postTokens` as cross-check |
| T_s | not in the transcript (the summary call skips it); OTel `api_request` with `query_source="compact"`, else assume T_s = y |
| R | measured: the recovery span after each boundary (above), by task kind, mean of the last 20 |
| q | share of turns whose gap exceeds the TTL, excluding turns right after idle compaction |

Before a session's first compaction, use fleet medians by model and effort, flagged provisional.

## Rules the cockpit applies

1. Recompute inputs after every `compact_boundary` and on a schedule; use the last 3 cycles.
2. Show per session: context now, its sweet spot, and the reason in one sentence.
3. Apply a new window only at launch with `--autocompact <plain integer>` from team.json. Never use
   `/autocompact` per session: it saves one value per model for every session (the current panel's
   bug). `CLAUDE_CODE_AUTO_COMPACT_WINDOW` also forces the window onto the session's subagents.
   The one exception is the autopilot's window step (`REQUIREMENTS.md`): 1M per model per account
   while it is on, 200k when it turns off.
4. Relaunch for a new window only when the predicted saving is at least 5% (hysteresis, a design
   choice).
5. At a task boundary, when the next task does not depend on the current one, prefer `/clear`
   (no summary, no rework).
6. Keep idle compaction on (default for interactive sessions on the 1h TTL at 200k+): it avoids
   rebuilding a 300k cache (about 22 normal turns on Opus) after an hour idle.
7. Haiku sessions: keep every prompt under 100k (see above).
8. Thrash guard: if two compactions in a row refill to the trigger, raise the window or clear. Built:
   when the first request after each of a session's last two compactions is at or above the line the
   autopilot compacts it at (its sweet spot, or the Haiku guard), the autopilot compacts it no more
   and its skip reason asks to raise its window or clear it; a task-end clear is still allowed.
9. Effort changes keep the cache on the 5.5 models; a model change rewrites the whole cache, so
   model changes happen only with a clear or at launch.

## Unknowns that need the owner's data (phase 0)

1. How Max-plan 5h/7d limits weight cache reads, 1h writes and output. The sweet spot moves a lot:
   283k weighted by dollars vs 151k weighted by raw tokens in one example. Calibrate from the
   balancer's `~/.claude/handoff/state/usage-samples.jsonl`: regress the 5h % deltas against the
   token mix of the same window.
2. Real S, T_s, D, k_R per model and effort (no compaction was measurable here).
3. Output per turn at effort medium for Opus 5.5, and for Haiku 5.5 at high.
4. A quality-vs-context curve for the 5.5 models does not exist publicly; the quality cap W_q is
   the owner's parameter, starting at no cap.
