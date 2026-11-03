import sys
sys.path.insert(0, r"d:\4th-year\Senior-Project\codedee\codedee_server")
from app.api.apply import apply_unified_diff

orig = """def login_user(request):
    username = request.args.get('username')
    cursor = db.cursor()
    query = f"SELECT id, role, email FROM accounts WHERE username = '{username}'"
    cursor.execute(query)
    return cursor.fetchall()
"""

diff_clean = """--- a/test.py
+++ b/test.py
@@ -1,6 +1,6 @@
 def login_user(request):
     username = request.args.get('username')
     cursor = db.cursor()
-    query = f"SELECT id, role, email FROM accounts WHERE username = '{username}'"
-    cursor.execute(query)
+    query = "SELECT id, role, email FROM accounts WHERE username = %s"
+    cursor.execute(query, (username,))
     return cursor.fetchall()
"""

res = apply_unified_diff(orig, diff_clean)
print("Result with diff_clean:\n", res)
print("Parameterized query in res?", "%s" in res)
