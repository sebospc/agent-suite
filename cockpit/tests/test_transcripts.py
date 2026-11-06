import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone

from cockpit.transcripts.jsonl_transcripts import JsonlTranscripts
from cockpit.transcripts.transcript_file import TranscriptFile
from tests.builders import FIXTURES

SESSION = "fa5982a7-9c01-5238-bfed-dd0f785ab697"
T0 = 1_790_000_000


def iso(stamp):
    return datetime.fromtimestamp(stamp, timezone.utc).isoformat().replace("+00:00", "Z")


def assistant(message_id, stamp, context, tools=(), output=300, text=""):
    content = [{"type": "tool_use", "name": n, "input": {"file_path": f}} for n, f in tools]
    if text:
        content.append({"type": "text", "text": text})
    return {"type": "assistant", "timestamp": iso(stamp), "isSidechain": False, "effort": "high",
            "message": {"id": message_id, "model": "claude-opus-5-5", "content": content,
                        "usage": {"input_tokens": 2, "cache_read_input_tokens": context - 1000, "cache_creation_input_tokens": 998,
                                  "output_tokens": output, "cache_creation": {"ephemeral_1h_input_tokens": 998, "ephemeral_5m_input_tokens": 0}}}}


class TranscriptsTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "proj"))
        self.addCleanup(shutil.rmtree, self.root)

    def write(self, entries, name="s1"):
        with open(os.path.join(self.root, "proj", f"{name}.jsonl"), "a") as handle:
            handle.writelines(json.dumps(e) + "\n" for e in entries)

    def stats(self, name="s1", now=T0 + 3000):
        return JsonlTranscripts(self.root, 100_000, 600).stats([name], now)[name]

    def test_the_fixture_counts_each_response_once(self):
        path = os.path.join(FIXTURES, "transcript.sample.jsonl")
        with open(path) as handle:
            assistant_lines = sum(1 for line in handle if '"type": "assistant"' in line)
        rows = TranscriptFile(path)
        rows.update()
        ids = {r for r in rows.rows}
        self.assertLess(len(ids), assistant_lines)  # the repeated-usage lines collapse
        with open(path) as handle:
            unique = {json.loads(line)["message"]["id"] for line in handle if '"type": "assistant"' in line}
        self.assertEqual(len(unique), len(ids))

    def test_jev_sees_only_its_last_few_turns_cut_short_and_never_a_tool_result(self):
        def user(stamp, content):
            return {"type": "user", "timestamp": iso(stamp), "isSidechain": False, "message": {"role": "user", "content": content}}
        entries = [user(T0, "first question, long gone")]
        entries += [assistant(f"m{i}", T0 + 10 * i, 10_000, text=f"reply {i}") for i in range(1, 6)]
        entries += [user(T0 + 60, [{"type": "tool_result", "content": "a file"}]), user(T0 + 70, "/compact"), user(T0 + 80, "x" * 900)]
        self.write(entries)
        turns = self.stats().last_turns
        self.assertEqual(["replied"] * 5 + ["asked"], [who for _, who, _ in turns])
        self.assertEqual(500, len(turns[-1][2]))

    def test_daily_totals_put_each_request_on_its_day(self):
        self.write([assistant("m1", T0 + 100, 10_000), assistant("m2", T0 + 86400 + 100, 20_000)])
        totals = JsonlTranscripts(self.root, 100_000, 600).daily_totals([T0, T0 + 86400, T0 + 2 * 86400], T0 + 2 * 86400 + 50)
        self.assertEqual([(10_300, 9_998), (20_300, 19_998), (0, 0)], totals)  # context plus output, of which cache reads and writes

    def test_a_response_written_twice_keeps_its_final_output(self):
        self.write([assistant("m1", T0, 50_000, output=10), assistant("m1", T0 + 1, 50_000, output=300)])
        stats = self.stats()
        self.assertEqual([300], stats.outputs)
        self.assertEqual(50_000, stats.context_now)

    def test_after_a_compaction_the_context_is_its_post_size_until_the_next_turn(self):
        self.write([assistant("m1", T0, 70_000),
                    {"type": "system", "subtype": "compact_boundary", "timestamp": iso(T0 + 60),
                     "compactMetadata": {"trigger": "auto", "preTokens": 70_000, "postTokens": 58_000}}])
        self.assertEqual(58_000, self.stats().context_now)

    def test_a_compaction_with_no_recorded_size_leaves_the_context_unknown_not_0_nor_the_old_size(self):
        self.write([assistant("m1", T0, 157_000),
                    {"type": "system", "subtype": "compact_boundary", "timestamp": iso(T0 + 60),
                     "compactMetadata": {"trigger": "manual", "preTokens": 157_000, "postTokens": 0}}])
        stats = self.stats()
        self.assertIsNone(stats.context_now)
        self.assertIsNone(stats.compactions[0].post)

    def test_compaction_inputs_and_growth_without_the_recovery_requests(self):
        self.write([assistant("m1", T0, 50_000, [("Read", "a.py")]), assistant("m2", T0 + 30, 60_000, [("Read", "b.py")]),
                    assistant("m3", T0 + 90, 70_000, [("Edit", "b.py")]),
                    {"type": "system", "subtype": "compact_boundary", "timestamp": iso(T0 + 120),
                     "compactMetadata": {"trigger": "auto", "preTokens": 70_000, "postTokens": 58_000}},
                    assistant("m4", T0 + 180, 59_000, [("Read", "a.py")]), assistant("m5", T0 + 210, 64_000, [("Read", "b.py")]),
                    assistant("m6", T0 + 240, 66_000, [("Read", "c.py")])])
        stats = self.stats()
        compaction = stats.compactions[0]
        self.assertEqual((59_000, 58_000, None), (compaction.first_context, compaction.first_cached, compaction.recovery))
        self.assertEqual([10_000, 10_000], stats.growth)  # m4 to m6 are its recovery, still unfinished

    def test_reading_is_incremental_and_waits_for_a_whole_line(self):
        transcripts = JsonlTranscripts(self.root, 100_000, 600)
        self.write([assistant("m1", T0, 50_000)])
        with open(os.path.join(self.root, "proj", "s1.jsonl"), "a") as handle:
            handle.write(json.dumps(assistant("m2", T0 + 10, 60_000))[:40])
        self.assertEqual(50_000, transcripts.stats(["s1"], T0 + 100)["s1"].context_now)
        with open(os.path.join(self.root, "proj", "s1.jsonl"), "a") as handle:
            handle.write(json.dumps(assistant("m2", T0 + 10, 60_000))[40:] + "\n")
        self.assertEqual(60_000, transcripts.stats(["s1"], T0 + 100)["s1"].context_now)

    def test_tokens_24h_include_subagents_and_bead_ids_named_in_replies(self):
        self.write([assistant("m1", T0, 50_000, text="Opened pg-ab12.3 and pg-zz99.")])
        os.makedirs(os.path.join(self.root, "proj", "s1", "subagents"))
        with open(os.path.join(self.root, "proj", "s1", "subagents", "a.jsonl"), "w") as handle:
            handle.write(json.dumps(dict(assistant("x1", T0 + 5, 20_000), isSidechain=True)) + "\n")
        stats = self.stats()
        self.assertEqual(2 + 300 + 2 + 300, stats.tokens_24h)  # without cache: fresh input and output
        self.assertEqual({"pg-ab12.3", "pg-zz99"}, stats.mentioned_beads)

    def test_daily_tokens_compare_today_with_yesterday_at_the_same_time(self):
        day = 86400
        self.write([assistant("m1", T0 - day + 100, 10_000), assistant("m2", T0 - day + 900, 20_000), assistant("m3", T0 + 100, 30_000)])
        # Without cache (fresh input and output), then today's cache reads and writes.
        self.assertEqual((302, 302, 29_998), JsonlTranscripts(self.root, 100_000, 600).daily_tokens((T0 - day, T0, T0 + 500)))


