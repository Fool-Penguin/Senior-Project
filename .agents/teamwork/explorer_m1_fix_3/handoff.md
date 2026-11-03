# Milestone 1 Fix Strategy Report: Test Design and Verification Architecture

**Agent**: `explorer_m1_fix_3` (Test Engineering & Verification Investigator)  
**Parent Orchestrator ID**: `cdd4c46b-fa83-40b4-992f-7161af706ca8`  
**Working Directory**: `d:\4th-year\Senior-Project\.agents\teamwork\explorer_m1_fix_3`  
**Target Codebase**: `d:\4th-year\Senior-Project\codedee\codedee_server\`  
**Timestamp**: 2026-11-01T09:32:00Z  
**Verdict**: **RECOMMEND COMPREHENSIVE TEST SUITE EXTENSION FOR DIFF APPLICATION AND ERROR HANDLING**

---

## 1. Observation

### 1.1 Root Test Gap in Existing API Test Suite (`codedee_server/tests/test_api.py`)
Direct inspection of `codedee/codedee_server/tests/test_api.py` lines 243–300 revealed why the upstream test suite did not catch the unified diff generation and application breakdown:

```python
# Lines 246-271:
def test_apply_patch_success(tmp_path):
    """Verify POST /api/apply-patch modifies target file, creates .bak, and verifies syntax."""
    target_file = tmp_path / "app_login.py"
    target_file.write_text(VULN_PYTHON_SNIPPET, encoding="utf-8")

    payload = {
        "target_file": str(target_file),
        "patch_id": "patch_cand_01",
        "remediated_code": SAFE_PYTHON_SNIPPET,  # <-- BYPASSES UNIFIED DIFF ENTIRELY
    }
    response = client.post("/api/apply-patch", json=payload)
    ...
```

- **Observation 1**: `test_apply_patch_success` tested ONLY direct code replacement using `remediated_code`. There was **zero test coverage** for applying a patch using `patch_diff`.
- **Observation 2**: There was **zero integration test coverage** connecting `POST /api/generate-patches` to `POST /api/apply-patch` in a full end-to-end roundtrip.
- **Observation 3**: There was **no test asserting negative validation** for malformed, corrupt, or unmatchable diffs in `POST /api/apply-patch`. When an invalid diff was supplied, the server silently returned `HTTP 200` with `{"success": true}` while leaving the vulnerable code on disk untouched.

### 1.2 Empirical Failure Demonstration via Standalone Prototype Test
To verify the exact failure conditions prior to proposing code edits, a standalone test suite (`test_prototype.py`) was executed against the active server implementation.

**Command Executed**:
```powershell
pytest d:\4th-year\Senior-Project\.agents\teamwork\explorer_m1_fix_3\test_prototype.py -v
```

**Verbatim Output**:
```
collected 2 items

.agents/teamwork/explorer_m1_fix_3/test_prototype.py::test_roundtrip_prototype FAILED [ 50%]
.agents/teamwork/explorer_m1_fix_3/test_prototype.py::test_malformed_diff_prototype FAILED [100%]

================================== FAILURES ===================================
__________________________ test_roundtrip_prototype ___________________________
>       assert "\n+++ " in diff, f"Diff header must have newline before '+++ ', got: {diff[:100]}"
E       AssertionError: Diff header must have newline before '+++ ', got: --- a/C:\Users\Ongsa\AppData\Local\Temp\pytest-of-Ongsa\pytest-31\test_roundtrip_prototype0\vulnerab
E       assert '\n+++ ' in '--- a/C:\\Users\\...\\vulnerable_login.py+++ b/C:\\Users\\...\\vulnerable_login.py@@ -1,6 +1,6 @@ def login_user(request):\n...'

