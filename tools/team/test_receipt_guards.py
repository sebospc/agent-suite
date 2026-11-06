# python3 -m unittest discover -s tools -p 'test_receipt_guards.py': the GO-REQ guards read from a patch (mb-5558).
import unittest

from receipt_guards import guards_text, problems

SKIP = "@unittest." + "skip"  # split so this file's own patch carries no marker


def patch_of(path: str, *lines: str) -> str:
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -1,2 +1,2 @@\n" + "\n".join(lines) + "\n"


class ReceiptGuardsTest(unittest.TestCase):
    def test_a_patch_with_no_test_change_is_ok(self):
        self.assertEqual(guards_text(patch_of("ai/core/x.py", "-a = 1", "+a = 2"), False), ("ok", False))

    def test_a_new_skip_marker_is_red_and_names_its_file(self):
        found = problems(patch_of("ai/tests/test_x.py", f"+    {SKIP}('slow')", "     def test_a(self):"), True)
        self.assertEqual(len(found), 1)
        self.assertIn("ai/tests/test_x.py", found[0])

    def test_fewer_tests_after_the_patch_is_red(self):
        found = problems(patch_of("core/tests/a.rs", "-#[test]", "-fn a() {}", "-#[test]", "+#[test]"), True)
        self.assertEqual(found, ["test count drops by 1 (1 added, 2 removed)"])

    def test_a_new_test_needs_a_mutant_line(self):
        patch = patch_of("android/app/T.kt", "+    @Test", "+    fun aNewRule() {}")
        self.assertIn("1 new tests and no --mutants line", guards_text(patch, False)[0])
        self.assertEqual(guards_text(patch, True), ("ok", False))

    def test_a_renamed_test_counts_as_no_new_test(self):
        patch = patch_of("ios/T.swift", "-    func testOldName() {", "+    func testNewName() {")
        self.assertEqual(problems(patch, False), [])

    def test_file_headers_are_not_removed_or_added_lines(self):
        name = "ios/XCTSk" + "ipHelper.swift"
        patch = f"diff --git a/{name} b/{name}\n--- a/{name}\n+++ b/{name}\n@@ -1 +1 @@\n-a\n+b\n"
        self.assertEqual(problems(patch, False), [])


if __name__ == "__main__":
    unittest.main()
