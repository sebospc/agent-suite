import unittest

from cockpit.snapshot.health_lights import GB, coordination_light, disk_light, memory_light, said_light


def process(duplicates=0, outside=0):
    week = {"messages": 12, "median": 3, "outside_format": outside}
    return {"this_week": week, "today_duplicates": duplicates}


class HealthLightsTest(unittest.TestCase):
    def test_disk_follows_the_teams_30_gb_floor(self):
        folders = {"transcripts": 4 * GB}
        self.assertEqual(("act", "20 GB free"), (lambda l: (l["level"], l["value"]))(disk_light({"volume": "/v", "free": 20 * GB, "total": 500 * GB, "folders": folders}, 30, 45)))
        self.assertEqual("watch", disk_light({"volume": "/v", "free": 40 * GB, "total": 500 * GB, "folders": {}}, 30, 45)["level"])
        self.assertIn("transcripts 4.0 GB", disk_light({"volume": "/v", "free": 90 * GB, "total": 500 * GB, "folders": folders}, 30, 45)["why"])
        self.assertEqual("unknown", disk_light(None, 30, 45, "no volume")["level"])

    def test_memory_watches_a_start_over_its_roles_usual_and_unsaved_notes(self):
        rows = [{"name": "ios", "state": "idle", "notes_saved": True, "start_load": 72_000, "start_over": True},
                {"name": "ai", "state": "idle", "notes_saved": False, "start_load": 30_000, "start_over": False}]
        light = memory_light(rows)
        self.assertEqual(("watch", "start ~72k"), (light["level"], light["value"]))
        self.assertIn("ios starts heavier than usual; ai: notes not saved", light["why"])
        self.assertEqual("ok", memory_light([dict(rows[1], notes_saved=True)])["level"])
        # A busy session is mid-turn and may still save, so only an idle one is judged.
        self.assertEqual("ok", memory_light([dict(rows[1], state="busy")])["level"])

    def test_coordination_acts_on_broken_receipts(self):
        self.assertEqual("act", coordination_light(process(), [{"id": "receipts"}])["level"])
        self.assertEqual(("watch", "1 issue"), (lambda l: (l["level"], l["value"]))(coordination_light(process(duplicates=1), [])))
        self.assertEqual(("ok", "in order"), (lambda l: (l["level"], l["value"]))(coordination_light(process(), [])))

    def test_a_saved_claim_with_no_id_is_not_a_session_that_named_a_missing_id(self):
        light = said_light({"not_in_decisions": [], "without_id": {"ios": 1}, "blocks": 0}, [{"id": "unsaved-ios", "text": "ios said saved"}])
        self.assertEqual("1 gap", light["value"])
        self.assertNotIn("missing id", light["why"])
        named = said_light({"not_in_decisions": [], "without_id": {}, "blocks": 0}, [{"id": "missing-ios", "text": 'ios named pg-x ("closed pg-x", 14:03) in a reply today, and none exists'}])
        self.assertIn('ios named pg-x ("closed pg-x", 14:03)', named["why"])

    def test_said_vs_saved_counts_every_gap(self):
        saved = {"not_in_decisions": [{"id": "x"}], "without_id": {"ai": 2}, "blocks": 1}
        light = said_light(saved, [{"id": "missing-ios"}])
        self.assertEqual(("watch", "4 gaps"), (light["level"], light["value"]))
        self.assertEqual("ok", said_light({"not_in_decisions": [], "without_id": {}, "blocks": 0}, [])["level"])


class NoBeadNamedTest(unittest.TestCase):
    def test_messages_that_name_no_bead_say_so_instead_of_a_0_median(self):
        from cockpit.snapshot.health_lights import coordination_light
        week = {"messages": 32, "beads": 0, "median": 0, "worst": 0, "duplicates": 0, "outside_format": 0}
        light = coordination_light({"this_week": week, "today_duplicates": 0}, [])
        self.assertIn("32 messages this week, none names a bead", str(light))
