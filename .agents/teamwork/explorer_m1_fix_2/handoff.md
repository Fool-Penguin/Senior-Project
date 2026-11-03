# Unified Diff Parsing & Patch Application Robustness Investigation Report

**Agent**: `explorer_m1_fix_2` (Exploration & Synthesis Agent)  
**Parent Orchestrator ID**: `cdd4c46b-fa83-40b4-992f-7161af706ca8`  
**Working Directory**: `d:\4th-year\Senior-Project\.agents\teamwork\explorer_m1_fix_2`  
**Timestamp**: 2026-11-01T09:33:00Z  
**Verdict**: Comprehensive Strategy Formulated for Milestone 1 Patch Fix

---

## 1. Observation

### 1.1 Diff Header Corruption in `patches.py`
- **Location**: `codedee/codedee_server/app/api/patches.py`, lines 233–247 (`generate_diff`):
  ```python
  def generate_diff(original: str, patched: str, filename: str) -> str:
      """Generate standard unified diff."""
      orig_lines = original.splitlines(keepends=True)
      patch_lines = patched.splitlines(keepends=True)

      diff_lines = list(
          difflib.unified_diff(
              orig_lines,
              patch_lines,
              fromfile=f"a/{filename}",
              tofile=f"b/{filename}",
              lineterm="",  # <-- Root Cause of Header Corruption
          )
      )
      return "".join(diff_lines) if diff_lines else "--- a/" + filename + "\n+++ b/" + filename + "\n@@ -1 +1 @@\n"
  ```
- **Observed Diff Output**:
  ```
  --- a/sample.py+++ b/sample.py@@ -1,4 +1,4 @@ def get_user(req):
       uid = req.args['id']
  -    query = f"SELECT * FROM users WHERE id = {uid}"
  ...
  ```
- **Impact on Git & Diff Viewers**:
  Running `git apply` with this diff failed with return code 128:
  ```
  error: No valid patches in input (allow with "--allow-empty")
  ```

### 1.2 Flaws in `apply_unified_diff` (`apply.py`)
- **Location**: `codedee/codedee_server/app/api/apply.py`, lines 23–76:
  ```python
  def apply_unified_diff(original_text: str, patch_diff: str) -> Optional[str]:
      orig_lines = original_text.splitlines()
      patch_lines = patch_diff.splitlines()

      result_lines = []
      orig_idx = 0
      in_hunk = False

      i = 0
      while i < len(patch_lines):
          line = patch_lines[i]
          if line.startswith("@@"):
              in_hunk = True
              try:
                  header = line.split("@@")[1].strip()
                  orig_part = header.split()[0]  # e.g. -1,5
                  orig_start = int(orig_part.split(",")[0].replace("-", ""))
                  while orig_idx < orig_start - 1 and orig_idx < len(orig_lines):
                      result_lines.append(orig_lines[orig_idx])
                      orig_idx += 1
              except Exception:
                  pass
              i += 1
              continue

          if in_hunk:
              if line.startswith("+") and not line.startswith("+++"):
                  result_lines.append(line[1:])
              elif line.startswith("-") and not line.startswith("---"):
                  orig_idx += 1
              elif line.startswith(" "):
                  result_lines.append(orig_lines[orig_idx] if orig_idx < len(orig_lines) else line[1:])
                  orig_idx += 1
              elif line.startswith("---") or line.startswith("+++"):
                  pass
              else:
                  if orig_idx < len(orig_lines):
                      result_lines.append(orig_lines[orig_idx])
                      orig_idx += 1
          i += 1

      while orig_idx < len(orig_lines):
          result_lines.append(orig_lines[orig_idx])
          orig_idx += 1

      return "\n".join(result_lines)
  ```
