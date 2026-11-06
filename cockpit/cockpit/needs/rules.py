from dataclasses import replace
from typing import List

from cockpit.accounts.login import logins_by_use, why_login
from cockpit.display_time import age, clock_time, day_time
from cockpit.milestone.criteria import Criteria
from cockpit.milestone.team_rules import broken_team_rules
from cockpit.milestone.tree import short_name
from cockpit.needs.need import Need
from cockpit.needs.needs_context import NeedsContext
from cockpit.sessions.session_row import kilo

LEVEL_ORDER = {"warning": 0, "caution": 1}


def haiku_over_step(ctx: NeedsContext) -> List[Need]:
    step = ctx.thresholds.value("haiku_step_tokens")
    guard = step * ctx.thresholds.value("haiku_guard_pct") / 100
    stuck = [r for r in ctx.rows if r["haiku_over_step"] and r.get("base") and r["base"] >= guard]
    rows = [Need(f"haiku-base-{r['name']}", "warning",
                 f"{r['name']} cannot stay under {kilo(step)} on {r['model']}: it starts at {kilo(r['base'])} before any work, "
                 f"so compacting does not help.",
                 "transcript: first turn and last compaction · the autopilot stopped compacting it",
                 "See sessions", "jump", "sessions")
            for r in stuck]
    return rows + [Need(f"haiku-{r['name']}", "warning",
                 f"{r['name']} is at {kilo(r['context'])} on {r['model']}. Above {kilo(step)} every turn costs 5 times as much.",
                 f"transcript · {r['state']}{', idle ' + r['idle_for'] if r['idle_for'] else ''}",
                 f"Compact {r['name']}" if r["can_compact"] else "Wait: " + r["why"].split(".")[0].lower(),
                 "control" if r["can_compact"] else "none", "compact", r["name"])
            for r in ctx.rows if r["haiku_over_step"] and r not in stuck]


def off_milestone(ctx: NeedsContext) -> List[Need]:
    if not ctx.tree or not ctx.criteria:
        return []
    name = short_name(ctx.criteria.milestone)
    off = [b for b in ctx.tree.by_id.values() if b.status == "in_progress" and b.priority != 0
           and not ctx.tree.is_under(b, ctx.criteria.milestone.id)]
    by_holder = {}
    for bead in off:
        by_holder.setdefault(bead.assignee or "nobody", []).append(bead)
    needs = []
    for holder, beads in sorted(by_holder.items()):
        listed = ", ".join(f"{b.id} ({short_name(ctx.tree.milestone_of(b))}, P{b.priority})" for b in beads)
        prompt = (f"coordinator: {holder} holds {listed} in progress while {name} is open. By DECISIONS 2026-10-13 only P0 "
                  f"runs outside the milestone. Please set {'it' if len(beads) == 1 else 'them'} back to open, or tell me why now.")
        needs.append(Need(f"off-{holder}", "warning",
                          f"{holder} works on {len(beads)} bead{'s' if len(beads) > 1 else ''} outside {name}: {listed}.",
                          f"bd: in progress, not under {ctx.criteria.milestone.id} · only P0 may run outside the milestone",
                          "Tell the coordinator", "copy", prompt, "coordinator"))
    return needs


def owner_criterion_without_ask(ctx: NeedsContext) -> List[Need]:
    if not ctx.criteria:
        return []
    waiting = [b for b in ctx.criteria.open() if Criteria.waits_on_owner(b) and not ctx.criteria.asks_for(b)]
    if not waiting:
        return []
    ids = ", ".join(b.id for b in waiting)
    return [Need("ask-criteria", "caution",
                 f"{short_name(ctx.criteria.milestone)} done criteri{'a' if len(waiting) > 1 else 'on'} {ids} wait{'' if len(waiting) > 1 else 's'} on you, "
                 f"and no ask on the panel says so.",
                 "bd · panel.json: no ask names it",
                 "Ask brain to add it", "copy",
                 f"brain: {ids} {'are open done criteria that wait' if len(waiting) > 1 else 'is an open done criterion that waits'} on me, "
                 f"and no ask on the panel names {'them' if len(waiting) > 1 else 'it'}. Please add one ask each with "
                 f"ask_owner.py add --bead <id>, with options, --rec and --why.", "brain")]


