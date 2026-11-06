import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import courier
import task_queue

CONFIG = {"session_prefix": "agent-", "courier": {"idle_minutes": 10, "cooldown_minutes": 30,
                                                  "always_watched": ["coordinator"]}}


def board():
    return {"tasks": [], "waiting_owner": [], "queue": []}


def agents(**status):
    return {name.replace("_", "-"): {"name": name, "pane_id": f"p-{name}", "agent_status": s} for name, s in status.items()}


class CourierTest(unittest.TestCase):
    def test_an_idle_free_session_is_handed_its_next_ticket_at_once(self):
        b = board()
        task_queue.add(b, "agent-ios", ["t-1"])
        actions = courier.decide(b, CONFIG, agents(agent_ios="idle"), {}, 0, on_a_dialog=lambda pane: False)
        self.assertEqual([("prompt", "agent-ios", "p-agent_ios", courier.HAND.format(bead="t-1"))], actions)
        self.assertEqual("t-1", task_queue.holder(b, "agent-ios"))

    def test_a_holder_is_nudged_after_idle_minutes_then_not_again_inside_the_cooldown(self):
        b, state = board(), {}
        task_queue.start(b, "t-1", ["agent-ai"])
        live = agents(agent_ai="idle", agent_coordinator="working")
        self.assertEqual([], courier.decide(b, CONFIG, live, state, 0, on_a_dialog=lambda pane: False))
        nudged = courier.decide(b, CONFIG, live, state, 11 * 60, on_a_dialog=lambda pane: False)
        self.assertEqual([("prompt", "agent-ai")], [a[:2] for a in nudged])
        self.assertEqual([], courier.decide(b, CONFIG, live, state, 20 * 60, on_a_dialog=lambda pane: False))

    def test_a_session_on_a_dialog_gets_a_notification_and_no_handed_ticket(self):
        b, state = board(), {}
        task_queue.add(b, "agent-ios", ["t-1"])
        self.assertEqual([], courier.decide(b, CONFIG, agents(agent_ios="blocked"), state, 0))
        self.assertIsNone(task_queue.holder(b, "agent-ios"))
        task_queue.start(b, "t-2", ["agent-ai"])
        courier.decide(b, CONFIG, agents(agent_ai="idle"), state, 0, on_a_dialog=lambda pane: True)
        actions = courier.decide(b, CONFIG, agents(agent_ai="idle"), state, 11 * 60, on_a_dialog=lambda pane: True)
        self.assertEqual("notify", actions[0][0])


if __name__ == "__main__":
    unittest.main()
