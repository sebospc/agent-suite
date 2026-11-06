"""Tests for the phase 0 scripts on small synthetic transcripts and board data.

Run: python3 -m unittest discover -s research/scripts -p 'test_*.py'
"""
import contextlib
import io
import json
import os
import random
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calibrate_quota  # noqa: E402
import calibrate_sessions  # noqa: E402
import measure_thresholds  # noqa: E402
from transcript_requests import address_in, read_transcript  # noqa: E402


def iso(stamp):
    return datetime.fromtimestamp(stamp, timezone.utc).isoformat().replace("+00:00", "Z")


def assistant(message_id, stamp, context, tools=(), output=300, model="claude-opus-5-5"):
    return {"type": "assistant", "timestamp": iso(stamp), "isSidechain": False, "effort": "high",
            "message": {"id": message_id, "model": model,
                        "content": [{"type": "tool_use", "name": n, "input": {"file_path": f}} for n, f in tools],
                        "usage": {"input_tokens": 2, "cache_read_input_tokens": context - 1000,
                                  "cache_creation_input_tokens": 998, "output_tokens": output,
                                  "cache_creation": {"ephemeral_1h_input_tokens": 998, "ephemeral_5m_input_tokens": 0}}}}


def write_lines(path, entries):
    with open(path, "w") as handle:
        handle.writelines(json.dumps(e) + "\n" for e in entries)


T0 = 1_790_000_000


class SessionCalibrationTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.path = os.path.join(self.folder, "s1.jsonl")
        write_lines(self.path, [
            {"type": "custom-title", "customTitle": "agent-ios"},
            assistant("m1", T0, 50_000, [("Read", "a.py")], output=10),
            assistant("m1", T0 + 1, 50_000, output=300),  # same response written twice
            assistant("m2", T0 + 30, 60_000, [("Read", "b.py")]),
            assistant("m3", T0 + 1200, 70_000, [("Edit", "b.py")]),
            {"type": "system", "subtype": "compact_boundary", "timestamp": iso(T0 + 1260),
             "compactMetadata": {"trigger": "auto", "preTokens": 70_000, "postTokens": 66_000}},
            assistant("m4", T0 + 1320, 59_000, [("Read", "a.py")]),
            assistant("m5", T0 + 1350, 64_000, [("Read", "b.py")]),
            assistant("m6", T0 + 1380, 66_000, [("Read", "c.py")]),
        ])

    def numbers(self):
        return calibrate_sessions.session_numbers(self.path, read_transcript(self.path))

    def test_a_response_written_twice_counts_once_with_its_final_output(self):
        rows = read_transcript(self.path)["requests"]
        self.assertEqual(6, len(rows))
        self.assertEqual(300, rows[0]["out"])

    def test_compaction_inputs_come_from_the_first_request_after_the_boundary(self):
        compaction = self.numbers()["compactions"][0]
        self.assertEqual((59_000, 58_000, 8_000), (compaction["P"], compaction["F_s"], compaction["S"]))

    def test_rereading_files_read_before_the_boundary_counts_as_rework(self):
        compaction = self.numbers()["compactions"][0]
        self.assertEqual((1, 5_000), (compaction["k_R"], compaction["D"]))

    def test_growth_leaves_out_the_post_compaction_and_rework_turns(self):
        self.assertAlmostEqual((10_000 + 10_000 + 2_000) / 3, self.numbers()["g"])

    def test_idle_gaps_count_only_waits_of_a_minute_or_more(self):
        self.assertEqual([19.5, 2.0], [round(m, 1) for m in self.numbers()["idle"]])


