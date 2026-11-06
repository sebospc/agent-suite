# The GO-REQ "guards" line (mb-5558): slips reviewers caught by hand more than once, read from the patch, no test run.
import re

FILE_HEADER = re.compile(r"^diff --git a/\S+ b/(\S+)$")
# In two parts each, so this file's own patch never trips its own guard.
SKIP_MARKERS = (r"@unittest\.sk" r"ip", r"unittest\.sk" r"ip(?:If|Unless)?\(", r"\.sk" r"ipTest\(",
                r"pytest\.mark\.(?:sk" r"ip|xf" r"ail)", r"#\[ign" r"ore\]", r"XCTSk" r"ip", r"@Ign" r"ore\b", r"@Disab" r"led\b")
SKIP_MARKER = re.compile("|".join(SKIP_MARKERS))
TEST_DEFINITION = re.compile(r"^\s*(?:def test_|func test[A-Z_]|@Test\b|#\[test\])")


def changed_lines(patch_text: str):
    # Only lines inside a hunk: a file header such as "--- a/x" is not a removed line.
    path, in_hunk = None, False
    for line in patch_text.splitlines():
        header = FILE_HEADER.match(line)
        if header:
            path, in_hunk = header[1], False
        elif line.startswith("@@"):
            in_hunk = True
        elif in_hunk and line[:1] in ("+", "-"):
            yield line[0], path, line[1:]


def problems(patch_text: str, has_mutants: bool) -> list[str]:
    lines = list(changed_lines(patch_text))
    skips = [f"new skip marker in {path}: {text.strip()[:60]}" for sign, path, text in lines
             if sign == "+" and SKIP_MARKER.search(text)]
    added = sum(1 for sign, _, text in lines if sign == "+" and TEST_DEFINITION.match(text))
    removed = sum(1 for sign, _, text in lines if sign == "-" and TEST_DEFINITION.match(text))
    found = skips
    if added < removed:
        found.append(f"test count drops by {removed - added} ({added} added, {removed} removed)")
    if added > removed and not has_mutants:
        found.append(f"{added - removed} new tests and no --mutants line: show each one failing without the fix")
    return found


def guards_text(patch_text: str, has_mutants: bool) -> tuple[str, bool]:
    found = problems(patch_text, has_mutants)
    return ("red: " + "; ".join(found), True) if found else ("ok", False)
