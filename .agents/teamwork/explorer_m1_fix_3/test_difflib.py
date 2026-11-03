import difflib

orig = """def login_user(request):
    username = request.args.get('username')
    cursor = db.cursor()
    query = f"SELECT id, role, email FROM accounts WHERE username = '{username}'"
    cursor.execute(query)
    return cursor.fetchall()
"""

patch = """def login_user(request):
    username = request.args.get('username')
    cursor = db.cursor()
    query = "SELECT id, role, email FROM accounts WHERE username = %s"
    cursor.execute(query, (username,))
    return cursor.fetchall()
"""

orig_lines = orig.splitlines(keepends=True)
patch_lines = patch.splitlines(keepends=True)

# Default difflib.unified_diff (lineterm='\n')
diff_default = "".join(difflib.unified_diff(orig_lines, patch_lines, fromfile="a/test.py", tofile="b/test.py"))
print("=== Default diff ===")
print(repr(diff_default))
print(diff_default)

# Buggy difflib.unified_diff (lineterm='')
diff_buggy = "".join(difflib.unified_diff(orig_lines, patch_lines, fromfile="a/test.py", tofile="b/test.py", lineterm=""))
print("=== Buggy diff ===")
print(repr(diff_buggy))
print(diff_buggy)
