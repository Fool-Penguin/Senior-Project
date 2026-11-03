import sys
import os

sys.path.insert(0, os.path.abspath("codedee/codedee_server"))
from app.taint.walker import SymbolicTaintWalker

code = """def login_user(request):
    username = request.args.get('username')
    cursor = db.cursor()
    query = f"SELECT id, role, email FROM accounts WHERE username = '{username}'"
    cursor.execute(query)
    return cursor.fetchall()
"""

walker = SymbolicTaintWalker()
findings = walker.analyze_code(code, "python", "auth_controller.py")
print("Total findings:", len(findings))
for idx, f in enumerate(findings):
    print(f"--- Finding {idx+1} ---")
    print("Source:", f.source_node)
    print("Sink:", f.sink_node)
    print("Sanitized:", f.sanitized)
    print("Path length:", len(f.taint_path))
