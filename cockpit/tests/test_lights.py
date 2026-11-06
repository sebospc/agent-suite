import unittest

from cockpit.git.gate_state import GateState
from cockpit.snapshot import lights
from tests.builders import HOUR, NOW


def session(state="idle", over=False, haiku=False):
    return {"state": state, "over": over, "haiku_over_step": haiku}


def level_and_value(light):
    return light["level"], light["value"]


class LightsTest(unittest.TestCase):
    def test_context_is_act_on_haiku_watch_over_spot_ok_otherwise(self):
        self.assertEqual(("act", "2 over"), level_and_value(lights.context_light([session(haiku=True, over=True), session(over=True)])))
        self.assertEqual(("watch", "1 over"), level_and_value(lights.context_light([session(over=True), session()])))
        self.assertEqual(("ok", "1 running"), level_and_value(lights.context_light([session(), session("off")])))
        self.assertEqual("sessions", lights.context_light([])["tab"])

    def test_main_is_act_when_red_and_unknown_without_a_gate(self):
        red = lights.main_light(GateState("C1abcdef9", False, False, 2, 0, ""))
        self.assertEqual(("act", "red, C1abcde", "The gate on C1abcdef9 failed: 2 failing tests."), (red["level"], red["value"], red["why"]))
        self.assertEqual(("watch", "3 to push"), level_and_value(lights.main_light(GateState("C1", True, False, 0, 3, ""))))
        self.assertEqual(("ok", "green"), level_and_value(lights.main_light(GateState("C1", True, False, 0, 0, ""))))
        self.assertEqual(("unknown", "unknown"), level_and_value(lights.main_light(None)))

    def test_tokens_today_in_millions(self):
        self.assertEqual(("ok", "41.2M"), level_and_value(lights.tokens_light((50_000_000, 41_200_000, 40_376_000))))
        self.assertIn("41.2M without cache so far today, 81.6M with cache", lights.tokens_light((50_000_000, 41_200_000, 40_376_000))["why"])
        self.assertEqual("unknown", lights.tokens_light(None)["level"])
        self.assertEqual(("watch", "41.2M ios"),
                         level_and_value(lights.tokens_light((0, 41_200_000, 0), {"top": "ios", "over_average": True})))


if __name__ == "__main__":
    unittest.main()
