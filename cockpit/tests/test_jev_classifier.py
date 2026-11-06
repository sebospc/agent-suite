import io
import json
import os
import unittest
import urllib.error
from unittest import mock

from cockpit.classifier.jev_classifier import ENDPOINT, JevClassifier
from cockpit.classifier.not_connected_classifier import NotConnectedClassifier
from cockpit.composition import task_classifier
from cockpit.source_unavailable import SourceUnavailable

KEY = "test-key-not-real"
ANSWER = {"model": "jev-1.14.0", "usage": {"input_tokens": 300, "output_tokens": 40}, "answers": {
    "mechanical": {"type": "choice", "choice": "no", "confidence": 0.81, "probabilities": {"yes": 0.12, "no": 0.88}},
    "deep_reasoning": {"type": "choice", "choice": "yes", "confidence": 0.64, "probabilities": {"yes": 0.75, "no": 0.25}},
    "needs_history": {"type": "choice", "choice": "no", "confidence": 0.9},
    "wide_reading": {"type": "choice", "choice": "yes", "confidence": 0.7}}}


class FakeHttp:
    """Stands in for urllib.request.urlopen: keeps the request, answers with a canned body or raises."""

    def __init__(self, body=b"", error=None):
        self.body = body
        self.error = error
        self.sent = None

    def __call__(self, request, timeout):
        self.sent = request
        if self.error:
            raise self.error
        return io.BytesIO(self.body)


class JevClassifierTest(unittest.TestCase):
    def test_it_asks_four_yes_no_judgments_on_the_beads_title_and_description(self):
        http = FakeHttp(json.dumps(ANSWER).encode())
        found = JevClassifier(KEY, 5, http).classify("pg-a", "Fix the date parser", "Off by one at month end.")
        self.assertEqual({"mechanical": 0.12, "deep_reasoning": 0.75, "needs_history": 0.1, "wide_reading": 0.7},
                         {k: round(v, 2) for k, v in found["probabilities"].items()})
        sent = json.loads(http.sent.data)
        self.assertEqual((ENDPOINT, "POST", f"Bearer {KEY}"), (http.sent.full_url, http.sent.get_method(), http.sent.get_header("Authorization")))
        self.assertEqual("jev-latest", sent["model"])
        self.assertEqual({"title": "Fix the date parser", "description": "Off by one at month end."}, sent["state"]["task"])
        self.assertEqual(["yes", "no"], list(sent["questions"]["deep_reasoning"]["criteria"]))

    def test_a_verdict_sends_its_own_questions_and_state_and_reads_only_their_answers(self):
        http = FakeHttp(json.dumps(ANSWER).encode())
        questions = {"deep_reasoning": {"type": "choice"}}
        found = JevClassifier(KEY, 5, http).judge("session brain", "v1", questions, {"session": {"role": "coordinates"}})
        self.assertEqual({"deep_reasoning": 0.75}, found)
        sent = json.loads(http.sent.data)
        self.assertEqual((questions, {"session": {"role": "coordinates"}}), (sent["questions"], sent["state"]))

    def test_a_refused_key_or_a_broken_answer_is_unavailable_and_never_shows_the_key(self):
        refused = urllib.error.HTTPError(ENDPOINT, 401, "Unauthorized", {}, io.BytesIO(b"{}"))
        for http in (FakeHttp(error=refused), FakeHttp(error=urllib.error.URLError("timed out")), FakeHttp(b"{\"answers\": {}}")):
            with self.assertRaises(SourceUnavailable) as caught:
                JevClassifier(KEY, 5, http).classify("pg-a", "title", "")
            self.assertNotIn(KEY, str(caught.exception))
            self.assertIn("pg-a", str(caught.exception))


class CompositionTest(unittest.TestCase):
    def test_jev_runs_only_when_jev_env_holds_a_key(self):
        with mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": KEY}):
            self.assertIsInstance(task_classifier().inner, JevClassifier)
        with mock.patch.dict(os.environ, {"TYPESAFE_API_KEY": " "}):
            self.assertIsInstance(task_classifier().inner, NotConnectedClassifier)


if __name__ == "__main__":
    unittest.main()


class JevCallsTest(unittest.TestCase):
    """pg-45v5 measure 2: Jev's own calls and tokens, from the usage TypeSafe returns."""

    def test_each_request_records_its_usage_and_the_light_shares_it_against_the_team(self):
        from cockpit.action_log.fake_action_log import FakeActionLog
        from cockpit.jev_record.jev_calls import JevCalls
        from tests.builders import NOW
        clock = [NOW]
        calls = JevCalls(FakeActionLog(), lambda: clock[0], lambda line: None)
        http = FakeHttp(json.dumps(ANSWER).encode())
        JevClassifier(KEY, 5, http, on_usage=calls.record).classify("pg-a", "Fix the date parser", "")
        self.assertEqual([("pg-a", 4, 300, 40)], [(r["key"], r["questions"], r["in"], r["out"]) for r in calls.log.records])
        clock[0] = NOW + 2 * 86400
        calls.record("session ios", 5, {"input_tokens": 1000, "output_tokens": 60})
        lit = calls.light(100_000)
        day, week = lit["table"]["rows"]
        self.assertEqual((1, 1060), (day["calls"], day["in"] + day["out"]))
        self.assertEqual((2, 1400), (week["calls"], week["in"] + week["out"]))
        self.assertEqual("watch", lit["level"])  # 1,060 of 100,000 is over 1%
        self.assertEqual("ok", calls.light(10_000_000)["level"])
        self.assertIn("1.06% of the team's", lit["why"])
