import difflib
import subprocess
import tempfile
from pathlib import Path

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

# Generate clean diff without lineterm=""
diff_lines = list(difflib.unified_diff(
    orig.splitlines(keepends=True),
    patched.splitlines(keepends=True),
    fromfile="a/sample.py",
    tofile="b/sample.py",
))
clean_diff = "".join(diff_lines)

with tempfile.TemporaryDirectory() as td:
    tpath = Path(td)
    # Init git repo
    subprocess.run(["git", "init"], cwd=tpath, capture_output=True, check=True)
    sample_file = tpath / "sample.py"
    sample_file.write_text(orig, encoding="utf-8")
    subprocess.run(["git", "add", "sample.py"], cwd=tpath, capture_output=True, check=True)

    patch_file = tpath / "patch.diff"
    patch_file.write_text(clean_diff, encoding="utf-8")

    # Apply with git apply
    res = subprocess.run(["git", "apply", str(patch_file)], cwd=tpath, capture_output=True, text=True)
    print("git apply returncode:", res.returncode)
    print("git apply stdout:", res.stdout)
    print("git apply stderr:", res.stderr)
    print("File content after git apply matches patched:", sample_file.read_text(encoding="utf-8") == patched)

# Test with corrupt diff (lineterm="")
corrupt_diff = "".join(difflib.unified_diff(
    orig.splitlines(keepends=True),
    patched.splitlines(keepends=True),
    fromfile="a/sample.py",
    tofile="b/sample.py",
    lineterm="",
))

with tempfile.TemporaryDirectory() as td:
    tpath = Path(td)
    subprocess.run(["git", "init"], cwd=tpath, capture_output=True, check=True)
    sample_file = tpath / "sample.py"
    sample_file.write_text(orig, encoding="utf-8")
    subprocess.run(["git", "add", "sample.py"], cwd=tpath, capture_output=True, check=True)

    patch_file = tpath / "patch_corrupt.diff"
    patch_file.write_text(corrupt_diff, encoding="utf-8")

    res = subprocess.run(["git", "apply", str(patch_file)], cwd=tpath, capture_output=True, text=True)
    print("Corrupt diff git apply returncode:", res.returncode)
    print("Corrupt diff git apply stderr:", repr(res.stderr))
