import sys, os
sys.path.insert(0, os.path.abspath("codedee/codedee_server"))
from app.verifier.multi_gate import MultiGateVerifier

verifier = MultiGateVerifier()
orig = """def get_item(item_id):
    query = "SELECT * FROM items WHERE id = " + item_id
    cursor.execute(query)
"""
cand_extra_branches = """def get_item(item_id):
    if item_id:
        if isinstance(item_id, str):
            query = "SELECT * FROM items WHERE id = ?"
            cursor.execute(query, (item_id,))
"""
res, delta = verifier.verify_gate_4_maintainability(orig, cand_extra_branches, "python")
print("Gate 4 regression check:", res.passed, "delta_cc:", delta, "details:", res.details)
