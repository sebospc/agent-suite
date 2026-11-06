import unittest
from types import SimpleNamespace

from cockpit.snapshot.hook_output_light import hook_output_light
from cockpit.transcripts.transcript_file import TranscriptFile

STATE = 'python3 "$HOME/.agent-board/session_state.py"'


class HookOutputTest(unittest.TestCase):
    def test_a_hooks_whole_stdout_is_measured_not_the_stub_claude_code_kept(self):
        transcript = TranscriptFile("unused")
        transcript.take({"type": "attachment", "timestamp": "2026-10-24T13:38:29Z", "attachment": {
            "type": "hook_success", "hookEvent": "SessionStart", "command": STATE, "stdout": "x" * 17_456,
            "content": "<persisted-output>\nOutput too large (17KB)."}})
        self.assertEqual(17_456, transcript.hook_outputs[STATE][1])

    def test_it_acts_on_the_hook_whose_last_output_reached_10k(self):
        named = {"brain": SimpleNamespace(hook_outputs=((STATE, 100.0, 12_000), ("rtk hook claude", 100.0, 3_000))),
                 "ios": SimpleNamespace(hook_outputs=((STATE, 200.0, 9_000),))}
        lit = hook_output_light(named)
        self.assertEqual(("ok", "largest 9,000 chars"), (lit["level"], lit["value"]))  # ios ran it last, under 10k
        named["ios"] = SimpleNamespace(hook_outputs=((STATE, 200.0, 10_000),))
        self.assertEqual(("act", ["session_state.py", "rtk hook claude"]), (hook_output_light(named)["level"],
                                                                  [r["script"] for r in hook_output_light(named)["table"]["rows"]]))


if __name__ == "__main__":
    unittest.main()
