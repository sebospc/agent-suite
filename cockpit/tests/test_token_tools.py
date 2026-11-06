import json
import os
import tempfile
import unittest

from tests.test_sessions import stats as Stats

from cockpit.config_guard.config_drift import config_drift
from cockpit.config_guard.json_config_files import watched_part
from cockpit.sessions.session_plugins import enabled_plugins

from cockpit.token_tools.local_token_tools import LocalTokenTools
from cockpit.token_tools.token_tool_lights import token_tool_lights
from cockpit.transcripts.session_stats import SessionStats
from cockpit.transcripts.transcript_file import TranscriptFile
from cockpit.transcripts.transcript_stats import re_reads


def stats(session_id, tools, tokens, closed, failures=()):
    return SessionStats(session_id=session_id, title="", model="", effort="", ttl_seconds=3600, context_now=None, floor=None,
                        last_turn_at=None, tokens_24h=tokens, growth=[], outputs=[200, 400], gaps=[], compactions=[],
                        haiku_over_step=0, token_tools=set(tools), tasks_closed=closed, tool_failures=list(failures))


def row(name, plugins=(), modes=()):
    return {"name": name, "plugins": list(plugins), "start_modes": list(modes)}


class TokenToolLightsTest(unittest.TestCase):
    def test_a_tool_whose_sessions_spend_more_per_finished_task_is_watched(self):
        named = {"cockpit": stats("s1", {"rtk", "context-mode"}, 900_000, 3), "ios": stats("s2", {"rtk"}, 400_000, 2)}
        lights = {l["id"]: l for l in token_tool_lights({"rtk": {"project": 12_000}, "ctx": {"s1": {"avoided": 80_000, "returned": 0}}}, named,
                                                    [row("cockpit"), row("ios")])}
        self.assertEqual(("12k saved today", "ok"), (lights["rtk"]["value"], lights["rtk"]["level"]))
        self.assertEqual(("~20k net (estimate)", "watch"), (lights["context-mode"]["value"], lights["context-mode"]["level"]))
        self.assertIn("On (cockpit): ~300k per finished task (3 closed)", lights["context-mode"]["why"])
        self.assertEqual("on in 0 of 2", lights["caveman"]["value"])

    def test_context_mode_net_is_the_pilots_kept_out_minus_its_hook_text_over_finished_sessions_too(self):
        named = {"cockpit": stats("s1", {"context-mode"}, 100, 1)}
        ctx = {"s1": {"avoided": 40_000, "returned": 0, "events": 2, "chars": 4_000},
               "old": {"avoided": 0, "returned": 0, "events": 0, "chars": 4_000}}  # a finished session: not live, still counted
        light = {l["id"]: l for l in token_tool_lights({"rtk": {}, "ctx": ctx}, named, [row("cockpit")])}["context-mode"]
        self.assertEqual(("~8k net (estimate)", "ok"), (light["value"], light["level"]))  # 10k kept - 2k hook text
        self.assertIn("2 events, counted once each", light["why"])
        ctx["old"]["chars"] = 80_000
        light = {l["id"]: l for l in token_tool_lights({"rtk": {}, "ctx": ctx}, named, [row("cockpit")])}["context-mode"]
        self.assertEqual(("~-11k net (estimate)", "watch"), (light["value"], light["level"]))

    def test_a_crashed_hook_is_watched_and_an_unreadable_count_is_unknown(self):
        named = {"ios": stats("s2", {"ponytail"}, 1, 0, [(1.0, "ponytail", "dyld: Library not loaded")])}
        lights = {l["id"]: l for l in token_tool_lights({"rtk": {"error": "rtk gain: not found"}, "ctx": {}}, named, [row("ios", ["ponytail"])])}
        self.assertEqual("watch", lights["ponytail"]["level"])
        self.assertIn("ios: dyld: Library not loaded", lights["ponytail"]["why"])
        self.assertEqual("unknown", lights["rtk"]["level"])

    def test_a_plugin_is_on_where_its_settings_enable_it_even_with_no_hook_run_in_24_h(self):
        named = {"brain": stats("s1", set(), 1, 0), "ios": stats("s2", set(), 1, 0)}
        lights = {l["id"]: l for l in token_tool_lights({"rtk": {}, "ctx": {}}, named,
                                                        [row("brain", ["ponytail"], ["adhd"]), row("ios", ["caveman", "ponytail"], ["caveman"])])}
        self.assertEqual(("on in 1 of 2", "on in 2 of 2", "on in 1 of 2"),
                         (lights["caveman"]["value"], lights["ponytail"]["value"], lights["i-have-adhd"]["value"]))
        self.assertIn("On (brain)", lights["i-have-adhd"]["why"])


