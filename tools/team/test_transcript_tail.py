# python3 -m unittest discover -s tools -p 'test_transcript_tail.py': hooks read only a transcript's recent end.
import tempfile
import unittest
from pathlib import Path

from transcript_tail import tail_lines


class TranscriptTailTest(unittest.TestCase):
    def test_a_short_transcript_keeps_its_first_line(self):
        path = Path(tempfile.mkdtemp()) / "t.jsonl"
        path.write_text("first\nsecond\n")
        self.assertEqual(tail_lines(str(path), 1000), ["first", "second"])

    def test_a_long_transcript_drops_the_cut_line(self):
        path = Path(tempfile.mkdtemp()) / "t.jsonl"
        path.write_text("a" * 50 + "\nlast\n")
        self.assertEqual(tail_lines(str(path), 10), ["last"])


if __name__ == "__main__":
    unittest.main()
