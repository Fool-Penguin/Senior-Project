"""
Verification that with the proposed fix logic:
1. Diff has clean standard header lines with newlines.
2. Applying the diff updates the file on disk to parameterized query.
3. Bogus diffs raise ValueError / HTTP 422.
"""

import difflib
import re
from pathlib import Path

VULN_PYTHON_SNIPPET = """def login_user(request):
    username = request.args.get('username')
    cursor = db.cursor()
    query = f"SELECT id, role, email FROM accounts WHERE username = '{username}'"
    cursor.execute(query)
    return cursor.fetchall()
"""

PATCHED_CODE = """def login_user(request):
    username = request.args.get('username')
    cursor = db.cursor()
    query = "SELECT id, role, email FROM accounts WHERE username = %s"
    cursor.execute(query, (username,))
    return cursor.fetchall()
"""

# Fixed generate_diff
def generate_diff_fixed(original: str, patched: str, filename: str) -> str:
    orig_lines = original.splitlines(keepends=True)
    patch_lines = patched.splitlines(keepends=True)
    diff_lines = list(
        difflib.unified_diff(
            orig_lines,
            patch_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            # lineterm defaults to "\n"
        )
    )
    return "".join(diff_lines)

HUNK_HEADER_RE = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@")

def apply_unified_diff_fixed(original_text: str, patch_diff: str) -> str:
    if not patch_diff or not patch_diff.strip():
        raise ValueError("Empty or whitespace-only diff.")

    orig_lines = original_text.splitlines()
    patch_lines = patch_diff.splitlines()
    result_lines = []
    orig_idx = 0
    hunks_count = 0
    i = 0

    while i < len(patch_lines):
        line = patch_lines[i]
        match = HUNK_HEADER_RE.match(line)
        if match:
            hunks_count += 1
            orig_start = int(match.group(1))
            orig_count = int(match.group(2)) if match.group(2) is not None else 1
            target_orig_idx = max(0, orig_start - 1) if orig_count > 0 else orig_start

            while orig_idx < target_orig_idx and orig_idx < len(orig_lines):
                result_lines.append(orig_lines[orig_idx])
                orig_idx += 1

            i += 1
            while i < len(patch_lines):
                hunk_line = patch_lines[i]
                if hunk_line.startswith("@@"):
                    break
                if hunk_line.startswith("+") and not hunk_line.startswith("+++"):
                    result_lines.append(hunk_line[1:])
                elif hunk_line.startswith("-") and not hunk_line.startswith("---"):
                    orig_idx += 1
                elif hunk_line.startswith(" "):
                    if orig_idx < len(orig_lines):
                        result_lines.append(orig_lines[orig_idx])
                        orig_idx += 1
                elif hunk_line.startswith("---") or hunk_line.startswith("+++"):
                    pass
                i += 1
            continue
        i += 1

    if hunks_count == 0:
        raise ValueError("No valid @@ hunk headers found in patch diff.")

    while orig_idx < len(orig_lines):
        result_lines.append(orig_lines[orig_idx])
        orig_idx += 1

    res = "\n".join(result_lines)
    if original_text.endswith("\n"):
        res += "\n"
    return res

def test_fixed_roundtrip_logic(tmp_path):
    target_file = tmp_path / "app.py"
    target_file.write_text(VULN_PYTHON_SNIPPET, encoding="utf-8")

    diff = generate_diff_fixed(VULN_PYTHON_SNIPPET, PATCHED_CODE, "app.py")
    assert diff.startswith("--- a/app.py\n")
    assert "\n+++ b/app.py\n" in diff
    assert "\n@@ -1,6 +1,6 @@\n" in diff

    updated = apply_unified_diff_fixed(VULN_PYTHON_SNIPPET, diff)
    target_file.write_text(updated, encoding="utf-8")

    disk_content = target_file.read_text(encoding="utf-8")
    assert 'f"SELECT' not in disk_content
    assert "%s" in disk_content
    assert "cursor.execute(query, (username,))" in disk_content

def test_fixed_bogus_diff_raises():
    import pytest
    with pytest.raises(ValueError, match="No valid @@ hunk headers"):
        apply_unified_diff_fixed(VULN_PYTHON_SNIPPET, "BOGUS DIFF")