________________________ test_malformed_diff_prototype ________________________
>       assert response_bogus.status_code == 422
E       assert 200 == 422
E        +  where 200 = <Response [200 OK]>.status_code
```

- **Failure 1**: Diff header has no newline breaks (`--- a/...+++ b/...@@ ... @@`) because `difflib.unified_diff(..., lineterm="")` stripped line terminators from control lines.
- **Failure 2**: When a malformed diff without hunks is submitted to `POST /api/apply-patch`, the endpoint returns `HTTP 200` with `{"success": true}` instead of `HTTP 422 Unprocessable Content`. The file on disk remains completely unpatched.

### 1.3 Starlette Deprecation Warning
When running `pytest d:\4th-year\Senior-Project\codedee\codedee_server\tests -v`, the following warning was triggered at line 134 of `app/api/apply.py`:
```
StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated. Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.
```
Accessing `status.HTTP_422_UNPROCESSABLE_ENTITY` triggers a runtime warning in Starlette/FastAPI on modern Python.

---

## 2. Logic Chain

1. **Why an End-to-End Roundtrip Test is Mandatory**:
   - The user workflow and VS Code extension architecture (R4 / F22 in `PROJECT.md`) operates as follows:
     1. User clicks `[Request AI Patches]` -> VS Code calls `POST /api/generate-patches`.
     2. Backend generates verified patches containing a `diff` string.
     3. VS Code displays the `diff` in `vscode.diff`.
     4. User clicks `[Apply Patch]` -> VS Code sends `{"target_file": ..., "patch_diff": diff}` to `POST /api/apply-patch`.
   - If tests only verify each endpoint in isolation with synthetic payloads (`remediated_code`), the interface contract between the output of `generate-patches` and the input of `apply-patch` is never validated.
   - An end-to-end test that extracts the actual `diff` from `generate-patches` and feeds it directly into `apply-patch` guarantees contract compatibility.

2. **Why Disk Verification (Not Just API Status) is Essential**:
   - Observation 1.2 proved that `POST /api/apply-patch` can return `HTTP 200` with `{"success": true}` while doing nothing to the target file.
   - Therefore, a test that merely checks `assert response.status_code == 200` and `assert response.json()["success"] is True` provides false confidence.
   - The test must inspect the actual target file on disk via `target_file.read_text()` and assert:
     - `on_disk_content != original_vulnerable_code`
     - The vulnerable concatenation (`f"SELECT ... {username}"`) is completely absent.
     - The remediated parameterized placeholder (`%s` or `?`) is present.
     - The database execution includes query arguments (`cursor.execute(query, (username,))`).
     - The automatic safety backup file (`<target_file>.bak`) exists and contains the exact original vulnerable code.

3. **Why Negative / Malformed Diff Tests are Critical**:
   - In production, diffs can be malformed, corrupted in transit, or applied against modified files where line offsets have drifted.
   - If `POST /api/apply-patch` does not validate that hunks were parsed and matched, it executes a silent no-op.
   - Testing negative cases ensures that:
     - Totally bogus strings without `@@` hunk headers return `HTTP 422`.
     - Corrupted hunk line numbers return `HTTP 422`.
     - Diffs with mismatched context lines return `HTTP 422`.
     - When `HTTP 422` is returned, the original file on disk remains 100% unaltered (no partial corruption).

4. **Multi-Language Coverage**:
   - The CodeDEE R1 requirement specifies CWE-89 across Python, JavaScript, and TypeScript.
   - Adding a JavaScript diff roundtrip test in addition to Python verifies that the diff parser and syntax validator work seamlessly across languages.

---

## 3. Recommended Test Design

We recommend adding the following four test cases and updating existing tests in `codedee_server/tests/test_api.py`.

### 3.1 Proposed Code Additions for `codedee_server/tests/test_api.py`

```python
# ============================================================================
# 5. Patch Diff Roundtrip & Robust Error Handling Tests
# ============================================================================

