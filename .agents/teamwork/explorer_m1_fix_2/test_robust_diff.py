import re
from typing import Optional, List

HUNK_HEADER_RE = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@")

def apply_unified_diff_robust(original_text: str, patch_diff: str) -> str:
    """
    Robust unified diff application complying with GNU/Git unified diff standards.
    Raises ValueError on malformed diffs, mismatched context, or out-of-bounds hunks.
    """
    if not patch_diff or not patch_diff.strip():
        raise ValueError("Patch diff is empty or whitespace-only.")

    orig_lines = original_text.splitlines()
    patch_lines = patch_diff.splitlines()

    result_lines: List[str] = []
    orig_idx = 0
    hunks_count = 0
    i = 0

    while i < len(patch_lines):
        line = patch_lines[i]

        # Check for hunk header
        match = HUNK_HEADER_RE.match(line)
        if match:
            hunks_count += 1
            orig_start = int(match.group(1))
            orig_count = int(match.group(2)) if match.group(2) is not None else 1
            new_start = int(match.group(3))
            new_count = int(match.group(4)) if match.group(4) is not None else 1

            # Determine 0-based target index in orig_lines
            if orig_count == 0:
                target_orig_idx = orig_start
            else:
                target_orig_idx = max(0, orig_start - 1)

            if target_orig_idx < orig_idx:
                raise ValueError(
                    f"Hunk {hunks_count} start line {orig_start} is before current line {orig_idx + 1}."
                )

            # Copy unchanged lines up to hunk start
            while orig_idx < target_orig_idx:
                if orig_idx < len(orig_lines):
                    result_lines.append(orig_lines[orig_idx])
                    orig_idx += 1
                else:
                    raise ValueError(
                        f"Hunk start line {orig_start} exceeds file line count {len(orig_lines)}."
                    )

            # Process lines in hunk
            i += 1
            while i < len(patch_lines):
                hunk_line = patch_lines[i]
                if hunk_line.startswith("@@"):
                    # Next hunk starts
                    break

                if hunk_line.startswith("+") and not hunk_line.startswith("+++"):
                    result_lines.append(hunk_line[1:])
                elif hunk_line.startswith("-") and not hunk_line.startswith("---"):
                    if orig_idx >= len(orig_lines):
                        raise ValueError(
                            f"Deletion line exceeds original file length at hunk {hunks_count}."
                        )
                    # Verify context match
                    expected = hunk_line[1:]
                    actual = orig_lines[orig_idx]
                    if actual != expected and actual.rstrip() != expected.rstrip():
                        raise ValueError(
                            f"Deletion mismatch at line {orig_idx + 1}: expected '{expected}', found '{actual}'."
                        )
                    orig_idx += 1
                elif hunk_line.startswith(" "):
                    if orig_idx >= len(orig_lines):
                        raise ValueError(
                            f"Context line exceeds original file length at hunk {hunks_count}."
                        )
                    expected = hunk_line[1:]
                    actual = orig_lines[orig_idx]
                    if actual != expected and actual.rstrip() != expected.rstrip():
                        raise ValueError(
                            f"Context mismatch at line {orig_idx + 1}: expected '{expected}', found '{actual}'."
                        )
                    result_lines.append(actual)
                    orig_idx += 1
                elif hunk_line == "" and orig_idx < len(orig_lines) and orig_lines[orig_idx] == "":
                    # Empty context line
                    result_lines.append("")
                    orig_idx += 1
                elif hunk_line.startswith("\\"):
                    # \ No newline at end of file
                    pass
                elif hunk_line.startswith("---") or hunk_line.startswith("+++"):
                    # Diff header inside hunk stream? Ignore
                    pass
                else:
                    raise ValueError(f"Unexpected line in hunk {hunks_count}: {repr(hunk_line)}")
                i += 1
            continue

        # Header lines before any hunk
        if line.startswith("---") or line.startswith("+++") or line.startswith("diff ") or line.startswith("index "):
            i += 1
            continue

        # If not in hunk and unrecognized line before first hunk
        if hunks_count == 0:
            i += 1
            continue

        i += 1

    if hunks_count == 0:
        raise ValueError("No valid @@ hunk headers found in patch diff.")

    # Copy remaining lines
    while orig_idx < len(orig_lines):
        result_lines.append(orig_lines[orig_idx])
        orig_idx += 1

    if not result_lines:
        return ""

    res = "\n".join(result_lines)
    if original_text.endswith("\n") or (not original_text and "No newline at end of file" not in patch_diff):
        res += "\n"
    return res


# Test harness
import difflib

orig = """def get_user(req):
    uid = req.args['id']
    query = f"SELECT * FROM users WHERE id = {uid}"
    cursor.execute(query)
"""

