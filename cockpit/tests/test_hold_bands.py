import json
import unittest

from cockpit.tokens.hold_bands import hold_bands
from cockpit.transcripts.history import History, PeerMessage, ReviewRequest
from cockpit.transcripts.jsonl_transcripts import JsonlTranscripts
from tests import test_transcripts as base


def sent(t, context, sha="aa", bead="pg-a1", model="claude-opus-5-5", sender="agent-ios"):
    return ReviewRequest(t=t, sender=sender, bead=bead, sha256=sha, context=context, model=model)


def verdict(t, kind, sha="aa", bead="pg-a1"):
    return PeerMessage(t=t, to="agent-ios", type=kind, bead=bead, in_format=True, digest="d", tokens=0, keys={"sha256": sha})


def bands(model):
    return {b["band"]: (b["n"], b["holds"]) for b in model["bands"]}


class HoldBandsTest(unittest.TestCase):
    def test_a_review_lands_in_the_band_of_the_senders_context_edges_included(self):
        contexts = [99_999, 100_000, 199_999, 200_000, 299_999, 300_000]
        requests = [sent(10, c, sha=str(i)) for i, c in enumerate(contexts)]
        got = hold_bands(History(review_requests=requests, messages=[verdict(20, "GO", sha=str(i)) for i in range(6)]), 1)
        self.assertEqual({"under 100k": (1, 0), "100-200k": (2, 0), "200-300k": (2, 0), "over 300k": (1, 0)}, bands(got["models"][0]))

    def test_the_verdict_is_matched_by_bead_and_sha256_and_comes_after_the_request(self):
        history = History(
            review_requests=[sent(10, 50_000, sha="aa"), sent(10, 50_000, sha="bb"), sent(10, 150_000, sha="cc"), sent(10, 150_000, sha="dd", bead="pg-b2")],
            messages=[verdict(20, "HOLD", sha="aa"),              # matches the first
                      verdict(20, "GO", sha="zz"),                # another patch: ignored
                      verdict(5, "GO", sha="bb"),                 # before the request: ignored, so bb waits
                      verdict(20, "GO", sha="cc"), verdict(30, "HOLD", sha="cc"),   # any HOLD makes it a HOLD
                      verdict(20, "GO", sha="dd", bead="pg-other")])                # another bead: ignored
        got = hold_bands(history, 1)
        self.assertEqual({"under 100k": (1, 1), "100-200k": (1, 1), "200-300k": (0, 0), "over 300k": (0, 0)}, bands(got["models"][0]))
        self.assertEqual(2, got["waiting"])

    def test_a_patch_sent_twice_counts_once_at_its_first_send(self):
        history = History(review_requests=[sent(10, 250_000), sent(50, 40_000)], messages=[verdict(60, "GO")])
        self.assertEqual({"under 100k": (0, 0), "100-200k": (0, 0), "200-300k": (1, 0), "over 300k": (0, 0)}, bands(hold_bands(history, 1)["models"][0]))

    def test_models_are_apart_and_a_band_under_the_minimum_shows_no_rate(self):
        requests = [sent(10, 50_000, sha=str(i)) for i in range(4)] + [sent(10, 50_000, sha="s", model="claude-sonnet-5-5")]
        messages = [verdict(20, "HOLD" if i == 0 else "GO", sha=str(i)) for i in range(4)] + [verdict(20, "HOLD", sha="s")]
        got = hold_bands(History(review_requests=requests, messages=messages), 4)
        self.assertEqual(["Opus 5.5", "Sonnet 5.5"], [m["model"] for m in got["models"]])
        opus, sonnet = (m["bands"][0] for m in got["models"])
        self.assertEqual((4, 1, True, 25), (opus["n"], opus["holds"], opus["enough"], opus["rate"]))
        self.assertEqual((1, 1, False, None), (sonnet["n"], sonnet["holds"], sonnet["enough"], sonnet["rate"]))


class SenderTranscriptTest(base.TranscriptsTest):
    def go_req(self, message_id, stamp, context, call, text="GO-REQ pg-a1b2 v1\npatch: /s/p.diff\nsha256: AA11\nbase: abc1234"):
        entry = base.assistant(message_id, stamp, context)
        entry["message"]["content"].append({"type": "tool_use", "id": call, "name": "SendMessage", "input": {"to": "agent-reviewer", "message": text}})
        return entry

    def test_the_sender_its_context_and_model_come_from_the_request_that_sent_the_go_req(self):
        first = self.go_req("m1", base.T0 + 10, 180_000, "t1")
        self.write([{"type": "custom-title", "customTitle": "agent-ios"}, base.assistant("m0", base.T0 + 5, 90_000), first, dict(first),
                    self.go_req("m2", base.T0 + 20, 190_000, "t2", text="HOLD pg-a1b2\nsha256: aa11")])
        past = JsonlTranscripts(self.root, 100_000, 600).history(base.T0, base.T0 + 100, {})
        self.assertEqual([("agent-ios", "pg-a1b2", "aa11", 180_000, "claude-opus-5-5")],
                         [(r.sender, r.bead, r.sha256, r.context, r.model) for r in past.review_requests])  # sent once, not a HOLD
        self.assertEqual(base.T0 + 10, past.review_requests[0].t)


if __name__ == "__main__":
    unittest.main()