if __name__ == "__main__":
    unittest.main()


class RepliesTest(TranscriptsTest):
    def test_ids_named_in_replies_and_saved_claims_by_place(self):
        self.write([assistant("m1", T0 + 10, 10_000, text="Answered ask abc123 and landed 1a2b3c4d."),
                    assistant("m2", T0 + 20, 10_000, text="Saved it to /tmp/notes.md."),
                    assistant("m3", T0 + 30, 10_000, text="Done, saved.")])
        st = self.stats(now=T0 + 100)
        self.assertEqual(({"abc123"}, {"1a2b3c4d"}), (st.mentioned_asks, st.mentioned_commits))
        self.assertEqual((1, ["scratchpad"]), (st.saved_without_id, st.saved_places))

    def test_a_peer_message_starts_a_turn_whose_tokens_it_carries(self):
        peer = {"type": "user", "timestamp": iso(T0 + 5), "isSidechain": False,
                "message": {"role": "user", "content": '<cross-session-message from="x">GO pg-a18q\nsha256: 1</cross-session-message>'}}
        self.write([{"type": "custom-title", "customTitle": "agent-ios"}, peer, assistant("m1", T0 + 10, 10_000)])
        past = JsonlTranscripts(self.root, 100_000, 600).history(T0, T0 + 100, {})
        self.assertEqual(("agent-ios", "peer"), (past.requests[0].session, past.requests[0].origin))
        self.assertEqual(("GO", "pg-a18q", 10_300), (past.messages[0].type, past.messages[0].bead, past.messages[0].tokens))


class ReadsSinceStartTest(unittest.TestCase):
    setUp, write, stats = TranscriptsTest.setUp, TranscriptsTest.write, TranscriptsTest.stats

    def test_the_files_it_reads_after_its_last_start_are_kept_apart_from_its_first_ones(self):
        start = {"type": "attachment", "timestamp": iso(T0 + 1000), "attachment": {"hookEvent": "SessionStart", "type": "hook_success", "stdout": ""}}
        ask = {"type": "user", "timestamp": iso(T0 + 1001), "message": {"role": "user", "content": "go on"}}
        self.write([assistant("a1", T0, 20_000, tools=[("Read", "/m/project_ios_state.md")]), start, ask,
                    assistant("a2", T0 + 1002, 30_000, tools=[("Read", "/repo/x.py")])])
        found = self.stats()
        self.assertEqual(frozenset({"/repo/x.py"}), found.reads_since_start)
        self.assertIn("/m/project_ios_state.md", found.first_reads)

    def test_no_turn_after_its_last_start_is_unknown(self):
        start = {"type": "attachment", "timestamp": iso(T0 + 1000), "attachment": {"hookEvent": "SessionStart", "type": "hook_success", "stdout": ""}}
        self.write([assistant("a1", T0, 20_000, tools=[("Read", "/repo/x.py")]), start])
        self.assertIsNone(self.stats().reads_since_start)

    def test_no_start_seen_is_unknown(self):
        self.write([assistant("a1", T0, 20_000, tools=[("Read", "/repo/x.py")])])
        self.assertIsNone(self.stats().reads_since_start)