def with_line(label: str, kind: str, ident: str, evidence: list) -> str:
    """The id, and the line of the latest reply that named it, so the owner can tell a real gap from a false alarm."""
    lines = [e for e in evidence if e[1] == kind and e[2] == ident]
    if not lines:
        return label
    at, _, _, line = max(lines, key=lambda e: e[0])
    return f'{label} ("{line}", {clock_time(at)})'


def known_bead(bead: str, tree) -> bool:
    """bd holds only mb- beads now; pg-<bead>-vN.patch is a patch file's name, so a pg- name is its mb- bead."""
    return bead in tree.by_id or (bead.startswith("pg-") and "mb-" + bead[len("pg-"):] in tree.by_id)


def missing_id(ctx: NeedsContext) -> List[Need]:
    """BRIEF: if it has no id it does not exist. Bead ids against bd, "ask <6 hex>" against panel.json, "commit <sha>"
    against git: one row per session. A reply that says saved or recorded with no id at all is another row, so the
    Said vs saved light can tell the two apart. Each row quotes the reply line it came from."""
    if not ctx.tree:
        return []
    needs = []
    for session, named in sorted(ctx.mentions.items()):
        evidence = named.get("evidence", [])
        unknown = [with_line(b, "bead", b, evidence) for b in sorted(b for b in named["beads"] if not known_bead(b, ctx.tree))]
        unknown += [with_line(f"ask {a}", "ask", a, evidence) for a in sorted(named["asks"] - ctx.known_asks)]
        if ctx.known_commits is not None:
            unknown += [with_line(f"commit {c}", "commit", c, evidence) for c in sorted(named["commits"] - ctx.known_commits)]
        if unknown:
            text = f"{session} named {', '.join(unknown)} in a reply today, and none exists"
            needs.append(Need(f"missing-{session}", "caution", text + ".", "transcript replies of the last 24 h · bd export, panel.json, git cat-file",
                              "Ask brain to check it", "copy",
                              f"brain: {text}. Please open what is missing (bead, ask or commit) or correct the reference.", "brain"))
        saved = named["saved"]
        if saved:
            claim = with_line(f"said saved or recorded {saved} time{'s' if saved > 1 else ''} with no id", "saved", "", evidence)
            needs.append(Need(f"unsaved-{session}", "caution", f"{session} {claim}.", "transcript replies of the last 24 h",
                              "Ask brain to check it", "copy", f"brain: {session} {claim}. Please have it name the id of what it saved.", "brain"))
    return needs


def receipts(ctx: NeedsContext) -> List[Need]:
    if not ctx.receipt_breaks:
        return []
    listed = "; ".join(ctx.receipt_breaks[:5]) + (f"; and {len(ctx.receipt_breaks) - 5} more" if len(ctx.receipt_breaks) > 5 else "")
    return [Need("receipts", "warning", f"Review receipts do not match: {listed}.",
                 "messages between sessions this week · sha256 of each GO-REQ, GO, HOLD and LAND-READY (the project's WORKFLOW)",
                 "Tell the coordinator", "copy",
                 f"coordinator: review receipts do not match this week: {listed}. Please bounce each one, or tell me why it is right.",
                 "coordinator")]


def main_red(ctx: NeedsContext) -> List[Need]:
    """The commit that failed and how many tests, which the Main light alone cannot say (review finding 2026-10-16)."""
    gate = ctx.gate
    if gate is None or gate.green is not False:
        return []
    return [Need("main-red", "warning",
                 f"Main is red: the gate on {gate.commit} failed with {gate.failing} failing test{'' if gate.failing == 1 else 's'}.",
                 f"verify_commit.sh log · {gate.source}", "Tell brain", "copy",
                 f"brain: the gate on {gate.commit} is red with {gate.failing} failing tests ({gate.source}). Please fix main "
                 f"before anything else lands, or tell me why not.", "brain")]


