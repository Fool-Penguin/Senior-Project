from codedee.codedee_server.app.taint.walker import SymbolicTaintWalker

code = """
from flask import request
from storage_service import execute_filtered_query

def get_store_items():
    search_term = request.args.get("category", "books")
    clause = "category = '" + search_term + "'"
    results = execute_filtered_query(conn, "inventory", clause)
    return results
"""

walker = SymbolicTaintWalker()
findings = walker.analyze_code(code, "python", "test_var_concat.py")
print(f"Total findings: {len(findings)}")
for i, f in enumerate(findings):
    print(f"Finding {i}: sanitized={f.sanitized}, severity={f.severity}")
    for s in f.taint_path:
        print(f"  step: {s['symbol']} ({s['operation']})")