patched = """def get_user(req):
    uid = req.args['id']
    query = "SELECT * FROM users WHERE id = %s"
    cursor.execute(query, (uid,))
"""

# 1. Standard diff
clean_diff = "".join(difflib.unified_diff(
    orig.splitlines(True), patched.splitlines(True), fromfile="a/f.py", tofile="b/f.py"
))
res = apply_unified_diff_robust(orig, clean_diff)
assert res == patched, "Clean diff failed!"
print("Test 1 (clean diff): PASSED")

# 2. Bogus diff
try:
    apply_unified_diff_robust(orig, "totally bogus diff string with no hunks")
    assert False, "Bogus diff should have raised ValueError!"
except ValueError as e:
    print(f"Test 2 (bogus diff caught): PASSED ({e})")

# 3. Empty diff
try:
    apply_unified_diff_robust(orig, "")
    assert False, "Empty diff should have raised ValueError!"
except ValueError as e:
    print(f"Test 3 (empty diff caught): PASSED ({e})")

# 4. Corrupted hunk header
try:
    corrupt_diff = "--- a/f.py\n+++ b/f.py\n@@ -INVALID_HUNK_HEADER @@\n+def foo():\n"
    apply_unified_diff_robust(orig, corrupt_diff)
    assert False, "Corrupt header should have raised ValueError!"
except ValueError as e:
    print(f"Test 4 (corrupt hunk header caught): PASSED ({e})")

# 5. Mismatched context
mismatched_diff = """--- a/f.py
+++ b/f.py
@@ -1,4 +1,4 @@
 def wrong_function_name(req):
     uid = req.args['id']
-    query = f"SELECT * FROM users WHERE id = {uid}"
+    query = "SELECT * FROM users WHERE id = %s"
     cursor.execute(query)
"""
try:
    apply_unified_diff_robust(orig, mismatched_diff)
    assert False, "Mismatched context should have raised ValueError!"
except ValueError as e:
    print(f"Test 5 (mismatched context caught): PASSED ({e})")

# 6. Multi-hunk diff
orig_multi = "\n".join([f"line_{i} = {i}" for i in range(1, 30)]) + "\n"
patched_multi = orig_multi.replace("line_2 = 2", "line_2 = 200").replace("line_25 = 25", "line_25 = 2500")
multi_diff = "".join(difflib.unified_diff(
    orig_multi.splitlines(True), patched_multi.splitlines(True), fromfile="a/f.py", tofile="b/f.py"
))
res_multi = apply_unified_diff_robust(orig_multi, multi_diff)
assert res_multi == patched_multi, "Multi-hunk failed!"
print("Test 6 (multi-hunk diff): PASSED")

# 7. No changes diff
no_change_diff = "".join(difflib.unified_diff(
    orig.splitlines(True), orig.splitlines(True), fromfile="a/f.py", tofile="b/f.py"
))
try:
    apply_unified_diff_robust(orig, no_change_diff)
    assert False, "No change diff should raise ValueError (no hunks)!"
except ValueError as e:
    print(f"Test 7 (no-change diff caught): PASSED ({e})")

# 8. Empty original file with addition
orig_empty = ""
patched_new = "line 1\nline 2\n"
new_diff = "".join(difflib.unified_diff(
    orig_empty.splitlines(True), patched_new.splitlines(True), fromfile="a/f.py", tofile="b/f.py"
))
res_new = apply_unified_diff_robust(orig_empty, new_diff)
assert res_new == patched_new, f"Empty orig failed: {repr(res_new)}"
print("Test 8 (empty orig): PASSED")

# 9. Delete entire file content
orig_to_del = "line 1\nline 2\n"
patched_empty = ""
del_diff = "".join(difflib.unified_diff(
    orig_to_del.splitlines(True), patched_empty.splitlines(True), fromfile="a/f.py", tofile="b/f.py"
))
res_del = apply_unified_diff_robust(orig_to_del, del_diff)
assert res_del == patched_empty, f"Delete all failed: {repr(res_del)}"
print("Test 9 (delete all): PASSED")

# 10. Single line hunk (no comma)
orig_single = "line 1\n"
patched_single = "line 1 modified\n"
single_diff = "".join(difflib.unified_diff(
    orig_single.splitlines(True), patched_single.splitlines(True), fromfile="a/f.py", tofile="b/f.py"
))
res_single = apply_unified_diff_robust(orig_single, single_diff)
assert res_single == patched_single, f"Single line failed: {repr(res_single)}"
print("Test 10 (single line): PASSED")

print("\nALL 10 TESTS PASSED!")
