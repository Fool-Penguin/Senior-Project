import sys, os
sys.path.insert(0, r"d:\4th-year\Senior-Project\codedee\codedee_server")
from app.taint.walker import SymbolicTaintWalker
from app.graphs.dfg import DFGBuilder

code = """
from flask import request

def cast_handler():
    raw_id = request.args.get('id')
    safe_id = int(raw_id)
    query = f"SELECT * FROM users WHERE id = {safe_id}"
    cursor.execute(query)
"""
w = SymbolicTaintWalker()
findings = w.analyze_code(code, "python", "typecast.py")
print("Findings count:", len(findings))
for i, f in enumerate(findings):
    print(f"Finding {i}: Sanitized={f.sanitized} Severity={f.severity} Path len={len(f.taint_path)}")
    for step in f.taint_path:
        print(f"  Step: {step['symbol']} ({step['operation']}) snippet={step['code_snippet']}")

b = DFGBuilder()
g = b.build_for_code(code, "python", "typecast.py")
print("\nDFG Nodes:")
for n, d in g.nodes(data=True):
    print(" ", n, d.get("node_kind"), d.get("var_name"), "expr:", repr(d.get("expression_text")))
