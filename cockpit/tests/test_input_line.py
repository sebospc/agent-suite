import os
import sys
import tempfile
import unittest

from cockpit.panes.herdr_panes import HerdrPanes
from cockpit.panes.input_line import input_text
from cockpit.source_unavailable import SourceUnavailable

RULE = "─" * 40
# brain's pane on 2026-10-18 while the owner was typing (pg-cpfu HOLD), and an idle reviewer's.
TYPING = "\n".join(["  done", RULE + " agent-brain ─", "❯\xa0first, brain cannot be reached through herdr", "  how annoying!",
                    RULE, "  #3 aux2 | Opus 5.5 1M | effort: med"])
EMPTY = "\n".join(["  done", RULE + " agent-reviewer ─", "❯", RULE, "  #3 aux2 | Sonnet 5.5"])
# brain's pane on 2026-10-19 read with --ansi: the box is empty, the dim text is Claude Code's suggestion (pg-jzva).
GREY = "\x1b[0m\x1b[38;2;136;136;136m"
SUGGESTED = "\n".join(["  done", GREY + RULE, "❯\xa0\x1b[0m\x1b[2mavisame cuando aterrice el fix del cockpit\x1b[0m", GREY + RULE,
                       "  \x1b[0m\x1b[38;2;153;153;153m#1 | \x1b[0m\x1b[38;2;0;153;255mOpus 5.5 1M\x1b[0m"])
TYPED_AFTER_COLOR = "\n".join([RULE, "❯\xa0\x1b[1mfix\x1b[0m this", RULE])


class InputLineTest(unittest.TestCase):
    def test_the_unsent_text_of_the_input_box_is_read_and_an_empty_box_is_empty(self):
        self.assertEqual("first, brain cannot be reached through herdr\n  how annoying!", input_text(TYPING))
        self.assertEqual("", input_text(EMPTY))
        self.assertEqual("", input_text(SUGGESTED))
        self.assertEqual("fix this", input_text(TYPED_AFTER_COLOR))
        self.assertIsNone(input_text("a shell prompt $ "))  # no input box: never typed on a guess

    def test_nothing_is_typed_while_the_input_line_holds_text(self):
        with tempfile.TemporaryDirectory() as folder:
            screen, log = os.path.join(folder, "screen.txt"), os.path.join(folder, "typed.txt")
            herdr = os.path.join(folder, "herdr.py")
            with open(herdr, "w") as handle:
                handle.write("import sys\nif sys.argv[1:3] == ['pane', 'read']:\n    sys.stdout.write(open(%r).read())\n"
                             "else:\n    open(%r, 'a').write(' '.join(sys.argv[1:]) + '\\n')\n" % (screen, log))
            panes = HerdrPanes([sys.executable, herdr], 5)
            with open(screen, "w") as handle:
                handle.write(TYPING)
            with self.assertRaises(SourceUnavailable) as raised:
                panes.type_into("w4:p3", "ANSWER 57484c")
            self.assertIn("holds unsent text", str(raised.exception))
            self.assertFalse(os.path.exists(log))
            with open(screen, "w") as handle:
                handle.write(EMPTY)
            panes.type_into("w4:pG", "TASK pg-x1")
            self.assertEqual("agent prompt w4:pG TASK pg-x1\n", open(log).read())

    def test_a_pane_herdr_does_not_know_as_an_agent_gets_the_text_typed_and_enter(self):
        with tempfile.TemporaryDirectory() as folder:
            screen, log = os.path.join(folder, "screen.txt"), os.path.join(folder, "typed.txt")
            herdr = os.path.join(folder, "herdr.py")
            with open(screen, "w") as handle:
                handle.write(EMPTY)
            with open(herdr, "w") as handle:
                handle.write("import sys\nif sys.argv[1:3] == ['pane', 'read']:\n    sys.stdout.write(open(%r).read())\n"
                             "elif sys.argv[1:3] == ['agent', 'prompt']:\n"
                             "    sys.stderr.write('{\"error\":{\"code\":\"agent_not_found\"}}')\n    sys.exit(1)\n"
                             "else:\n    open(%r, 'a').write(' '.join(sys.argv[1:]) + '\\n')\n" % (screen, log))
            HerdrPanes([sys.executable, herdr], 5).type_into("w9:p1", "/compact")
            self.assertEqual("pane send-text w9:p1 /compact\npane send-keys w9:p1 enter\n", open(log).read())


if __name__ == "__main__":
    unittest.main()
