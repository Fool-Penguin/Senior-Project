import sys, os
sys.path.insert(0, os.path.abspath("codedee/codedee_server"))
from app.verifier.multi_gate import MultiGateVerifier

verifier = MultiGateVerifier()
orig = """def find_user(uid):
    cursor.execute("SELECT * FROM users WHERE id = " + uid)
"""
# Candidate attempts to bypass with dummy tuple while keeping string concatenation
bypass_cand = """def find_user(uid):
    cursor.execute("SELECT * FROM users WHERE id = " + uid, (uid,))
"""
res = verifier.verify_gate_3_taint_neutralized(orig, bypass_cand, "python")
print("Gate 3 bypass result:", res.passed, res.details)
