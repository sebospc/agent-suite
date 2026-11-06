# Cockpit

A local HTML cockpit for the owner of an agent team: about ten long-running Claude Code
sessions (brain, coordinator, reviewers, ai, ios, android, format, backend, design) on one Mac,
in herdr panes, on several Claude accounts rotated by cswap and a balancer.

It replaces the roadmap panel (a Claude Code mod). The owner stops using the panel once the
cockpit answers asks.

Status: phase 0 scripts and the phase 1 read-only cockpit are built (`docs/PLAN.md`). Run it with `python3 cockpit.py`
(`docs/RUNNING.md`). Start at `CLAUDE.md`.

## What it must do

1. Show the current milestone with genuine progress (the goal metric first, never a closed-beads bar)
   and prove whether the team is working on it.
2. Show what each session is doing right now, and whether the team is in order.
3. Let the owner answer every pending ask in an embedded grill-with-ui round.
4. Show where tokens go, and manage each session's context against its own sweet spot.
5. Offer a few basic controls whose effect is verified on screen (compact, clear at task end, effort,
   pause the team), plus an autopilot the owner switches on per rule.

## Map

| Path | What |
|---|---|
| `CLAUDE.md` | Rules for whoever builds this. Read first |
| `docs/MILESTONE.md` | The milestone view and how "is the team on it" is computed (now a Needs you row and marks) |
| `docs/COMPACTION.md` | The sweet-spot cost model, prices, rules and what is still unknown |
| `docs/DATA_SOURCES.md` | Every file and command the cockpit reads, with formats and traps |
| `docs/GRILL.md` | How asks become an embedded grill-with-ui round |
| `docs/BALANCER.md` | The cswap balancer, what the cockpit shows from it, what it must log |
| `docs/ARCHITECTURE.md` | Hexagonal layout, ports and adapters, phases and their done criteria |
| `docs/DESIGN.md` | The design system and the anti-slop rules the mockups follow |
| `docs/TEAM_DEPENDENCIES.md` | Changes the team (brain) must make for some features |
| `docs/PLAN.md`, `docs/RUNNING.md` | Phase 0 and 1 plan; how to run and check it on the Mac |
| `cockpit.py`, `cockpit/`, `page/`, `config/` | The cockpit: entry point, core and adapters by feature, the page, thresholds and prices |
| `.cockpit.json` | the project's project config (paths, team, port), merged over `~/.config/cockpit/config.json` and checked at start (`docs/RUNNING.md`) |
| `tools/install_project.py`, `.claude/skills/cockpit-setup/` | Adapt the cockpit to another project: its `.cockpit.json`, then the status line and pause guard wrapped into its `.claude/settings.json`, with a backup and an uninstall |
| `tests/` | `python3 -m unittest discover -s tests -t .` |
| `fixtures/` | Real-format samples: panel.json, dod.json, goal.json, stack.json, beads, a transcript |

Some docs mention `research/`, `reference/`, `design/` and design-history docs. Those hold one team's own data and are not part of this repo.
