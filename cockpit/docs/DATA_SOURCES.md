# Data sources

Everything the cockpit reads, where, in what format, and the traps. Formats for the board files are
in `fixtures/` (real data, trimmed). Sources for the Claude Code facts: `research/raw/tools-and-sources.json`
(official docs read on 2026-10-15, Claude Code 2.1.301, plus verifier corrections).

The panel (`reference/panel/team-roadmap/panel.py`) already reads most of these; reuse its working
details (timeouts on `bd`, herdr quirks), not its percent bar or mode buttons.

## Paths on the owner's Mac

| What | Path or command |
|---|---|
| Repo (shared checkout) | `~/Documents/project` (panel.py `REPO`); landing ref `stack-brain` |
| Board | `~/.agent-board` (run `bd` there with `BEADS_ACTOR=<name>`) |
| Panel asks | `~/.agent-board/panel.json`, written only through `ask_owner.py` |
| Milestone done criteria | `~/.agent-board/dod.json`; goal metric `~/.agent-board/goal.json` |
| Stack of commits and slots | `~/.agent-board/stack.json` |
| Transcripts (all accounts) | `~/.claude/projects/-Users-me-Documents-project/<session-id>.jsonl` |
| cswap profiles | `~/.claude-swap-backup/sessions/<n>-<email>/` (macOS) |
| Live session records | `<profile>/sessions/<pid>.json`, and `~/.claude/sessions/<pid>.json` for the default login |
| Account settings (the window step's proof) | `<profile>/settings.json`, and `~/.claude/settings.json` for the default login; read only |
| Balancer state | `~/.claude/handoff/state/` (`usage-samples.jsonl`, `affinity.json`, `limited.json`, `live/`) |
| grill-with-ui sessions | `~/.grill-with-ui/<session>/{state.json, events.jsonl, server.json}` |
| herdr | `herdr` CLI |

## What the cockpit writes

- `~/.cockpit/actions.jsonl`: one line per control or autopilot action, and one line per
  proof of it (`proves` names the action's `id`). Append only.
- `~/.cockpit/metrics.jsonl`: one line per read, `{"t", "areas": {area: {row id: {column: value} or null}}}`,
  only the rows that changed since the line before; the first line of a run holds every row. Append only. About 1 to
  10 KB a line at one read every 30 s; rotate it by month when a history click takes over a second.
- `~/.agent-board/paused`: the pause hook's mode file (pg-nplt, written by the project repo
  `tools/team_pause.py`). The cockpit only reads whether it exists; nothing the autopilot types
  goes out while it does.
- `modelSettings.<model>.autoCompactWindow` in a session's user settings, only through the
  autopilot's `/autocompact` step (`REQUIREMENTS.md`), once per model per cswap account. `/autocompact` takes 100K to 1M as a plain
  count (`1000000`), a `k`/`M` suffix or a bare 100 to 1000; it saves under the model's canonical
  name and applies to the session it is typed into (code.claude.com/docs/en/model-config, "Set the
  auto-compact window"). `CLAUDE_CODE_AUTO_COMPACT_WINDOW` in a session's environment overrides it,
  and `--autocompact` overrides it for that launch.

## Claude Code transcripts (tokens, context, model, messages)

- One JSONL per session. With `cswap run N --share-history`, every profile's `projects/` is a
  symlink to `~/.claude/projects`, so all sessions of all accounts land in one tree. Subagents in
  `<session-id>/subagents/`. A launch without `--share-history` removes the link: detect it.
- Assistant lines carry `message.id`, `message.model`, `message.usage.{input_tokens,
  output_tokens, cache_creation_input_tokens, cache_read_input_tokens, cache_creation.{ephemeral_1h_input_tokens, ephemeral_5m_input_tokens}}`,
  `requestId`, `sessionId`, `timestamp`, `isSidechain`, `version`.
- Trap: one response is written as up to 4 lines (one per content block) repeating the usage. Count
  once per `message.id` (fallback `requestId`): input sides once, output at its maximum. Skip
  `message.model == "<synthetic>"`.
- Context now = input + cache_read + cache_creation of the newest main-thread (`isSidechain` false)
  assistant entry; after `{type:"system", subtype:"compact_boundary", compactMetadata:{trigger, preTokens, postTokens}}`
  use postTokens until the next turn. `panel.py context_tokens()` does exactly this.
- Session name: last `{type:"custom-title", customTitle}` else `{type:"ai-title", aiTitle}`. Launch
  sessions with `--name old-<role>` so the name is stable.
- Account: transcripts may carry `session_context.userEmail` in recent versions (unconfirmed on the
  Mac); the reliable way is the live record below.
- Messages between sessions: the sender's transcript has the send tool call; the receiver gets a
  `<cross-session-message …>` user line (the balancer and owner_ask_guard key on that prefix).
- The format is internal and can change between Claude Code versions: keep the parser in one
  adapter with fixture tests (`fixtures/transcript.sample.jsonl`).
- Default retention is 30 days (`cleanupPeriodDays`).

## Live sessions, account, busy/idle

- `<profile>/sessions/<pid>.json`: `pid`, `sessionId`, `cwd`, `name`, `kind`, `status`, `startedAt`.
  The profile folder name `<n>-<email>` gives the account. Default-login sessions are in
  `~/.claude/sessions/`.
- herdr: `herdr pane list` (JSON `result.panes[]`, use panes with `agent_session`; it misses agents
  in panes it did not start), `herdr pane process-info --pane <id>`, `herdr agent read <pane> --source visible`
  (only the visible screen, else it scrolls the owner's pane), `herdr agent prompt <pane> <text>`
  (types into the pane; a busy agent runs it after its turn). See `panel.py panes()` and `live_status()`.
- `claude agents --json` lists live sessions with `status` busy/waiting/idle, one supervisor per
  config dir; it has no token fields and its summaries are model-written. Optional.

## Accounts and quota

- `cswap list --json` (read-only; run with `env -u CLAUDE_CONFIG_DIR`): per account `number`,
  `email`, `usage.fiveHour.{pct, resetsAt}`, `usage.sevenDay.{pct, resetsAt}`, `usageAgeSeconds`,
  `usageStatus`, plan. Values are the server's; respect their age. See `reference/balancer/pick_account.py`.
- The balancer's decision log does not exist yet (see `TEAM_DEPENDENCIES.md`).

## Board

- Beads: `bd list --json` / `bd show <id> --json` (or the export format in
  `fixtures/beads.sample.jsonl`): `id`, `title`, `status` (open, in_progress, blocked, closed),
  `priority`, `issue_type` (milestone, task, bug…), `assignee`, `labels` (dod, nice, from:Mn),
  `dependencies[]` (`type` parent-child, blocks, related, discovered-from), `updated_at`, `notes`.
  bd waits on a board lock while another session writes: always use a timeout (panel.py `run()`).
- `dod.json`, `goal.json`, `stack.json`, `panel.json`: see fixtures.
- `ask_owner.py answer <id> "<owner's words>"` is the only way an ask leaves the panel; never edit
  panel.json by hand (owner, 2026-10-12).

## Optional live feeds (phase 2 or later)

- Status line JSON: Claude Code passes each session's `session_id`, `session_name`,
  `context_window.{total_input_tokens, used_percentage, context_window_size}`, `rate_limits`,
  `effort.level` to a status line command. A command in the repo's `.claude/settings.json` (scope
  "any file") covers every cswap profile; it can append each JSON to a file the cockpit reads.
  Changing settings needs the owner's yes.
- OpenTelemetry `api_request` events carry per-request tokens with `user.email` (splits accounts)
  and `query_source="compact"` for the summary call (the only place its tokens appear). Needs a
  local OTLP receiver; OTel variables must be set in the launch shell.
- Hooks (`UserPromptSubmit`, `PostCompact`, `Stop`) can log events to a JSONL keyed by session.
