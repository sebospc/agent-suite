import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from cockpit.accounts.balancer_log_file import BalancerLogFile
from cockpit.accounts.cswap_accounts import CswapAccounts
from cockpit.asks.panel_file_asks import PanelFileAsks
from cockpit.board.bd_board import BdBoard
from cockpit.milestone.milestone_plan_files import MilestonePlanFiles
from cockpit.git.git_cli import GitCli
from cockpit.live_sessions.cswap_herdr_sessions import CswapHerdrSessions
from cockpit.snapshot.lights import main_light
from cockpit.source_unavailable import SourceUnavailable
from cockpit.team_plan.team_plan_file import TeamPlanFile
from tests.builders import FIXTURES, NOW


def script(folder, name, body):
    """A stand-in executable (bd, herdr, cswap, ask_owner.py) so the real adapters run their real code."""
    path = os.path.join(folder, name)
    with open(path, "w") as handle:
        handle.write("import sys, json\n" + body)
    return [sys.executable, path]


def no_ps(folder):
    """ps that shows no environment, as in a sandbox: the profile folder decides."""
    return script(folder, "ps_none.py", "print('PID COMMAND')")


class AdapterTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder)

    def test_bd_board_reads_the_export_and_the_board_files(self):
        for name in ("dod.json", "goal.json"):
            shutil.copy(os.path.join(FIXTURES, name), self.folder)
        bd = script(self.folder, "bd.py", f"sys.stdout.write(open({os.path.join(FIXTURES, 'beads.sample.jsonl')!r}).read())")
        state = BdBoard(self.folder, bd, 5, lambda: NOW, MilestonePlanFiles(self.folder)).read()
        self.assertEqual(15, len(state.beads))
        self.assertEqual(2, state.goal["value"])

    def test_a_locked_board_times_out_as_unavailable(self):
        bd = script(self.folder, "bd.py", "import time; time.sleep(5)")
        with self.assertRaises(SourceUnavailable):
            BdBoard(self.folder, bd, 0.5, lambda: NOW, MilestonePlanFiles(self.folder)).read()

    def test_answer_goes_through_ask_owner_with_the_owners_words(self):
        record = os.path.join(self.folder, "calls.json")
        ask_owner = script(self.folder, "ask_owner.py", f"json.dump(sys.argv[1:], open({record!r}, 'w')); print('answered')")
        shutil.copy(os.path.join(FIXTURES, "panel.json"), self.folder)
        asks = PanelFileAsks(os.path.join(self.folder, "panel.json"), ask_owner, 5, lambda: NOW)
        self.assertEqual(["696253"], [a["id"] for a in asks.read().open])
        self.assertEqual("answered", asks.answer("696253", "Approve this coverage"))
        with open(record) as handle:
            self.assertEqual(["answer", "696253", "Approve this coverage"], json.load(handle))

    def test_a_failed_answer_is_reported(self):
        ask_owner = script(self.folder, "ask_owner.py", "sys.exit('no such ask')")
        with self.assertRaises(SourceUnavailable):
            PanelFileAsks("unused", ask_owner, 5, lambda: NOW).answer("x", "y")

    def test_live_sessions_join_records_with_herdr_panes(self):
        sessions = os.path.join(self.folder, "profiles", "15-someone@example.com", "sessions")
        os.makedirs(sessions)
        with open(os.path.join(sessions, f"{os.getpid()}.json"), "w") as handle:
            json.dump({"pid": os.getpid(), "sessionId": "s1", "name": "agent-ios"}, handle)
        with open(os.path.join(sessions, "999999999.json"), "w") as handle:
            json.dump({"pid": 999999999, "sessionId": "dead"}, handle)
        panes = {"result": {"panes": [{"pane_id": "w1:p2", "agent_status": "working", "agent_session": {"value": "s1"}}]}}
        herdr = script(self.folder, "herdr.py", f"print(json.dumps({panes!r}))")
        found = CswapHerdrSessions(os.path.join(self.folder, "profiles"), os.path.join(self.folder, "none"), herdr, 5, no_ps(self.folder)).list()
        self.assertEqual([("agent-ios", "s1", "w1:p2", "15", "busy")],
                         [(s.name, s.session_id, s.pane, s.account, s.state) for s in found])

    def test_a_side_project_session_is_named_by_its_working_folder(self):
        sessions = os.path.join(self.folder, "profiles", "3-someone@example.com", "sessions")
        os.makedirs(sessions)
        project = os.path.join(self.folder, "agent-ddp")
        os.makedirs(project)
        with open(os.path.join(sessions, f"{os.getpid()}.json"), "w") as handle:
            json.dump({"pid": os.getpid(), "sessionId": "s1", "name": "agent-ddp-a4", "nameSource": "derived", "cwd": project}, handle)
        herdr = script(self.folder, "herdr.py", 'print(json.dumps({"result": {"panes": []}}))')
        none = os.path.join(self.folder, "none")
        named = CswapHerdrSessions(os.path.join(self.folder, "profiles"), none, herdr, 5, no_ps(self.folder), {project: "agent-agent-ddp"})
        plain = CswapHerdrSessions(os.path.join(self.folder, "profiles"), none, herdr, 5, no_ps(self.folder))
        self.assertEqual(["agent-agent-ddp"], [s.name for s in named.list()])
        self.assertEqual(["agent-ddp-a4"], [s.name for s in plain.list()])

    def test_live_flags_are_the_herdr_argv_of_the_sessions_process_without_its_id_or_prompt(self):
        sessions = os.path.join(self.folder, "profiles", "15-someone@example.com", "sessions")
        os.makedirs(sessions)
        with open(os.path.join(sessions, f"{os.getpid()}.json"), "w") as handle:
            json.dump({"pid": os.getpid(), "sessionId": "s1", "name": "agent-coordinator", "startedAt": 1792359874500}, handle)
        panes = {"result": {"panes": [{"pane_id": "w4:p1S", "agent_status": "idle", "agent_session": {"value": "s1"}}]}}
        info = {"result": {"process_info": {"foreground_processes": [{"pid": os.getpid(), "argv": [
            "claude", "--name", "agent-coordinator", "--model", "claude-haiku-5-5", "--resume", "s1", "continue"]}]}}}
        herdr = script(self.folder, "herdr.py", f"print(json.dumps({info!r} if 'process-info' in sys.argv else {panes!r}))")
        found = CswapHerdrSessions(os.path.join(self.folder, "profiles"), os.path.join(self.folder, "none"), herdr, 5, no_ps(self.folder)).list()
        self.assertEqual([(("--name", "agent-coordinator", "--model", "claude-haiku-5-5"), True)], [(s.flags, s.flags_known) for s in found])
        self.assertEqual([1792359874.5], [s.started_at for s in found])

    def test_a_session_is_busy_when_its_pane_or_its_record_says_busy(self):
        sessions = os.path.join(self.folder, "profiles", "1-someone@example.com", "sessions")
        os.makedirs(sessions)
        with open(os.path.join(sessions, f"{os.getpid()}.json"), "w") as handle:
            json.dump({"pid": os.getpid(), "sessionId": "s1", "name": "agent-brain", "status": "busy"}, handle)
        panes = {"result": {"panes": [{"pane_id": "w4:p3", "agent_status": "idle", "agent_session": {"value": "s1"}}]}}
        herdr = script(self.folder, "herdr.py", f"print(json.dumps({panes!r}))")
        found = CswapHerdrSessions(os.path.join(self.folder, "profiles"), os.path.join(self.folder, "none"), herdr, 5, no_ps(self.folder)).list()
        self.assertEqual(["busy"], [s.state for s in found])

    def test_the_account_is_the_processes_config_dir_not_the_shared_sessions_folder(self):
        shared = os.path.join(self.folder, "shared")
        os.makedirs(shared)
        with open(os.path.join(shared, f"{os.getpid()}.json"), "w") as handle:
            json.dump({"pid": os.getpid(), "sessionId": "s1", "name": "agent-ai"}, handle)
        for profile in ("1-a@example.com", "12-b@example.com.lock", "3-c@example.com"):
            os.makedirs(os.path.join(self.folder, "profiles", profile))
            os.symlink(shared, os.path.join(self.folder, "profiles", profile, "sessions"))
        herdr = script(self.folder, "herdr.py", "print(json.dumps({'result': {'panes': []}}))")
        ps = script(self.folder, "ps.py", "print('claude --name agent-ai HOME=/u CLAUDE_CONFIG_DIR=/u/profiles/3-c@example.com SECRET=x')")
        found = CswapHerdrSessions(os.path.join(self.folder, "profiles"), shared, herdr, 5, ps).list()
        self.assertEqual([("s1", "3")], [(s.session_id, s.account) for s in found])  # once, not once per profile
        default = script(self.folder, "ps_default.py", "print('claude HOME=/u')")
        self.assertEqual(["default"], [s.account for s in CswapHerdrSessions(os.path.join(self.folder, "profiles"), shared, herdr, 5, default).list()])

    def test_cswap_accounts_keep_quota_and_drop_the_email(self):
        listed = [{"number": 15, "email": "someone@example.com", "usageAgeSeconds": 40, "usageStatus": "ok",
                   "usage": {"fiveHour": {"pct": 88, "resetsAt": "2026-10-16T05:10:00+00:00"}, "sevenDay": {"pct": 71}}}]
        cswap = script(self.folder, "cswap.py", f"print(json.dumps({listed!r}))")
        account = CswapAccounts(cswap, 5).list()[0]
        self.assertEqual(("15", 88.0, 71.0), (account.number, account.five_hour_pct, account.seven_day_pct))
        self.assertNotIn("example.com", repr(account))

    def test_gate_log_and_unpushed_commits(self):
        repo = os.path.join(self.folder, "repo")
        os.makedirs(repo)
        git = lambda *args: subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t"] + list(args), cwd=repo, check=True, capture_output=True)
        git("init", "-q", "-b", "main")
        git("commit", "-q", "--allow-empty", "-m", "one")
        logs = os.path.join(self.folder, "scratch")
        os.makedirs(logs)
        with open(os.path.join(logs, "gate_68d356e6.log"), "w") as handle:
            handle.write("== format\n== ios\nFailing tests:\nTestA\nTestB\n\n")
        gate = GitCli(repo, "main", lambda: logs, 5).gate()
        self.assertEqual(("68d356e6", False, 2), (gate.commit, gate.green, gate.failing))

    def test_without_a_gate_log_the_gate_comes_from_stack_json(self):
        repo, _ = self.make_repo("gated", "one")
        stack = os.path.join(self.folder, "stack.json")
        for gate, expected in (({"status": "green"}, (True, False)), ("C120 gate running", (None, True)),
                               ({"status": "red: 2 failing"}, (False, False))):
            with open(stack, "w") as handle:
                json.dump({"gate": gate, "commits": [{"c": "C1", "sha": "cad13f53"}]}, handle)
            found = GitCli(repo, "main", lambda: os.path.join(self.folder, "no-logs"), 5, None, stack).gate()
            self.assertEqual(expected + ("cad13f53",), (found.green, found.running, found.commit))
        with open(stack, "w") as handle:
            json.dump({"gate": {"status": ""}}, handle)
        with self.assertRaises(Exception):
            GitCli(repo, "main", lambda: "", 5, None, stack).gate()
        with open(stack, "w") as handle:
            json.dump({"gate": "", "commits": [], "pushed": "cad13f53850105520c2c4dab92cd31c7316323bb"}, handle)
        idle = GitCli(repo, "main", lambda: "", 5, None, stack).gate()
        self.assertEqual(("cad13f538501", False), (idle.commit, idle.in_flight))
        self.assertEqual(("nothing in flight", "ok"), (main_light(idle)["value"], main_light(idle)["level"]))

    def make_repo(self, name, message):
        repo = os.path.join(self.folder, name)
        os.makedirs(repo)
        git = lambda *args: subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t"] + list(args), cwd=repo, check=True, capture_output=True, text=True)
        git("init", "-q", "-b", "main")
        git("commit", "-q", "--allow-empty", "-m", message)
        return repo, git("rev-parse", "HEAD").stdout.strip()[:10]

    def test_a_sha_is_found_when_any_repo_has_it(self):
        first, in_first = self.make_repo("first", "app commit")
        second, in_second = self.make_repo("second", "cockpit commit")
        git = GitCli(first, "main", lambda: "", 5, [first, second])
        self.assertEqual({in_first, in_second}, git.known_commits({in_first, in_second, "0123456"}))
        self.assertEqual({in_second}, git.known_commits({in_second}))  # only in the second repo
        self.assertEqual(set(), GitCli(first, "main", lambda: "", 5).known_commits({in_second}))  # one repo: still missing there

    def test_a_repo_that_cannot_be_asked_makes_the_answer_unavailable_unless_every_sha_was_found(self):
        first, in_first = self.make_repo("first", "app commit")
        git = GitCli(first, "main", lambda: "", 5, [first, os.path.join(self.folder, "gone")])
        self.assertEqual({in_first}, git.known_commits({in_first}))
        with self.assertRaises(SourceUnavailable):
            git.known_commits({in_first, "0123456"})

    def test_files_that_do_not_exist_yet_are_unavailable_not_empty(self):
        with self.assertRaises(SourceUnavailable):
            BalancerLogFile(os.path.join(self.folder, "decisions.jsonl")).since(0)
        with self.assertRaises(SourceUnavailable):
            TeamPlanFile(os.path.join(self.folder, "team.json")).read()

    def test_team_json_roles_drop_the_prefix(self):
        path = os.path.join(self.folder, "team.json")
        with open(path, "w") as handle:
            json.dump({"sessions": {"agent-ios": {"model": "claude-opus-5-5", "effort": "medium"}}}, handle)
        self.assertEqual({"ios": {"model": "claude-opus-5-5", "effort": "medium"}}, TeamPlanFile(path).read())