def test_apply_patch_with_unified_diff_roundtrip(tmp_path):
    """
    Verify complete patch generation and unified diff application roundtrip:
    1. Seed vulnerable Python code into a target file on disk.
    2. Call POST /api/generate-patches to generate verified patch candidates.
    3. Extract the generated unified diff from verified_patches.
    4. Assert that the diff has standard unified diff headers with clean line breaks.
    5. Send the exact diff to POST /api/apply-patch with {"patch_diff": diff}.
    6. Assert API returns HTTP 200 with success=True and valid backup file.
    7. Assert target file on disk is genuinely updated to parameterized query.
    8. Assert vulnerable f-string is eliminated from disk.
    9. Assert safety backup contains the exact original unpatched code.
    """
    target_file = tmp_path / "vulnerable_auth.py"
    target_file.write_text(VULN_PYTHON_SNIPPET, encoding="utf-8")

    # Step 1: Call POST /api/generate-patches
    gen_payload = {
        "issue_id": "ISSUE-CWE89-ROUNDTRIP-01",
        "target_file": str(target_file),
        "candidate_count": 3,
        "code_content": VULN_PYTHON_SNIPPET,
    }
    gen_response = client.post("/api/generate-patches", json=gen_payload)
    assert gen_response.status_code == 200
    gen_data = gen_response.json()

    assert gen_data["verified_count"] >= 1
    assert len(gen_data["verified_patches"]) >= 1

    # Step 2: Extract verified patch and diff
    patch = gen_data["verified_patches"][0]
    diff = patch["diff"]
    assert isinstance(diff, str) and len(diff) > 0

    # Step 3: Validate standard unified diff formatting (clean newlines)
    assert diff.startswith("--- "), f"Diff must start with '--- ', got: {diff[:40]}"
    assert "\n+++ " in diff, f"Diff must have newline before '+++ ', got: {diff[:80]}"
    assert "\n@@ " in diff, f"Diff must have newline before hunk header '@@ ', got: {diff[:120]}"

    # Step 4: Apply the exact generated diff via POST /api/apply-patch
    apply_payload = {
        "target_file": str(target_file),
        "patch_id": patch.get("patch_id", "patch_cand_01"),
        "patch_diff": diff,
    }
    apply_response = client.post("/api/apply-patch", json=apply_payload)
    assert apply_response.status_code == 200
    apply_data = apply_response.json()

    assert apply_data["success"] is True
    assert apply_data["target_file"] == str(target_file)
    assert apply_data["backup_file"] == str(target_file) + ".bak"

    # Step 5: Verify safety backup exists and contains original vulnerable code
    backup_path = Path(apply_data["backup_file"])
    assert backup_path.exists()
    assert backup_path.read_text(encoding="utf-8") == VULN_PYTHON_SNIPPET

    # Step 6: Verify file on disk has genuinely been updated
    on_disk_content = target_file.read_text(encoding="utf-8")
    assert on_disk_content != VULN_PYTHON_SNIPPET

    # Verify vulnerable f-string is eradicated
    assert 'f"SELECT id, role, email FROM accounts WHERE username = \'{username}\'"' not in on_disk_content

    # Verify parameterized placeholder and argument tuple are present
    assert ("%s" in on_disk_content or "?" in on_disk_content)
    assert ("cursor.execute(query, (" in on_disk_content or "cursor.execute(query, [" in on_disk_content)


def test_apply_patch_javascript_diff_roundtrip(tmp_path):
    """
    Verify complete patch generation and diff application roundtrip on JavaScript code.
    Ensures language neutrality and Tree-sitter validation for JS.
    """
    target_file = tmp_path / "search_service.js"
    target_file.write_text(VULN_JS_SNIPPET, encoding="utf-8")

    gen_payload = {
        "issue_id": "ISSUE-CWE89-JS-ROUNDTRIP",
        "target_file": str(target_file),
        "candidate_count": 3,
        "code_content": VULN_JS_SNIPPET,
    }
    gen_response = client.post("/api/generate-patches", json=gen_payload)
    assert gen_response.status_code == 200
    gen_data = gen_response.json()
    assert gen_data["verified_count"] >= 1

    patch = gen_data["verified_patches"][0]
    diff = patch["diff"]
    assert diff.startswith("--- ")
    assert "\n+++ " in diff

    apply_payload = {
        "target_file": str(target_file),
        "patch_id": patch.get("patch_id", "patch_cand_01"),
        "patch_diff": diff,
    }
    apply_response = client.post("/api/apply-patch", json=apply_payload)
    assert apply_response.status_code == 200
    assert apply_response.json()["success"] is True

    # Verify JavaScript file on disk is updated
    updated_js = target_file.read_text(encoding="utf-8")
    assert updated_js != VULN_JS_SNIPPET
    assert "LIKE '%${term}%'" not in updated_js


