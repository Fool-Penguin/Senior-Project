import sys
import tempfile
from pathlib import Path
sys.path.insert(0, r"d:\4th-year\Senior-Project\codedee\codedee_server")
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


VULN = """def login_user(request):
    username = request.args.get('username')
    cursor = db.cursor()
    query = f"SELECT id, role, email FROM accounts WHERE username = '{username}'"
    cursor.execute(query)
    return cursor.fetchall()
"""

with tempfile.TemporaryDirectory() as td:
    f = Path(td) / "test.py"
    f.write_text(VULN, encoding="utf-8")
    res_gen = client.post(
        "/api/generate-patches",
        json={"issue_id": "TEST", "code_content": VULN, "target_file": str(f)},
    )
    print("Gen status:", res_gen.status_code)
    data_gen = res_gen.json()
    patches = data_gen.get("verified_patches", [])
    print("Verified patches count:", len(patches))
    if patches:
        diff = patches[0]["diff"]
        print("Diff repr:\n", repr(diff[:200]))
        print("Diff text:\n", diff[:200])
        res_apply = client.post(
            "/api/apply-patch",
            json={"target_file": str(f), "patch_diff": diff},
        )
        print("Apply response status:", res_apply.status_code)
        print("Apply response json:", res_apply.json())
        content_after = f.read_text(encoding="utf-8")
        print("f.read_text() == VULN:", content_after == VULN)
        print("f.read_text() lines == VULN.splitlines():", content_after.splitlines() == VULN.splitlines())
        print("Parameterized query in content_after?", "%s" in content_after or "?" in content_after)
        print("Vulnerable f-string in content_after?", 'query = f"SELECT' in content_after)


    # Test bogus diff
    res_bogus = client.post(
        "/api/apply-patch",
        json={"target_file": str(f), "patch_diff": "BOGUS MALFORMED DIFF WITHOUT HUNKS"},
    )
    print("Bogus diff status:", res_bogus.status_code)
    print("Bogus diff json:", res_bogus.json())
