import sys
from pathlib import Path

SERVER_ROOT = Path(r"D:\4th-year\Senior-Project\codedee\codedee_server")
sys.path.insert(0, str(SERVER_ROOT))

from app.taint.walker import SymbolicTaintWalker

w = SymbolicTaintWalker()
code = """
def tricky_fake_param():
    username = request.args.get("username")
    query = f"SELECT * FROM users WHERE name = '{username}'"
    cursor.execute(query, ())
"""
res = w.analyze_code(code, "python")
print([(f.severity, f.sanitized, f.sink_node) for f in res])