def test_apply_patch_malformed_diff_rejected(tmp_path):
    """
    Verify POST /api/apply-patch rejects invalid or malformed diffs with HTTP 422:
    - Case A: Arbitrary text without @@ hunk headers.
    - Case B: Corrupted hunk headers with unparseable line numbers.
    - Case C: Valid hunk format targeting non-matching context lines.
    Asserts HTTP 422 is returned and disk file remains completely unaltered.
    """
    target_file = tmp_path / "app_safe_state.py"
    target_file.write_text(VULN_PYTHON_SNIPPET, encoding="utf-8")

    # Case A: Totally bogus string without hunks
    bogus_payload = {
        "target_file": str(target_file),
        "patch_id": "patch_bogus",
        "patch_diff": "BOGUS DIFF TEXT WITH NO HUNK HEADERS OR VALID FORMAT",
    }
    response_bogus = client.post("/api/apply-patch", json=bogus_payload)
    assert response_bogus.status_code == 422
    assert "detail" in response_bogus.json()
    assert target_file.read_text(encoding="utf-8") == VULN_PYTHON_SNIPPET

    # Case B: Corrupted hunk header
    corrupt_payload = {
        "target_file": str(target_file),
        "patch_id": "patch_corrupt",
        "patch_diff": "--- a/app.py\n+++ b/app.py\n@@ -invalid,line @@\n-some line\n+new line\n",
    }
    response_corrupt = client.post("/api/apply-patch", json=corrupt_payload)
    assert response_corrupt.status_code == 422
    assert target_file.read_text(encoding="utf-8") == VULN_PYTHON_SNIPPET

    # Case C: Context mismatch diff
    mismatch_payload = {
        "target_file": str(target_file),
        "patch_id": "patch_mismatch",
        "patch_diff": (
            "--- a/app.py\n+++ b/app.py\n@@ -1,3 +1,3 @@\n"
            " def completely_different_function():\n"
            "-    completely_different_line()\n"
            "+    new_replacement_line()\n"
        ),
    }
    response_mismatch = client.post("/api/apply-patch", json=mismatch_payload)
    assert response_mismatch.status_code == 422
    assert target_file.read_text(encoding="utf-8") == VULN_PYTHON_SNIPPET


def test_apply_patch_empty_payload_rejected(tmp_path):
    """
    Verify POST /api/apply-patch returns HTTP 400 when neither
    remediated_code nor patch_diff is provided.
    """
    target_file = tmp_path / "empty_target.py"
    target_file.write_text(VULN_PYTHON_SNIPPET, encoding="utf-8")

    response = client.post("/api/apply-patch", json={"target_file": str(target_file)})
    assert response.status_code == 400
    assert "Either remediated_code or patch_diff" in response.json()["detail"]
```

### 3.2 Update for Starlette Deprecation Warning
In `test_apply_patch_syntax_error_rejection`:
Assert `assert response.status_code == 422` directly without relying on deprecated status code constants. In `codedee_server/app/api/apply.py`, replace `getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", status.HTTP_422_UNPROCESSABLE_ENTITY)` with `status.HTTP_422_UNPROCESSABLE_CONTENT` (or integer `422`).

---

## 4. Caveats

1. **Ollama Offline Fallback**:
   Patch generation tests rely on Ollama if reachable; if Ollama is unreachable, `POST /api/generate-patches` invokes the deterministic AST transform fallback. The test assertions (`"verified_count" >= 1`, `%s` or `?` placeholders) are designed to pass under both live Ollama and rule-based fallback paths.
2. **Path Separators on Windows**:
   When comparing diff paths on Windows, unified diff headers emitted by `difflib.unified_diff` use forward slashes (`a/vulnerable_auth.py` and `b/vulnerable_auth.py`) or Windows backslashes depending on how `target_file` is formatted. The test assertion `assert diff.startswith("--- ")` and `assert "\n+++ " in diff` is OS-neutral.
3. **Single File vs Multi-File Diffs**:
   In Milestone 1, patches apply to a single target file. The test design scopes diff application strictly to single-file targets, matching R1.

---

## 5. Conclusion

