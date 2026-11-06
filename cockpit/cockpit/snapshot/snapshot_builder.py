import time
from typing import Dict, List, Optional, Tuple

from cockpit.asks.asks_view import answered_today, asks_view, owner_beads_without_ask, waiting_blockers
from cockpit.autopilot.keep_warm import KEEP_WARM
from cockpit.autopilot.rules import HAIKU, SPOT
from cockpit.autopilot.task_start import TASK_START
from cockpit.autopilot.window_step import canonical_model
from cockpit.board.bead_card import bead_card
from cockpit.classifier.shadow import suggestions
from cockpit.snapshot.outcome_lights import good_use_light, outcomes_light
from cockpit.snapshot.rewrites_light import rewrites_light
from cockpit.snapshot.hook_output_light import hook_output_light
from cockpit.snapshot.engram_light import RULE as ENGRAM_RULE, SOURCE as ENGRAM_SOURCE, engram_light
from cockpit.snapshot.mac_light import RULE as MAC_RULE, SOURCE as MAC_SOURCE, mac_light
from cockpit.snapshot.docs_age import RULE as DOCS_RULE, SOURCE as DOCS_SOURCE, WINDOW_DAYS, docs_light, stale_docs
from cockpit.classifier.verdict_state import world_of
from cockpit.compaction.price_table import PriceTable
from cockpit.compaction.recovery_book import RecoveryBook
from cockpit.compaction.recovery_by_role import recovery_by_role
from cockpit.controls.controls import Controls
from cockpit.controls.permission import EFFORTS, clear_permission
from cockpit.display_time import age, clock_seconds, clock_time, day, when
from cockpit.milestone.criteria import Criteria
from cockpit.milestone.milestone_view import milestone_view
from cockpit.milestone.stuck import stuck_beads
from cockpit.milestone.tree import BeadTree
from cockpit.needs.needs_context import NeedsContext
from cockpit.needs.rules import needs_for
from cockpit.sessions.session_row import session_row
from cockpit.sessions.session_plugins import enabled_plugins, hook_plugins, settings_flag
from cockpit.sessions.working_on import working_on
from cockpit.sessions.live_by_role import live_by_role
from cockpit.snapshot.accounts_section import accounts_section, balancer_rows
from cockpit.config_guard.config_drift import config_drift
from cockpit.token_tools.token_tool_lights import token_tool_lights
from cockpit.snapshot.health_lights import coordination_light, disk_light, memory_light, said_light
from cockpit.snapshot.lights import context_light, light, main_light, tokens_light
from cockpit.saved.said_vs_saved import said_vs_saved
from cockpit.sessions.start_limit import start_limit
from cockpit.snapshot.ports import Ports
from cockpit.snapshot.source_reads import SourceReads, source_line
from cockpit.snapshot.status_lines import clear_lines, handled_lines
from cockpit.hooks.hooks_view import hooks_view
from cockpit.jobs.jobs_section import self_compacted
from cockpit.pause.pause_view import pause_view
from cockpit.process.process_line import process_line
from cockpit.process.receipts import receipt_breaks
from cockpit.source_unavailable import SourceUnavailable
from cockpit import team as team_names
from cockpit.team import Team, session_name
from cockpit.tokens.hold_bands import hold_bands
from cockpit.tokens.landed_beads import landed_beads
from cockpit.tokens.tokens_section import tokens_section
from cockpit.transcripts.history import History
from cockpit.thresholds import Thresholds

AUTOPILOT_RULES = [  # the conditions themselves are in cockpit/autopilot/rules.py
    {"name": SPOT, "label": "Sweet spot compaction", "threshold": "cache_expiry_margin_minutes", "short": "Compacts an idle session over its sweet spot",
     "when": "With no TASK coming, {value} m before its cache expires, and its notes are saved or it holds no bead in progress"},
    {"name": HAIKU, "label": "Haiku under 100k", "threshold": "haiku_guard_pct", "short": "Compacts a Haiku session before it reaches 100k",
     "when": "When it is idle at {value}% of 100k or more, so no turn runs at 5 times the price"},
    {"name": KEEP_WARM, "label": "Keep-warm probe", "threshold": "probe_max_spot_multiple", "switch": "keep_warm_probe_on",
     "short": "Types one short prompt into an idle session so its cache does not expire",
     "when": "Near its cache's expiry, at or under {value}x its sweet spot, up to the count where probes cost what a rewrite or a compaction would, when Jev expects it to wake"},
]
HISTORY_DAYS = 14  # two weeks: this week against last week, and the Jev record's outcomes