if __name__ == "__main__":
    unittest.main()


class RealSampleTest(unittest.TestCase):
    """Redacted real outputs from the owner's Mac (fixtures/real, Oct 16)."""
    REAL = os.path.join(FIXTURES, "real")

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder)

    def test_cswap_without_a_login_shows_the_last_good_usage_with_its_age_and_status(self):
        cswap = script(self.folder, "cswap.py", f"sys.stdout.write(open({os.path.join(self.REAL, 'cswap-list.json')!r}).read())")
        first, second = CswapAccounts(cswap, 5).list()
        self.assertEqual(("1", 100.0, "no_credentials", 34911.0), (first.number, first.seven_day_pct, first.status, first.age_seconds))
        self.assertEqual(("disabled, relogin_required", 85.0), (second.status, second.five_hour_pct))

    def test_a_derived_session_name_gives_way_to_the_pane_label(self):
        with open(os.path.join(self.REAL, "session-pid.json")) as handle:
            record = json.load(handle)
        sessions = os.path.join(self.folder, "profiles", "1-user@example.com", "sessions")
        os.makedirs(sessions)
        record["pid"] = os.getpid()
        with open(os.path.join(sessions, f"{os.getpid()}.json"), "w") as handle:
            json.dump(record, handle)
        herdr = script(self.folder, "herdr.py", f"sys.stdout.write(open({os.path.join(self.REAL, 'herdr-pane-list.json')!r}).read())")
        found = CswapHerdrSessions(os.path.join(self.folder, "profiles"), os.path.join(self.folder, "none"), herdr, 5, no_ps(self.folder)).list()
        self.assertEqual([("old-brain", "w4:p3", "1", "busy")], [(s.name, s.pane, s.account, s.state) for s in found])

    def test_a_real_gate_log_without_a_result_line_is_unknown_not_red(self):
        logs = os.path.join(self.folder, "scratch")
        os.makedirs(logs)
        shutil.copy(os.path.join(self.REAL, "gate.log"), os.path.join(logs, "gate_B.log"))
        gate = GitCli(self.folder, "main", lambda: logs, 5).gate()
        self.assertEqual(("B", None, 0), (gate.commit, gate.green, gate.failing))
