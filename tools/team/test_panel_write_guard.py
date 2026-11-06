# python3 -m unittest discover -s tools -p 'test_panel_write_guard.py': only the panel tool writes the panel (mb-5558).
import os
import unittest

from panel_write_guard import PANEL, verdict


def bash(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


class PanelWriteGuardTest(unittest.TestCase):
    def test_an_edit_or_write_of_the_panel_is_refused(self):
        self.assertIsNotNone(verdict({"tool_name": "Edit", "tool_input": {"file_path": PANEL}}))
        self.assertIsNotNone(verdict({"tool_name": "Write", "tool_input": {"file_path": PANEL}}))
        self.assertIsNone(verdict({"tool_name": "Write", "tool_input": {"file_path": os.path.dirname(PANEL) + "/x.json"}}))

    def test_a_shell_write_of_the_panel_is_refused(self):
        self.assertIsNotNone(verdict(bash("python3 -c \"import json;p=json.load(open('panel.json'));json.dump(p,open('panel.json','w'))\"")))
        self.assertIsNotNone(verdict(bash("sed -i '' s/a/b/ ~/.agent-board/panel.json")))
        self.assertIsNotNone(verdict(bash("python3 -c \"import json; p='panel.json'; f=open(p, mode); json.dump(d, f)\"")))
        self.assertIsNotNone(verdict(bash("cat new.json > ~/.agent-board/panel.json")))

    def test_reading_the_panel_and_the_panel_tool_go_through(self):
        self.assertIsNone(verdict(bash("grep -n a351d8 ~/.agent-board/panel.json 2>/dev/null")))
        self.assertIsNone(verdict(bash("python3 -c \"import json;print(json.load(open('panel.json'))['asks'])\"")))
        self.assertIsNone(verdict(bash("cp ~/.agent-board/panel.json /tmp/panel-copy.json")))
        self.assertIsNone(verdict(bash("python3 ~/.agent-board/ask_owner.py add \"cp a panel.json by hand?\" --kind design")))


if __name__ == "__main__":
    unittest.main()