def week_starts(now: float) -> list:
    """Local midnights of the last 7 days, oldest first; mktime normalises the day before the 1st of a month."""
    local = time.localtime(now)
    return [time.mktime((local.tm_year, local.tm_mon, local.tm_mday - back, 0, 0, 0, 0, 0, -1)) for back in range(6, -1, -1)]


def day_starts(now: float):
    local = time.localtime(now)
    today = time.mktime((local.tm_year, local.tm_mon, local.tm_mday, 0, 0, 0, 0, 0, -1))
    return today - 86400, today, now



class SnapshotBuilder:
    """Reads every port once per cycle and assembles the view model. Every number carries its source and
    age, and a source that fails is named with its error instead of showing as zero."""

    def __init__(self, ports: Ports, team: Team, thresholds: Thresholds, prices: PriceTable, budget_s: float,
                 hook_logs: Optional[dict] = None, docs_skipped: Optional[List[str]] = None,
                 decision_log: str = "docs/DECISIONS.md"):
        self.ports = ports
        self.prices = prices
        self.team = team
        self.thresholds = thresholds
        self.reads = SourceReads(budget_s)
        self.tree: Optional[BeadTree] = None  # the last board read, so a bead opens without another bd call
        self.hook_logs = hook_logs or {}
        self.docs_skipped = list(docs_skipped or [])
        self.decision_log = decision_log
        self.docs_read: tuple = (0.0, None)  # (when, stale docs): git log and the docs are read once an hour
        self.wrongs: Dict[str, list] = {}
        self.week: Dict[str, dict] = {}
        self.samples: dict = {}
        self.quota_per_task: Dict[str, float] = {}
        self.history: Optional[History] = None
        self.history_start = 0.0
        self.recovery = RecoveryBook()  # Jev's category per bead, asked once
        self.to_classify: list = []

    def build(self, grill: Optional[dict] = None, controls: Optional[Controls] = None, arriving: Optional[Dict[str, str]] = None,
              wrongs: Optional[Dict[str, list]] = None, week: Optional[Dict[str, dict]] = None,
              quota_per_task: Optional[Dict[str, float]] = None) -> dict:
        """arriving: per session, the bead of the TASK it gets next, so Jev's bead verdict is about that bead. wrongs:
        per session, the owner's latest wrong clicks, which Jev sees (design Q4 G)."""
        self.wrongs = wrongs or {}
        self.week = week or {}
        self.quota_per_task = quota_per_task or {}  # 7 d points per finished task per account, the last read's (QuotaUse)  # the autopilot's decisions and their outcomes per session, 7 d (Autopilot.week_outcomes)
        p, now = self.ports, self.ports.clock.now()
        jobs = {"board": p.board.read, "asks": p.asks.read, "live": p.live_sessions.list, "accounts": p.accounts.list,
                "balancer": lambda: p.balancer_log.since(now - 86400), "gate": p.git.gate, "plan": p.team_plan.read,
                "tokens": lambda: p.transcripts.daily_tokens(day_starts(now)),
                "landed": lambda: p.git.commits_since(day_starts(now)[1]),
                "decisions": lambda: p.git.committed_text(self.decision_log),
                "pause": p.pause.since,
                "guard": lambda: p.saved_guard.since(day_starts(now)[1]),
                "disk": p.disk.read,
                "hooks": lambda: hooks_view(p.hooks, self.hook_logs, day_starts(now)[1], now),
                "history": lambda: p.transcripts.daily_totals(week_starts(now), now),
                "config": p.config_files.read, "docs": lambda: self.stale_docs(now),
                "engram": p.engram.read if p.engram else lambda: None,
                "mac": p.mac.read if p.mac else lambda: None,
                "token_tools": lambda: p.token_tools.read(time.strftime("%Y-%m-%d", time.localtime(now)))}
        got = self.reads.read(jobs)
        live = value(got, "live") or []
        names = {s.session_id: s.name for s in live}
        stats = self.reads.read({"transcripts": lambda: p.transcripts.stats([s.session_id for s in live], now),
                                 "past": lambda: p.transcripts.history(now - HISTORY_DAYS * 86400, now, names)})
        got.update(stats)
        snapshot = self.assemble(got, live, now, grill, arriving or {})
        snapshot["actions"] = controls.effects(snapshot["sessions"], value(got, "transcripts") or {}, now) if controls else []
        return snapshot

    def assemble(self, got: dict, live, now: float, grill: Optional[dict], arriving: Optional[Dict[str, str]] = None) -> dict:
        board, asks = value(got, "board"), value(got, "asks")
        board_absent, milestone_used = got["board"].get("absent", False), bool(board and board.milestone_used)
        open_asks = asks.open if asks else []
        tree = BeadTree(board.beads) if board else None
        self.tree = tree or self.tree
        milestone = tree.current_milestone() if tree and milestone_used else None
        criteria = Criteria(tree, milestone, board.dod, open_asks) if milestone else None
        stats_by_id = value(got, "transcripts") or {}
        plan = value(got, "plan") or {}
        past = value(got, "past")
        if past is not None:
            self.history, self.history_start = past, now - HISTORY_DAYS * 86400
        rows = self.session_rows(live, stats_by_id, tree, criteria, plan, now, "" if board_absent else "board unavailable")
        for row in rows:
            row["can_clear"], row["clear_why"] = clear_permission(row)
            row["auto_compact_window"] = self.saved_window(row)
            row["plugins"], row["plugins_error"] = self.plugins_of(row)
            row["hook_plugins"] = hook_plugins(row["start_modes"], row["plugins"])
        # The owner, 2026-10-16: while the team is off, nothing that costs runs, so Jev is not asked.
        paused = value(got, "pause") is not None
        yes = self.thresholds.value("jev_yes_probability")
        world = world_of(rows, tree, board, plan, self.team.coordinating, stats_by_id, value(got, "accounts") or [],
                         self.wrongs, self.quota_per_task)
        got.update(self.reads.read({"classifier": (lambda: {}) if paused else lambda: suggestions(rows, tree, self.ports.classifier, yes, world, now, arriving or {}),
                                    # Kinds learned now serve the next read's sweet spots; Jev costs, so not while paused.
                                    "task_kinds": (lambda: 0) if paused else
                                    lambda: self.recovery.learn(self.to_classify, self.ports.classifier, yes)}))
        for row in rows:
            row["suggested"] = (value(got, "classifier") or {}).get(row["name"])
        self.start_loads(rows, value(got, "past"))
        holder_turns = {self.team.session_name(r["name"]): r["last_turn_at"] for r in rows if r["last_turn_at"]}
        if tree and value(got, "pause") is None:  # a paused team is not stuck (design chat M13)
            mark_stuck(rows, tree, holder_turns, now, self.thresholds.value("silent_bead_hours"))
        raw_accounts = value(got, "accounts") or []
        accounts = accounts_section(raw_accounts, rows, self.thresholds, now)
        pick = next_pick(value(got, "balancer") or [])
        named = {r["name"]: stats_by_id[r["session_id"]] for r in rows if r["session_id"] in stats_by_id}
        self.samples = {"turn_gaps": [g for s in named.values() for g in s.turn_gaps]}  # for the daily re-fit (cockpit/refit)
        mentions = {name: {"beads": st.mentioned_beads, "asks": st.mentioned_asks, "commits": st.mentioned_commits,
                           "saved": st.saved_without_id, "evidence": st.evidence} for name, st in named.items()}
        shas = set().union(*(m["commits"] for m in mentions.values())) if mentions else set()
        got.update(self.reads.read({"commits": lambda: self.ports.git.known_commits(shas)}))
        asks_read = value(got, "asks")
        known_asks = {a.get("id") for a in (asks_read.open + asks_read.answered)} if asks_read else set()
        stuck = stuck_beads(tree.by_id.values(), holder_turns, now, self.thresholds.value("silent_bead_hours")) if tree else {}
        needs = needs_for(NeedsContext(rows=rows, tree=tree, criteria=criteria, open_asks=open_asks, mentions=mentions,
                                       team=self.team, thresholds=self.thresholds, now=now, accounts=raw_accounts, next_pick=pick,
                                       known_asks=known_asks, known_commits=value(got, "commits"), gate=value(got, "gate"), stuck=stuck,
                                       receipt_breaks=receipt_breaks(value(got, "past").messages, now) if value(got, "past") else [],
                                       **self.guard(value(got, "config"), named, now)))
        milestone = (milestone_view(board, open_asks, self.team, self.thresholds, now, holder_turns,
                                    {r["name"]: r["state"] for r in rows}) if milestone_used
                     else {"available": False, "absent": True} if board or board_absent
                     else {"available": False, "error": got["board"]["error"]})
        asks_section = self.asks_section(got, tree, criteria, open_asks, now, grill)
        need_dicts = [n.__dict__ for n in needs]
        # A blocker question lights Your tasks at once: the session that asked waits for it (panel 4c9041).
        asks_section["blockers"] = len(waiting_blockers(open_asks, self.thresholds.value("blocker_ask_hours"), now))
        tokens = self.tokens_section(rows, got, tree, now)
        past = value(got, "past")
        process = process_line(past.messages, {b.id for b in tree.by_id.values() if b.is_open} if tree else set(),
                               self.thresholds.value("duplicate_window_minutes") * 60, now) if past else None
        saved = said_vs_saved(asks_section.get("log") or [], value(got, "decisions"),
                              [{"id": b.id, "title": b.title, "by": b.assignee} for b in tree.by_id.values()
                               if b.created_at and b.created_at >= day_starts(now)[1]] if tree else [],
                              value(got, "landed"),
                              {name: {"saved": st.saved_without_id, "places": st.saved_places} for name, st in named.items()},
                              {k: got[k].get("error", "") for k in ("decisions", "landed")}, value(got, "guard"))
        for row in rows:
            if row["name"] == team_names.LEAD:  # the lead carries the owner's answers into the decision log
                row["unsaved_answers"] = [a["id"] for a in saved["not_in_decisions"]]
        # Team health (the owner, 2026-10-16): the team's resources, one row each; what needs the owner is in Your tasks.
        health = [tokens_light(value(got, "tokens"), tokens), context_light(rows), memory_light(rows), said_light(saved, need_dicts),
                  disk_light(value(got, "disk"), self.thresholds.value("disk_min_free_gb"), self.thresholds.value("disk_watch_free_gb"),
                             got["disk"].get("error", "")),
                  coordination_light(process, need_dicts), main_light(value(got, "gate"))] + token_tool_lights(value(got, "token_tools"), named, rows) \
            + [outcomes_light(named, self.week, self.history, now), good_use_light(rows, named, now), rewrites_light(named), hook_output_light(named)] \
            + ([docs_light(value(got, "docs"), self.thresholds.value("doc_lag_days"))] if value(got, "docs") is not None else
               [light("docs_age", "Docs against code", "unknown", "unknown", "", got["docs"].get("error", "not read yet"), DOCS_RULE, DOCS_SOURCE)]) \
            + ([] if not self.ports.engram else [engram_light(value(got, "engram"), rows)] if value(got, "engram") is not None else
               [light("engram", "Engram", "unknown", "unknown", "", got["engram"].get("error", "not read yet"), ENGRAM_RULE, ENGRAM_SOURCE)]) \
            + ([] if not self.ports.mac else [mac_light(value(got, "mac"), rows, self.thresholds.value("mac_watch_free_pct"),
                                                        self.thresholds.value("mac_act_free_pct"))] if value(got, "mac") is not None else
               [light("mac", "Mac", "unknown", "unknown", "", got["mac"].get("error", "not read yet"), MAC_RULE, MAC_SOURCE)])
        return {
            "health": health,
            "read_at": now, "read_clock": clock_time(now), "read_seconds": clock_seconds(now), "refresh_s": self.thresholds.value("refresh_seconds"),
            "sources": {name: source_line(r) for name, r in got.items()},
            "needs": need_dicts,
            "handled": handled_lines(accounts, raw_accounts, rows, pick, bool(self.thresholds.value("autopilot_on"))),
            "clear": clear_lines(value(got, "gate"), value(got, "tokens"), process),
            "milestone": milestone,
            "sessions": rows, "efforts": list(EFFORTS), "self_compacted": self_compacted(named, day_starts(now)[1]),
            "tokens": tokens,
            "process": process,
            "price_mark": self.prices.stale_mark(now, self.thresholds.value("price_max_age_days")),
            "asks": asks_section,
            "hooks": value(got, "hooks") or [], "hooks_error": got["hooks"].get("error", ""),
            "pause": pause_view(value(got, "pause"), value(got, "landed"), tree.by_id.values() if tree else [], now),
            "saved": saved,
            "accounts": accounts, "accounts_error": got["accounts"].get("error", ""),
            "balancer": balancer_rows(value(got, "balancer") or [], now), "balancer_error": got["balancer"].get("error", ""),
            "autopilot": [{"name": r["name"], "label": r["label"], "short": r["short"], "when": self.rule_when(r)} for r in AUTOPILOT_RULES],
            "thresholds": {k: {"value": t.value, "status": t.status, "source": t.source} for k, t in self.thresholds.items.items()},
        }

    def stale_docs(self, now: float) -> List[dict]:
        when, found = self.docs_read
        if found is None or now - when >= 3600:
            changes = self.ports.git.path_changes(WINDOW_DAYS)
            found = stale_docs(self.ports.git.doc_texts(self.docs_skipped), changes, now - WINDOW_DAYS * 86400,
                               self.thresholds.value("doc_lag_days") * 86400)
            self.docs_read = (now, found)
        return found

    def rule_when(self, rule: dict) -> str:
        if "switch" in rule and not self.thresholds.value(rule["switch"]):
            return f"Off: {rule['switch']} is false in config/thresholds.json ({self.thresholds[rule['switch']].source})"
        return rule["when"].format(value=self.thresholds.value(rule["threshold"]))

    def start_loads(self, rows, past) -> None:
        """Each running session's start load against its role's usual (the owner, 2026-10-16)."""
        rise = self.thresholds.value("start_load_rise_pct")
        for row in rows:
            name = self.team.session_name(row["name"])
            others = [load for who, t, load in (past.starts if past else []) if who == name and t != row.get("started_at")]
            row["start_limit"] = start_limit(others, rise)
            row["start_over"] = bool(row["start_limit"] and row["start_load"] and row["start_load"] > row["start_limit"]["limit"])

    def tokens_section(self, rows, got, tree, now) -> dict:
        past = value(got, "past")
        section = tokens_section(rows, past, history_days(value(got, "history"), now), value(got, "tokens"), self.team,
                                 self.thresholds, now, self.prices)
        section["landed"] = landed_beads(tree.by_id.values(), past.requests, self.team,
                                         self.thresholds.value("tokens_per_bead_rise_pct"), now) if tree and past else []
        section["holds"] = hold_bands(past, self.thresholds.value("hold_band_min_reviews")) if past else None
        section["error"] = "" if past is not None else got["past"].get("error", "")
        return section

    def bead(self, bead_id: str) -> Optional[dict]:
        return bead_card(self.tree, bead_id) if self.tree else None

    def session_rows(self, live, stats_by_id, tree, criteria, plan, now, no_board_tag):
        beads = list(tree.by_id.values()) if tree else []
        fleet = list(stats_by_id.values())
        by_name = live_by_role(live, self.team.role_of)
        sessions = {role: (self.team.session_name(role), stats_by_id.get(by_name[role].session_id) if role in by_name else None)
                    for role in self.team.roles}
        recovery, self.to_classify = recovery_by_role(self.recovery, sessions, beads,
                                                      self.thresholds.value("recovery_min_compactions"), now)
        rows = []
        for role in self.team.roles:
            session = by_name.get(role)
            assignee = self.team.session_name(role)
            state = session.state if session else "off"
            work = working_on(role, assignee, beads, tree, criteria, role in self.team.coordinating, state) if tree else \
                {"bead": "", "tag": no_board_tag, "kind": "none", "line": "", "held": []}
            if session is None and not work["held"] and role not in (team_names.LEAD, team_names.COORDINATOR, "reviewer"):  # the team stops without these three, so one that is down stays on the board as off
                continue  # a role with no session and no bead in progress is no row (reviewer-2, cockpit, on-demand roles)
            held = [tree.by_id[i] for i in work["held"]] if tree else []
            stats = stats_by_id.get(session.session_id) if session else None
            # A role session holds no bead, so its memory is its state file (the owner, 2026-10-16).
            state_file = self.ports.role_memory.state_file(role, stats.cwd if stats else "") if work["kind"] == "role" else ""
            state_at = self.ports.role_memory.modified_at(stats.cwd, role) if state_file and stats else None
            # Every session that has a state file reads it again after a restart; MEMORY.md holds only its pointer (brain).
            memory_file = self.ports.role_memory.state_file(role, stats.cwd) \
                if stats and self.ports.role_memory.modified_at(stats.cwd, role) is not None else ""
            rows.append(session_row(role, session, stats, work, held, plan.get(role), fleet, self.thresholds, self.prices, now,
                                    state_file, state_at, recovery[role]["recovery"], recovery[role]["kind"],
                                    recovery[role]["source"], memory_file))
        return rows

    def saved_window(self, row: dict) -> Optional[int]:
        """What its account saved for its model: the first proof of the autopilot's window step; unread proves nothing."""
        if not row["account"] or not row["model_id"]:
            return None
        try:
            return self.ports.window_settings.window(row["account"], canonical_model(row["model_id"]))
        except SourceUnavailable:
            return None

    def plugins_of(self, row: dict) -> Tuple[List[str], str]:
        if row["state"] == "off" or not row["account"]:
            return [], ""
        try:
            layers = self.ports.window_settings.plugin_layers(row["account"], row.get("cwd") or "", settings_flag(row["flags"]))
        except SourceUnavailable as error:
            return [], str(error)
        return enabled_plugins(layers, row["flags"]), ""

    @staticmethod
    def guard(config: Optional[dict], named: dict, now: float) -> dict:
        drift = config_drift(config["baseline"], config["current"]) if config else []
        return {"config_drift": drift, "config_since": when(config["since"], now) if config else "",
                "tool_failures": [f"{name}: {tool}: {said}" for name, st in named.items() for _, tool, said in st.tool_failures]}

    def asks_section(self, got, tree, criteria, open_asks, now, grill):
        if not got["asks"]["ok"]:
            return {"available": False, "absent": got["asks"].get("absent", False), "error": got["asks"]["error"], "rows": [],
                    "grill": grill}
        waiting = owner_beads_without_ask(tree, criteria, open_asks) if tree else []
        view = asks_view(open_asks, waiting, now, f"{value(got, 'asks').source}, read {age(now - value(got, 'asks').read_at)} ago")
        view.update(available=True, grill=grill, log=answered_today(value(got, "asks").answered, day_starts(now)[1]))
        return view