class SessionPluginsTest(unittest.TestCase):
    def test_a_later_layer_wins_and_a_plugin_dir_adds_its_folder(self):
        layers = [("user", {"caveman@caveman": True, "ponytail@ponytail": True}), ("project", {"impeccable@impeccable": True}),
                  ("--settings", {"caveman@caveman": False})]
        self.assertEqual(["impeccable", "ponytail", "tools"],
                         enabled_plugins(layers, ["--settings", "/x/settings.json", "--plugin-dir", "/p/tools/"]))

    def test_a_start_mode_no_loaded_plugin_explains_shows_as_a_hook(self):
        from cockpit.sessions.session_plugins import hook_plugins
        self.assertEqual(["i-have-adhd"], hook_plugins(["adhd", "ponytail"], ["ponytail", "typesafe"]))
        self.assertEqual([], hook_plugins(["caveman"], ["caveman"]))

    def test_the_modes_of_the_last_start_and_the_skills_used_are_read_from_the_transcript(self):
        start = lambda t, said: {"type": "attachment", "timestamp": t, "attachment": {"type": "hook_success", "hookEvent": "SessionStart", "stdout": said}}
        lines = [start("2026-10-17T10:00:00Z", "CAVEMAN MODE ACTIVE — level: full"),
                 start("2026-10-18T10:00:00Z", "ADHD MODE ACTIVE (brain only)."), start("2026-10-18T10:00:02Z", "PONYTAIL MODE ACTIVE"),
                 {"type": "assistant", "timestamp": "2026-10-18T10:01:00Z", "message": {"id": "m1", "model": "claude-opus-5-5",
                  "usage": {"input_tokens": 1, "output_tokens": 1}, "content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "impeccable"}}]}}]
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "t.jsonl")
            with open(path, "w") as handle:
                handle.write("".join(json.dumps(l) + "\n" for l in lines))
            transcript = TranscriptFile(path)
            transcript.update()
        from cockpit.transcripts.transcript_stats import start_modes
        self.assertEqual({"adhd", "ponytail"}, start_modes(transcript.start_modes))
        self.assertEqual([("Skill", "impeccable")], next(iter(transcript.rows.values()))["tools"])


    def test_a_resume_record_counts_only_when_it_comes_after_the_process_start(self):
        # The shape of brain's resume at 2026-10-18T21:44:35Z (c4624776): hook_success, SessionStart:resume.
        resume = {"type": "attachment", "timestamp": "2026-10-18T21:44:35.062Z", "attachment": {
            "type": "hook_success", "hookName": "SessionStart:resume", "hookEvent": "SessionStart", "exitCode": 0,
            "command": "sh adhd_rules.sh", "stdout": "ADHD MODE ACTIVE (brain only)."}}
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "t.jsonl")
            with open(path, "w") as handle:
                handle.write(json.dumps(resume) + "\n")
            transcript = TranscriptFile(path)
            transcript.update()
        from dataclasses import replace
        from cockpit.sessions.session_row import modes_since_start
        from cockpit.times import parse_time
        from cockpit.transcripts.transcript_stats import start_modes
        at = parse_time("2026-10-18T21:44:35.062Z")
        stats = replace(Stats(90_000), start_modes=start_modes(transcript.start_modes), start_modes_at=at)
        self.assertEqual((["adhd"], ""), modes_since_start(stats, at - 0.5))
        modes, note = modes_since_start(stats, at + 3600)  # relaunched later, and that resume wrote no record
        self.assertEqual([], modes)
        self.assertIn("no SessionStart record since its process started", note)

class LocalTokenToolsTest(unittest.TestCase):
    def test_rtk_counts_the_team_scratchpad_folders_beside_the_repos(self):
        fake_rtk = ["python3", "-c", "import json; print(json.dumps({'daily': [{'date': '2026-10-18', 'saved_tokens': 5}]}))"]
        with tempfile.TemporaryDirectory() as root:
            for folder in ("repo", "tmp-team-a", "tmp-team-b", "other"):
                os.mkdir(os.path.join(root, folder))
            tools = LocalTokenTools(fake_rtk, [os.path.join(root, "repo")], os.path.join(root, "tmp-team-*"), root, root, 5)
            self.assertEqual({"repo": 5, "tmp-team-a": 5, "tmp-team-b": 5}, tools.rtk_saved("2026-10-18"))

    def test_hook_chars_count_context_mode_hook_output_and_tool_lines_only(self):
        lines = [{"type": "attachment", "attachment": {"type": "hook_success", "command": "node context-mode/hooks/x.mjs", "stdout": "a" * 100}},
                 {"type": "attachment", "attachment": {"type": "hook_success", "command": "rtk hook claude", "stdout": "b" * 50}},
                 {"type": "attachment", "attachment": {"type": "deferred_tools_delta",
                                                       "addedLines": ["mcp__plugin_context-mode__ctx_stats", "mcp__other__tool"]}}]
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "s9.jsonl")
            with open(path, "w") as handle:
                handle.write("".join(json.dumps(l, separators=(",", ":")) + "\n" for l in lines))
            ctx = LocalTokenTools([], [], root, root, os.path.join(root, "*.jsonl"), 5).ctx_kept_out()
        self.assertEqual(100 + len("mcp__plugin_context-mode__ctx_stats"), ctx["s9"]["chars"])