- The root cause of the Milestone 1 failure was a combination of:
  1. `difflib.unified_diff(..., lineterm="")` omitting newline delimiters on header control lines.
  2. `apply_unified_diff` lacking hunk counter validation and context matching, allowing malformed diffs to silently return the original content under an HTTP 200 status.
  3. A critical test blindspot where `test_api.py` only exercised `remediated_code` replacement, never testing `patch_diff` application or roundtrip pipeline execution.
- By incorporating:
  1. `test_apply_patch_with_unified_diff_roundtrip`
  2. `test_apply_patch_javascript_diff_roundtrip`
  3. `test_apply_patch_malformed_diff_rejected` (testing bogus, corrupt, and context-mismatched diffs)
  4. `test_apply_patch_empty_payload_rejected`
- The test suite will guarantee that:
  - Diffs produced by `POST /api/generate-patches` are 100% compliant unified diffs.
  - Applying diffs via `POST /api/apply-patch` genuinely remediates the file on disk to a parameterized query.
  - Invalid diffs are deterministically rejected with `HTTP 422 Unprocessable Content`.
  - The test suite executes warning-free under modern Starlette / FastAPI.

---

## 6. Verification Method

Once Worker M1 implements the recommended fixes in `patches.py`, `apply.py`, and `test_api.py`, the changes must be verified using the following exact commands:

### Step 1: Run Full Pytest Test Suite
```powershell
pytest d:\4th-year\Senior-Project\codedee\codedee_server\tests -v
```
**Expected Result**:
- All test cases pass (24+ tests passed).
- `test_apply_patch_with_unified_diff_roundtrip` PASSED.
- `test_apply_patch_javascript_diff_roundtrip` PASSED.
- `test_apply_patch_malformed_diff_rejected` PASSED.
- `test_apply_patch_empty_payload_rejected` PASSED.

### Step 2: Run Pytest with Zero Warnings Allowed
```powershell
pytest d:\4th-year\Senior-Project\codedee\codedee_server\tests -v -W error
```
**Expected Result**:
- Zero warnings (including no `StarletteDeprecationWarning`).
- Entire suite passes cleanly.

### Step 3: Run Standalone Adversarial Verification
```powershell
pytest d:\4th-year\Senior-Project\.agents\teamwork\challenger_m1_1\test_adversarial_m1.py -v
```
**Expected Result**:
- All 35 adversarial tests pass.

### Step 4: Verify Disk Mutation via CLI Inspection
```powershell
python -c "
import tempfile, pathlib
from fastapi.testclient import TestClient
import sys; sys.path.insert(0, r'd:\4th-year\Senior-Project\codedee\codedee_server')
from app.main import app

c = TestClient(app)
vuln = 'def f(req):\n    x = req.args[\"x\"]\n    cursor.execute(f\"SELECT * FROM t WHERE id = {x}\")\n'
with tempfile.TemporaryDirectory() as td:
    f = pathlib.Path(td) / 'test.py'
    f.write_text(vuln, encoding='utf-8')
    res_gen = c.post('/api/generate-patches', json={'issue_id': 'T1', 'code_content': vuln, 'target_file': str(f)})
    diff = res_gen.json()['verified_patches'][0]['diff']
    res_apply = c.post('/api/apply-patch', json={'target_file': str(f), 'patch_diff': diff})
    assert res_apply.status_code == 200
    content = f.read_text(encoding='utf-8')
    assert 'f\"SELECT' not in content
    assert '%s' in content or '?' in content
    print('VERIFICATION SUCCESSFUL: Disk content was genuinely patched!')
"
```
**Expected Result**: Prints `VERIFICATION SUCCESSFUL: Disk content was genuinely patched!`.

### Invalidation Conditions
The fix shall be declared **INVALID** if any of the following occur:
1. `diff` generated by `generate-patches` does not have newline breaks between `---`, `+++`, and `@@`.
2. Applying the generated `diff` leaves the vulnerable f-string or string concatenation on disk.
3. Submitting a bogus string like `"BOGUS DIFF TEXT"` returns `HTTP 200` instead of `HTTP 422`.
4. `pytest -W error` fails due to `StarletteDeprecationWarning`.