def history_days(totals, now: float) -> list:
    if not totals:
        return []
    # Without the cache (fresh input and output, the owner 56fba6) first, and with it (all the model processed).
    return [{"day": day(start), "tokens": total, "no_cache": total - cached} for start, (total, cached) in zip(week_starts(now), totals)]


def mark_stuck(rows, tree, holder_turns, now, hours):
    """A mark, not a Needs you row (the owner, 2026-10-16: "(the owner\'s words)")."""
    stuck = stuck_beads(tree.by_id.values(), holder_turns, now, hours)
    for row in rows:
        mine = [(bead_id, h) for bead_id, h in stuck.items() if tree.by_id[bead_id].assignee == session_name(row['name'])]
        if mine:
            row["stuck"] = "stuck " + ", ".join(f"{bead_id} {h:.0f} h" for bead_id, h in mine)


def next_pick(decisions) -> str:
    """The balancer's last choice stands for its next one: it logs choices, not a forecast (BALANCER.md)."""
    latest = max(decisions, key=lambda d: d["t"], default=None)
    chosen = latest and (latest.get("chosen") or latest.get("account"))
    return str(chosen) if chosen is not None else ""


def value(got: dict, name: str):
    result = got.get(name) or {}
    return result.get("value") if result.get("ok") else None
