"""
stress_tests.py - Adversarial review and edge case stress tests for Milestone 1.
"""

import sys
import tempfile
from pathlib import Path

SERVER_DIR = Path(r"D:\4th-year\Senior-Project\codedee\codedee_server")
sys.path.insert(0, str(SERVER_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.api.apply import apply_unified_diff

client = TestClient(app)

print("--- Stress Test 1: Empty / Malformed Scan Request ---")
res1 = client.post("/api/scan", json={})
assert res1.status_code == 400, f"Expected 400, got {res1.status_code}"
print("Passed: Empty scan request rejected with HTTP 400.")

print("--- Stress Test 2: In-memory Unicode & Multi-line Comments in Scan ---")
unicode_code = """# Unicode comment: ค้นหาผู้ใช้งาน 🚀
def search_user(req):
    '''
    Docstring:
    SELECT * FROM fake_table WHERE ignore = 1
    '''
    q = req.args.get('term')
    # cursor.execute(f"SELECT * FROM users WHERE q = '{q}'")
    cursor.execute("SELECT * FROM users WHERE q = ?", (q,))
    return cursor.fetchall()
"""
res2 = client.post("/api/scan", json={"code_content": unicode_code, "language": "python"})
assert res2.status_code == 200
data2 = res2.json()
assert data2["issues_count"] == 0, f"Commented-out injection should not be flagged! Got {data2['issues_count']}"
print("Passed: Commented-out and docstring queries are not falsely flagged.")

print("--- Stress Test 3: Unified Diff Application ---")
orig_text = "line 1\nline 2\nline 3\nline 4\n"
patch_diff = """--- a/test.py
+++ b/test.py
@@ -2,2 +2,2 @@
-line 2
-line 3
+line 2 modified
+line 3 modified
"""
patched = apply_unified_diff(orig_text, patch_diff)
expected = "line 1\nline 2 modified\nline 3 modified\nline 4\n"
assert patched.strip() == expected.strip(), f"Diff mismatch:\nGot: {patched}\nExpected: {expected}"
print("Passed: Unified diff parsing and line substitution verified.")

print("--- Stress Test 4: Maintainability Engine Edge Cases (No Functions) ---")
script_code = """# Simple script
import os
import sys

x = 10
y = 20
if x > 5:
    print(x + y)
"""
res4 = client.post("/api/scan", json={"code_content": script_code, "language": "python"})
assert res4.status_code == 200
m = res4.json()["maintainability"]
assert m["cyclomatic_complexity"] >= 2
assert m["function_sloc"] >= 1
print(f"Passed: Script without functions computed maintainability cleanly: {m}")

print("--- Stress Test 5: Boundary Values in Generate Patches ---")
res5 = client.post("/api/generate-patches", json={
    "issue_id": "TEST_EMPTY",
    "target_file": "missing.py",
    "code_content": "def foo():\n    pass\n"
})
assert res5.status_code == 200
assert res5.json()["verified_count"] == 0  # No vulnerability to patch, 0 verified patches
print("Passed: Clean code with no vulnerability produces 0 patches cleanly.")

print("\nALL ADVERSARIAL STRESS TESTS PASSED.")
