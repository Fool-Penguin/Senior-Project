import sys, os
sys.path.insert(0, r"d:\4th-year\Senior-Project\codedee\codedee_server")
from app.taint.walker import SymbolicTaintWalker

w = SymbolicTaintWalker()
code = '''from flask import request

def complex_handler():
    raw = request.args.get('term')
    cleaned = raw.strip()
    formatted = f"search: {cleaned}"
    query = "SELECT * FROM docs WHERE content LIKE '%" + formatted + "%'"
    cursor.execute(query)
'''
findings = w.analyze_code(code, "python", "multi.py")
print("Count:", len(findings))
for i, f in enumerate(findings):
    print(f"Finding {i}: Source={f.source_node.get('symbol')} Sink={f.sink_node.get('symbol')} Sanitized={f.sanitized} Steps={len(f.taint_path)}")
    for s in f.taint_path:
        print(f"   Step {s['step_index']}: {s['symbol']} ({s['operation']})")

