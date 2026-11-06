import unittest

from cockpit.snapshot.rewrites_light import rewrites_light
from cockpit.transcripts.cache_rewrites import rewrites
from tests.builders import NOW
from tests.test_sessions import stats
from dataclasses import replace


def request(t, context, write, model="claude-opus-5-5", effort="medium"):
    return {"t_first": t, "t_last": t + 5, "context": context, "write": write, "model": model, "effort": effort}


class CacheRewritesTest(unittest.TestCase):
    def test_each_rewrite_gets_its_cause_and_a_normal_turn_is_none(self):
        rows = [request(NOW - 9000, 60_000, 60_000),                  # first request: clear or new start
                request(NOW - 8900, 62_000, 2_000),                   # a normal turn writes only its new part
                request(NOW - 8800, 30_000, 30_000),                  # after a compact_boundary
                request(NOW - 4000, 31_000, 31_000),                  # 80 m later on a 60 m cache
                request(NOW - 3900, 32_000, 32_000, effort="xhigh"),  # effort changed: the cached messages are gone
                request(NOW - 3800, 33_000, 33_000, effort="xhigh")]  # none of those: an account move or a relaunch
        found = rewrites(rows, [{"at": NOW - 8850}], 3600, NOW - 86400)
        self.assertEqual(["clear", "compact", "expiry", "settings change", "unknown"], [c for c, _ in found])
        self.assertEqual([], [c for c, _ in rewrites(rows, [], 3600, NOW)])  # older than 24 h

    def test_the_light_watches_avoidable_rewrites_and_totals_each_cause(self):
        named = {"ios": replace(stats(90_000), rewrites_24h=(("expiry", 50_000), ("settings change", 40_000))),
                 "ai": replace(stats(90_000), rewrites_24h=(("compact", 30_000),))}
        lit = rewrites_light(named)
        self.assertEqual(("watch", "3 in 24 h"), (lit["level"], lit["value"]))
        totals = {t["key"]: t["value"] for t in lit["table"]["totals"]}
        self.assertEqual((50_000, 40_000, 30_000, 0), (totals["expiry"], totals["settings change"], totals["compact"], totals["unknown"]))
        self.assertEqual("ok", rewrites_light({"ai": named["ai"]})["level"])


if __name__ == "__main__":
    unittest.main()
