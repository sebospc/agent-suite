import os
import re
import unittest

PAGE = os.path.join(os.path.dirname(__file__), "..", "page")


def read(name):
    with open(os.path.join(PAGE, name), encoding="utf-8") as handle:
        return handle.read()


class SessionsTableTest(unittest.TestCase):
    """pg-i0zr (owner 2026-10-19): no Account column; the agent cell carries the account number."""

    def test_the_table_has_no_account_column_and_the_agent_cell_shows_the_account(self):
        sessions = read("sections.js").split("function renderSessions", 1)[1].split("\nfunction ", 1)[0]
        head = re.search(r"const head = `(.*?)`;", sessions).group(1)
        self.assertEqual(["Session", "State", "Model", "Context / sweet spot", "Start / limit", "Bead"],
                         re.findall(r"<span[^>]*>([^<]+)</span>", head))
        agent_cell = re.search(r'<span class="agent-cell".*?</span>\$\{r\.account \?[^`]*`[^`]*`', sessions)
        self.assertIsNotNone(agent_cell)
        self.assertIn("${h(r.account)}", agent_cell.group())
        columns = re.search(r"^\.team-row \{[^}]*grid-template-columns: ([^;]+);", read("cockpit.css"), re.M).group(1)
        self.assertEqual(6, len(re.findall(r"minmax\([^)]*\)|\S+", columns)))  # one grid column per header cell


if __name__ == "__main__":
    unittest.main()