- **Direct Observations & Defects**:
  1. **Silent No-Op on Bogus or Corrupted Diffs**:
     If `patch_diff` has no `@@` header (e.g. `"totally bogus diff string"` or empty string), `in_hunk` remains `False`. The loop ignores every line, and lines 72–74 append all `orig_lines` to `result_lines`. The function returns `original_text` verbatim.
  2. **False Success in `apply_patch`**:
     `apply_patch` (lines 111–157) receives `new_content == original_content`. Tree-sitter parses the original valid code without syntax errors, overwrites the file with its own unpatched content, and returns `ApplyPatchResponse(success=True, message="Patch applied successfully...")`.
  3. **Absence of Context Validation**:
     On lines 57–61, when processing `-` (removal) or `' '` (context) lines, the function performs zero comparison between `line[1:]` and `orig_lines[orig_idx]`. If an offset diff or mismatched patch is supplied, arbitrary lines are removed and substituted without warning.
  4. **Fragile Hunk Header Parsing**:
     `header = line.split("@@")[1].strip()` followed by `orig_part = header.split()[0]` and `.replace("-", "")` fails on single-line diffs without commas (`@@ -1 +1 @@`), zero-line additions (`@@ -0,0 +1,5 @@`), or trailing function descriptors. Any exception is swallowed by `except Exception: pass`, leaving `orig_idx` unaligned while `in_hunk` remains `True`.
  5. **Mishandling of Empty Context Lines and Metadata**:
     In standard diff outputs, blank context lines may appear as empty strings `""` or single spaces `" "`. In current code, `""` falls into `else:`, advancing `orig_idx`. Furthermore, metadata lines like `\ No newline at end of file` also fall into `else:` and advance `orig_idx`, deleting an extra line from the target file.

### 1.3 Starlette Deprecation Warning
- **Location**: `codedee/codedee_server/app/api/apply.py`, line 134:
  ```python
  http_422 = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", status.HTTP_422_UNPROCESSABLE_ENTITY)
  ```
- **Observed Warning**:
  `StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated. Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.`
- **Cause**: In Python, argument expressions are evaluated eagerly before calling `getattr()`. Evaluating `status.HTTP_422_UNPROCESSABLE_ENTITY` triggers the module-level deprecation getter.

---

## 2. Logic Chain

1. **Diff Generation & Representation (`patches.py`)**:
   - Python's `difflib.unified_diff()` controls line terminators for control lines (`---`, `+++`, `@@`) using the `lineterm` parameter (default `"\n"`).
   - Because the input code lines are split with `keepends=True`, they already retain trailing newlines. Setting `lineterm=""` stripped newlines solely from the control headers, causing `--- a/...+++ b/...@@ ... @@` to be concatenated onto a single line.
   - Removing `lineterm=""` restores standard POSIX/GNU unified diff formatting.
   - Independent verification with Git 2.55 confirmed:
     - Diffs generated without `lineterm=""` applied cleanly via `git apply` (exit code 0, 100% content match).
     - Diffs generated with `lineterm=""` were rejected by `git apply` with exit code 128 (`error: No valid patches in input`).

