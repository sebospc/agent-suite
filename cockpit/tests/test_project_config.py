import json
import os
import shutil
import tempfile
import unittest

from cockpit.composition import project_config, team_and_thresholds
from cockpit.project_config.config_error import ConfigError
from cockpit.project_config.project_config import load_config
from cockpit.team import Team
from tests.builders import FIRST_PROJECT, FIXTURES, ROOT
from tests.test_snapshot import builder

STEP5 = os.path.join(FIXTURES, "step5_config")  # config/paths.json and team_sessions.json as they were at f3df56f


def step5(name: str) -> dict:
    with open(os.path.join(STEP5, name), encoding="utf-8") as handle:
        return json.load(handle)


def without_notes(raw: dict) -> dict:
    return {key: value for key, value in raw.items() if not key.startswith("_")}


class AcmeConfigTest(unittest.TestCase):
    def test_acme_reads_the_same_paths_port_and_team_as_the_step5_files(self):
        config = project_config(FIRST_PROJECT)
        old_paths = without_notes(step5("paths.json"))
        self.assertEqual(old_paths.pop("port"), config["port"])
        new_paths = without_notes(config["paths"])
        self.assertEqual("docs/DECISIONS.md", new_paths.pop("decision_log"))  # added after step 5, the old fixed path
        self.assertEqual(old_paths["board_dir"], new_paths.pop("milestone_dir"))  # dod.json and goal.json sat in board_dir
        self.assertEqual(old_paths, new_paths)
        # The step 5 files predate the session prefix keys, which only the project config carries.
        team = {key: value for key, value in config["team"].items() if key not in ("session_prefix", "legacy_prefixes", "decisions_writer")}
        self.assertEqual(without_notes(step5("team_sessions.json")), without_notes(team))

    def test_the_snapshot_for_the_same_inputs_is_equal_with_the_step5_team_and_the_new_config(self):
        old = step5("team_sessions.json")
        old_team = Team(old["roles"], old["coordinating"], old["known_holders"])
        new_team, _ = team_and_thresholds(project_config(FIRST_PROJECT))
        before, after = builder(), builder()
        before.team, after.team = old_team, new_team
        self.assertEqual(json.dumps(before.build(), sort_keys=True), json.dumps(after.build(), sort_keys=True))


class LoadConfigTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder)
        self.global_path = os.path.join(self.folder, "global.json")
        self.complete = project_config(FIRST_PROJECT)

    def write(self, path: str, raw) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(raw, handle)

    def load(self, project: dict, global_layer=None) -> dict:
        self.write(os.path.join(self.folder, ".cockpit.json"), project)
        if global_layer is not None:
            self.write(self.global_path, global_layer)
        return load_config(self.folder, self.global_path)

    def assertFailsWith(self, line: str, project: dict, global_layer=None):
        with self.assertRaises(ConfigError) as caught:
            self.load(project, global_layer)
        self.assertIn(line, str(caught.exception))

    def test_project_and_suite_in_a_path_are_their_folders(self):
        project = dict(self.complete, paths=dict(self.complete["paths"], repo="{project}", repos=["{project}", "~/x"],
                                                 grill_server="{suite}/tools"))
        merged = self.load(project)
        self.assertEqual(os.path.abspath(self.folder), merged["paths"]["repo"])
        self.assertTrue(os.path.isfile(os.path.join(merged["paths"]["grill_server"], "install_team.py")))
        self.assertEqual([os.path.abspath(self.folder), "~/x"], merged["paths"]["repos"])

    def test_the_project_file_wins_over_the_global_one_key_by_key(self):
        machine = {"port": 9000, "paths": {key: self.complete["paths"][key] for key in ("transcripts", "node")}}
        project = dict(self.complete, paths={k: v for k, v in self.complete["paths"].items() if k != "transcripts"})
        project["paths"]["node"] = "/usr/local/bin/node"
        merged = self.load(project, machine)
        self.assertEqual(self.complete["port"], merged["port"])
        self.assertEqual(self.complete["paths"]["transcripts"], merged["paths"]["transcripts"])
        self.assertEqual("/usr/local/bin/node", merged["paths"]["node"])

    def test_an_unknown_key_fails_at_start_naming_its_file_and_key(self):
        self.assertFailsWith("global.json: paths.bord_dir is not a known key", self.complete, {"paths": {"bord_dir": "~/x"}})

    def test_a_wrong_type_fails_at_start_with_what_was_expected(self):
        broken = dict(self.complete, team=dict(self.complete["team"], roles="brain"))
        self.assertFailsWith(".cockpit.json: team.roles must be a list of strings, got a string", broken)
        self.assertFailsWith("port must be a whole number, got true or false", dict(self.complete, port=True))

    def test_a_missing_key_fails_and_a_missing_global_file_does_not(self):
        self.assertEqual(self.complete["port"], self.load(self.complete)["port"])
        self.assertFailsWith("paths.repo is missing", dict(self.complete, paths=without_key(self.complete["paths"], "repo")))

    def test_a_project_without_its_file_fails_with_where_to_get_one(self):
        with self.assertRaises(ConfigError) as caught:
            load_config(self.folder, self.global_path)
        self.assertIn("not found; the cockpit-setup skill writes it", str(caught.exception))


def without_key(raw: dict, key: str) -> dict:
    return {k: v for k, v in raw.items() if k != key}


if __name__ == "__main__":
    unittest.main()
