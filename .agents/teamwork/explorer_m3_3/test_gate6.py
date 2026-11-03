import sys, os
sys.path.insert(0, os.path.abspath("codedee/codedee_server"))
from app.verifier.multi_gate import MultiGateVerifier

verifier = MultiGateVerifier()
clean_cand = """def get_item(item_id):
    query = "SELECT * FROM items WHERE id = ?"
    cursor.execute(query, (item_id,))
"""
res_clean = verifier.verify_gate_6_sast_rescan(clean_cand, "python")
print("Clean cand Gate 6:", res_clean.passed, res_clean.details)

vuln_cand = """def get_item(item_id):
    query = f"SELECT * FROM items WHERE id = '{item_id}'"
    cursor.execute(query)
"""
res_vuln = verifier.verify_gate_6_sast_rescan(vuln_cand, "python")
print("Vuln cand Gate 6:", res_vuln.passed, res_vuln.details)