2. **Hunk Header & Context Parsing (`apply.py`)**:
   - A canonical unified diff hunk header is defined by the regular expression:
     ```python
     HUNK_HEADER_RE = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@")
     ```
   - Hunk boundaries and line mapping:
     - `orig_start`: 1-based start line in the original file.
     - `orig_count`: number of lines affected in the original file (defaults to 1 if omitted, e.g. `@@ -1 +1 @@`; equals 0 for pure insertions, e.g. `@@ -0,0 +1,5 @@`).
     - Target index `target_orig_idx`: if `orig_count == 0`, target is `orig_start`; otherwise `max(0, orig_start - 1)`.
     - Lines prior to `target_orig_idx` are copied verbatim. If `target_orig_idx < orig_idx`, hunks are overlapping or out of order (`ValueError`).
   - Line-by-line verification within hunks:
     - `+` (addition): append `line[1:]` to result lines. Does NOT advance `orig_idx`.
     - `-` (deletion): assert `orig_lines[orig_idx]` matches `line[1:]` (supporting `.rstrip()` tolerance for newline/whitespace differences). Advance `orig_idx += 1`.
     - `' '` (context): assert `orig_lines[orig_idx]` matches `line[1:]`. Append `orig_lines[orig_idx]`. Advance `orig_idx += 1`.
     - `""` (empty context line): if `orig_lines[orig_idx] == ""`, match empty line. Advance `orig_idx += 1`.
     - `\` (metadata, e.g., `\ No newline at end of file`): skip without advancing `orig_idx`.
     - Any unrecognized line inside a hunk raises `ValueError(f"Unexpected line in hunk: {line}")`.
   - Completion check:
     - Track `hunks_count`. If `hunks_count == 0`, raise `ValueError("No valid @@ hunk headers found in patch diff.")`.
     - Append any remaining lines from `orig_lines[orig_idx:]`.
     - Ensure trailing newline matches original file convention or diff metadata.

3. **HTTP 422 Error Protocol in `apply_patch`**:
   - When `req.patch_diff` is provided:
     - Wrap `apply_unified_diff()` in a `try...except ValueError as err`.
     - On `ValueError` (empty diff, malformed header, context mismatch, out-of-order hunks): raise `HTTPException(status_code=422, detail=f"Failed to apply patch diff: {str(err)}")`.
     - If `new_content == original_content`: raise `HTTPException(status_code=422, detail="Patch diff produced no changes to the target file.")`.
     - This guarantees that corrupt or ineffective patches never result in false-positive `{"success": true}` responses.
   - When `req.remediated_code` is provided:
     - Use `new_content = req.remediated_code`.
     - Run Tree-sitter CST syntax verification. If syntax errors exist (`has_error` is True), revert from backup and raise `HTTPException(status_code=422, detail="Patch resulted in invalid CST syntax. Changes reverted from backup.")`.
   - When neither `remediated_code` nor `patch_diff` is provided:
     - Raise `HTTPException(status_code=400, detail="Either remediated_code or patch_diff must be supplied to apply patch.")`.
   - Deprecation fix:
     - Directly use `status.HTTP_422_UNPROCESSABLE_CONTENT` (or integer `422`), resolving the Starlette deprecation warning.

---

## 3. Caveats

1. **Adversarial Test Assertion in `challenger_m1_1`**:
   - `challenger_m1_1` created `test_adversarial_m1.py` containing `test_apply_patch_silent_noop_on_bogus_diff`, which asserted `status_code == 200` to document the existing silent no-op bug.
   - Once `apply_patch` is updated to reject bogus diffs with HTTP 422, running `test_adversarial_m1.py` without updating that test's expectation would report a failure. However, the challenger's own handoff report (Finding 1) explicitly mandated returning an error for bogus diffs.
2. **Fuzz Factor in Context Matching**:
   - In GNU patch, a fuzz factor (e.g. searching +/- 2 lines) is sometimes supported. In automated security repair (CodeDEE), strict context matching is preferred to prevent mistakenly mutating surrounding non-vulnerable code.

---

## 4. Conclusion & Recommended Implementation Strategy

### 4.1 Changes to `codedee_server/app/api/patches.py`
In `generate_diff` (lines 233–248), remove `lineterm=""`:

```python
def generate_diff(original: str, patched: str, filename: str) -> str:
    """Generate standard POSIX/GNU unified diff."""
    orig_lines = original.splitlines(keepends=True)
    patch_lines = patched.splitlines(keepends=True)

    diff_lines = list(
        difflib.unified_diff(
            orig_lines,
            patch_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
        )
    )
    return "".join(diff_lines)
```

### 4.2 Changes to `codedee_server/app/api/apply.py`
Replace `apply_unified_diff` and update `apply_patch`:

```python
import re
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status
import tree_sitter

HUNK_HEADER_RE = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@")

