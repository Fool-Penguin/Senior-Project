import sys
sys.path.insert(0, "codedee/codedee_server")
from app.graphs.dfg import DFGBuilder
from app.taint.walker import SymbolicTaintWalker

code = '''from flask import request

def get_user_profile():
    username = request.args.get("username")
    sql = "SELECT * FROM users WHERE name = '%s'" % (username,)
    cursor.execute(sql)
'''

builder = DFGBuilder()
g = builder.build_for_code(code, "python")
print("DFG node count:", len(g.nodes))
print("DFG edge count:", len(g.edges))
for u, v, d in g.edges(data=True):
    print(f"  {u} --({d.get('flow_type')}, op={d.get('operation')})--> {v}")

walker = SymbolicTaintWalker()
findings = walker.analyze_code(code, "python")
print("\nFindings count:", len(findings))
for idx, f in enumerate(findings):
    print(f"Finding {idx}: cwe={f.cwe_id}, sev={f.severity}, sanitized={f.sanitized}")
    for step in f.taint_path:
        print(f"   Step {step['step_index']}: {step['symbol']} ({step['operation']}) line {step['line']}")