class QuotaCalibrationTest(unittest.TestCase):
    def test_the_fit_recovers_the_weights_that_moved_the_5h_percent(self):
        folder = tempfile.mkdtemp()
        os.mkdir(os.path.join(folder, "projects"))
        rng, samples = random.Random(1), []
        for number, email, weight in ((1, "a@x.com", 1), (2, "b@x.com", 20)):
            entries = [{"type": "attachment", "timestamp": iso(T0), "attachment": {"context": {"userEmail": f"The user's email address is {email}. Use it only to identify the user."}}}]
            stamp, index = T0, 0
            for window in range(10):  # one usage point per 5h window; the % starts again at each reset
                resets = iso(T0 + (window + 1) * 6 * 3600)
                pct5 = float(window % 3)  # a window may already be in use when the balancer first samples it
                samples.append({"t": stamp, "account": number, "usage": {"fiveHour": {"pct": pct5, "resetsAt": resets}, "sevenDay": {"pct": 0}}})
                start5 = pct5
                for _ in range(2):
                    for _ in range(4):
                        stamp, index = stamp + 60, index + 1
                        read, output = rng.randint(50, 300) * 1000, rng.randint(1, 8) * 1000
                        entries.append(assistant(f"{number}-{index}", stamp, read + 1000, output=output))
                        pct5 += (0.002 * (read - 1000) / 1000 + 0.08 * 0.998 + 0.1 * output / 1000) / weight
                    stamp += 1200
                    samples.append({"t": stamp, "account": number, "usage": {"fiveHour": {"pct": pct5, "resetsAt": resets},
                                                                            "sevenDay": {"pct": (pct5 - start5) / 6.5}}})
                stamp = T0 + (window + 1) * 6 * 3600
            write_lines(os.path.join(folder, "projects", f"s{number}.jsonl"), entries)
        write_lines(os.path.join(folder, "samples.jsonl"), samples)
        with open(os.path.join(folder, "cswap.json"), "w") as handle:
            json.dump([{"number": 1, "email": "a@x.com", "plan": "pro"}, {"number": 2, "email": "b@x.com", "plan": "max_20x"}], handle)
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            calibrate_quota.main(["--cswap", os.path.join(folder, "cswap.json"), "--samples",
                                  os.path.join(folder, "samples.jsonl"), os.path.join(folder, "projects")])
        text = printed.getvalue()
        self.assertIn("read=0.00200", text)
        self.assertIn("out=0.10000", text)
        self.assertIn("pro: 6.50", text)
        self.assertNotIn("a@x.com", text)


class NonnegativeFitTest(unittest.TestCase):
    def test_a_column_that_would_go_negative_is_held_at_zero(self):
        from least_squares import nonnegative_fit
        xs = [[1, 1], [2, 1], [3, 1], [4, 2]]
        ys = [1.9, 4.1, 5.9, 7.8]  # unconstrained gives the second column a negative weight
        weights = nonnegative_fit(xs, ys)
        self.assertEqual(0.0, weights[1])
        self.assertAlmostEqual(1.97, weights[0], places=2)


class EmailMatchTest(unittest.TestCase):
    def test_display_names_case_dots_and_plus_tags_do_not_block_a_match(self):
        self.assertEqual(calibrate_quota.normal("ab@gmail.com"), calibrate_quota.normal("Name <A.b+2@Gmail.com>"))
        self.assertEqual("aa9@a.aaa", calibrate_quota.shape("ab1@x.com"))

    def test_the_address_is_taken_out_of_the_userEmail_sentence(self):
        sentence = "The user's email address is ab-12cd@example.com. Use it only to identify the user."
        self.assertEqual("ab-12cd@example.com", address_in(sentence))
        self.assertIsNone(address_in("no address here"))


class ThresholdEvidenceTest(unittest.TestCase):
    def test_longest_silence_is_the_biggest_gap_between_visible_updates(self):
        bead = {"id": "pg-1", "started_at": iso(T0), "closed_at": iso(T0 + 10 * 3600), "status": "closed",
                "comments": [{"created_at": iso(T0 + 1 * 3600)}, {"created_at": iso(T0 + 3 * 3600)}]}
        longest, durations = measure_thresholds.silences([bead], T0 + 20 * 3600)
        self.assertEqual(([7.0], [10.0]), (longest, durations))

    def test_concurrency_counts_overlapping_claims_per_assignee(self):
        beads = [{"assignee": "agent-ai", "started_at": iso(T0), "closed_at": iso(T0 + 4 * 3600)},
                 {"assignee": "agent-ai", "started_at": iso(T0 + 3600), "closed_at": iso(T0 + 2 * 3600)}]
        self.assertEqual({"agent-ai": (2, 1.0)}, measure_thresholds.concurrency(beads, T0 + 10 * 3600))


if __name__ == "__main__":
    unittest.main()