def apply_unified_diff(original_text: str, patch_diff: str) -> str:
    """
    Applies a standard unified diff to original text.
    Handles hunk headers (@@ -start,count +start,count @@), context lines,
    deletions (-), and additions (+).
    Raises ValueError on malformed diffs, context mismatches, or invalid hunks.
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

        match = HUNK_HEADER_RE.match(line)
        if match:
            hunks_count += 1
            orig_start = int(match.group(1))
            orig_count = int(match.group(2)) if match.group(2) is not None else 1

            if orig_count == 0:
                target_orig_idx = orig_start
            else:
                target_orig_idx = max(0, orig_start - 1)

            if target_orig_idx < orig_idx:
                raise ValueError(
                    f"Hunk {hunks_count} start line {orig_start} is before current line {orig_idx + 1}."
                )

            while orig_idx < target_orig_idx:
                if orig_idx < len(orig_lines):
                    result_lines.append(orig_lines[orig_idx])
                    orig_idx += 1
                else:
                    raise ValueError(
                        f"Hunk start line {orig_start} exceeds original file length {len(orig_lines)}."
                    )

            i += 1
            while i < len(patch_lines):
                hunk_line = patch_lines[i]
                if hunk_line.startswith("@@"):
                    break

                if hunk_line.startswith("+") and not hunk_line.startswith("+++"):
                    result_lines.append(hunk_line[1:])
                elif hunk_line.startswith("-") and not hunk_line.startswith("---"):
                    if orig_idx >= len(orig_lines):
                        raise ValueError(
                            f"Deletion exceeds file length at hunk {hunks_count}."
                        )
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
                            f"Context line exceeds file length at hunk {hunks_count}."
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
                    result_lines.append("")
                    orig_idx += 1
                elif hunk_line.startswith("\\"):
                    pass
                elif hunk_line.startswith("---") or hunk_line.startswith("+++"):
                    pass
                else:
                    raise ValueError(f"Unexpected line in hunk {hunks_count}: {repr(hunk_line)}")
                i += 1
            continue

        if line.startswith("---") or line.startswith("+++") or line.startswith("diff ") or line.startswith("index "):
            i += 1
            continue

        if hunks_count == 0:
            i += 1
            continue

        i += 1

    if hunks_count == 0:
        raise ValueError("No valid @@ hunk headers found in patch diff.")

    while orig_idx < len(orig_lines):
        result_lines.append(orig_lines[orig_idx])
        orig_idx += 1

    if not result_lines:
        return ""

    res = "\n".join(result_lines)
    if original_text.endswith("\n") or (not original_text and "No newline at end of file" not in patch_diff):
        res += "\n"
    return res
```

In `apply_patch` (around line 111–138):

```python
    # Determine updated content
    new_content: Optional[str] = None

    if req.remediated_code:
        # Direct code substitution
        new_content = req.remediated_code
    elif req.patch_diff:
        # Unified diff application
        try:
            new_content = apply_unified_diff(original_content, req.patch_diff)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Failed to apply patch diff: {str(e)}",
            )
        if new_content == original_content:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Patch diff produced no changes to target file.",
            )

    if new_content is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either remediated_code or patch_diff must be supplied to apply patch.",
        )

    # Post-application Tree-sitter CST syntax verification
    lang = detect_language(str(target_path), new_content)
    parser = get_parser_for_language(lang)
    tree = parser.parse(new_content.encode("utf-8"))

    if tree.root_node.has_error:
        # Revert to backup immediately
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Patch resulted in invalid CST syntax. Changes reverted from backup.",
        )
```

### 4.3 New Pytest Coverage in `codedee_server/tests/test_api.py`
Add tests covering the end-to-end roundtrip and diff error conditions:

1. `test_apply_patch_via_diff_roundtrip(tmp_path)`:
   - Call `POST /api/generate-patches` to produce verified candidate patches.
   - Extract `verified_patches[0]['diff']`.
   - Confirm diff contains proper line breaks (`\n` after `---`, `+++`, and `@@`).
   - Call `POST /api/apply-patch` with `{"target_file": str(target_file), "patch_diff": diff}`.
   - Assert `status_code == 200` and target file on disk matches safe remediated code.
2. `test_apply_patch_malformed_diff_rejected(tmp_path)`:
   - Pass `"totally bogus diff string with no hunks"`.
   - Assert `status_code == 422`.
   - Assert target file content remains untouched.
3. `test_apply_patch_empty_diff_rejected(tmp_path)`:
   - Pass `""`.
   - Assert `status_code == 422`.
4. `test_apply_patch_mismatched_context_rejected(tmp_path)`:
   - Pass a diff that modifies unrelated code.
   - Assert `status_code == 422`.

---

## 5. Verification Method

To verify the proposed implementation strategy:

1. **Verify Standalone Robust Diff Harness (10/10 tests pass)**:
   ```powershell
   python d:\4th-year\Senior-Project\.agents\teamwork\explorer_m1_fix_2\test_robust_diff.py
   ```
   *Expected*: `ALL 10 TESTS PASSED!`

2. **Verify Git Apply Compatibility**:
   ```powershell
   python d:\4th-year\Senior-Project\.agents\teamwork\explorer_m1_fix_2\test_git_apply.py
   ```
   *Expected*: `git apply returncode: 0`, `File content after git apply matches patched: True`.

3. **Post-Implementation Pytest Suite**:
   ```powershell
   pytest d:\4th-year\Senior-Project\codedee\codedee_server\tests -v
   ```
   *Expected*: All tests pass with zero warnings (including `StarletteDeprecationWarning`).