class TokenToolHooksTest(unittest.TestCase):
    def test_hook_runs_and_failures_are_read_from_the_transcript(self):
        lines = [{"type": "attachment", "timestamp": "2026-10-18T10:00:00Z",
                  "attachment": {"type": "hook_success", "command": "PATH=x rtk hook claude", "exitCode": 0}},
                 {"type": "attachment", "timestamp": "2026-10-18T10:01:00Z",
                  "attachment": {"type": "hook_cancelled", "command": "Loading ponytail mode...", "timedOut": True}},
                 {"type": "attachment", "timestamp": "2026-10-18T10:02:00Z",
                  "attachment": {"type": "hook_success", "command": "bash guard.sh"}}]
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "t.jsonl")
            with open(path, "w") as handle:
                handle.write("".join(json.dumps(l) + "\n" for l in lines))
            transcript = TranscriptFile(path)
            transcript.update()
        self.assertEqual({"rtk"}, set(transcript.tool_runs))
        self.assertEqual([("ponytail", "timed out")], [(tool, said) for _, tool, said in transcript.tool_failures])


    def test_a_file_read_again_counts_until_a_compaction_drops_the_first_read(self):
        rows = [{"t_first": t, "tools": [("Read", path)]} for t, path in ((1, "a.py"), (2, "a.py"), (3, "b.py"), (5, "a.py"))]
        self.assertEqual(1, re_reads(rows, [{"at": 4}], 0))
        self.assertEqual(2, re_reads(rows, [], 0))



def hooks(*commands):
    return {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": c} for c in commands]}]}}


class ConfigGuardTest(unittest.TestCase):
    def test_a_tool_line_added_or_another_tools_line_dropped_is_drift_and_other_lines_are_not(self):
        before = {"s.json": hooks("rtk hook claude", "bash guard.sh")}
        after = {"s.json": hooks("node context-mode/hooks/pretooluse.mjs", "bash other.sh")}
        [change] = config_drift(before, after)
        self.assertEqual(["hook PreToolUse Bash: node context-mode/hooks/pretooluse.mjs"], change["added"])
        self.assertEqual(["hook PreToolUse Bash: rtk hook claude"], change["removed"])
        self.assertEqual(["context-mode", "rtk"], change["tools"])
        self.assertEqual([], config_drift(before, before))

    def test_an_mcp_servers_env_never_reaches_the_baseline(self):
        part = watched_part({"mcpServers": {"context-mode": {"command": "node", "env": {"TOKEN": "x"}}}, "model": "opus"})
        self.assertEqual({"mcpServers": {"context-mode": {"command": "node"}}}, part)


if __name__ == "__main__":
    unittest.main()