def team_rules_broken(ctx: NeedsContext) -> List[Need]:
    """One row, only when a rule breaks (the owner, 2026-10-16: "Team rules broken: ... [Tell brain]")."""
    broken = broken_team_rules(ctx.tree, ctx.criteria, ctx.team, ctx.thresholds, ctx.stuck) if ctx.criteria else []
    if not broken:
        return []
    listed = "; ".join(broken)
    return [Need("team-rules", "caution", f"Team rules broken: {listed}.",
                 "bd · .cockpit.json team · found work links the criterion it moves, one bead per task session, "
                 "every holder a team session", "Tell brain", "copy",
                 f"brain: team rules are broken on the board: {listed}. Please fix them, or tell me why not.", "brain")]


BASELINE = "~/.cockpit/config-baseline.json"


def token_tool_guard(ctx: NeedsContext) -> List[Need]:
    """The autopilot's guard for the token tools (the owner, ask 8ccee2: "por si daña la config de alguna agente"): a tool
    line added or removed in a settings or .mcp.json file, or a tool hook that crashed. The cockpit never edits them."""
    needs = []
    if ctx.config_drift:
        diff = "; ".join(f"{c['path']}: " + ", ".join([f"+ {l}" for l in c["added"]] + [f"- {l}" for l in c["removed"]])
                         for c in ctx.config_drift)
        tools = ", ".join(sorted({t for c in ctx.config_drift for t in c["tools"]}))
        needs.append(Need("token-tool-config", "warning", f"Token tool config changed since {ctx.config_since} ({tools}): {diff}.",
                          f"settings files and .mcp.json against {BASELINE}; to accept the change, delete that file", "Tell brain", "copy",
                          f"brain: the token tool config changed since {ctx.config_since}: {diff}. Check no session lost a hook or its "
                          f"settings; put back what broke, or tell me it is fine and delete {BASELINE} so the cockpit takes the new "
                          f"config as its baseline.", "brain"))
    if ctx.tool_failures:
        listed = "; ".join(ctx.tool_failures)
        needs.append(Need("token-tool-broken", "caution", f"A token tool hook failed in 24 h: {listed}.",
                          "transcripts (hook errors and timeouts)", "Tell brain", "copy",
                          f"brain: these token tool hooks crashed or timed out in 24 h: {listed}. Find why and fix it, or tell me "
                          f"why not.", "brain"))
    return needs


def account_login(ctx: NeedsContext) -> List[Need]:
    live = [r["account"] for r in ctx.rows if r["state"] != "off" and r["account"]]
    in_use, _ = logins_by_use(ctx.accounts, live, ctx.next_pick)
    needs = []
    for account in in_use:
        on_it = [r["name"] for r in ctx.rows if r["account"] == account.number and r["state"] != "off"]
        users = (", ".join(on_it) + (" run" if len(on_it) > 1 else " runs") + " on it") if on_it else "the balancer picked it last"
        text = f"Account {account.number} needs your login ({why_login(account)}); {users}."
        source = f"cswap list --json · usageStatus {account.usage_status or 'unknown'}{', disabled' if account.disabled else ''}"
        if account.active:
            # Logged in on ~/.claude itself: a re-login there touches every session's default login, so brain does it.
            needs.append(Need(f"login-{account.number}", "warning", text, source + " · active: logged in on ~/.claude",
                              "Tell brain", "copy",
                              f"brain: account {account.number} needs a new login ({why_login(account)}) and it is the one logged in "
                              f"on ~/.claude. Please re-login it there and tell me when it is back.", "brain"))
        else:
            needs.append(Need(f"login-{account.number}", "warning", text, source, f"Copy cswap-relogin {account.number}", "copy",
                              f"cswap-relogin {account.number}"))
    return needs


# A stuck bead is a mark in the milestone and sessions, and a blocker ask lives only in Your asks: Needs you holds
# only actions (the owner, 2026-10-16).
RULES = [main_red, receipts, haiku_over_step, off_milestone, owner_criterion_without_ask, missing_id, team_rules_broken,
         token_tool_guard, account_login]


def needs_for(ctx: NeedsContext) -> List[Need]:
    found = [sent_to_its_session(need, ctx) for rule in RULES for need in rule(ctx)]
    return sorted(found, key=lambda n: LEVEL_ORDER[n.level])


def sent_to_its_session(need: Need, ctx: NeedsContext) -> Need:
    """A prompt for a team session is typed into its pane on the owner's click; a command for a terminal stays a copy."""
    if need.action_kind == "copy" and need.target in ctx.team.roles:
        return replace(need, action_kind="send")
    return need
