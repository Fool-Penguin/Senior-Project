import sys, os
sys.path.insert(0, os.path.abspath("codedee/codedee_server"))
from app.verifier.multi_gate import MultiGateVerifier

verifier = MultiGateVerifier()
orig = """def find_user(uid):
    cursor.execute("SELECT * FROM users WHERE id = " + uid)
"""
bypass_cand = """def find_user(uid):
    cursor.execute("SELECT * FROM users WHERE id = " + uid, (uid,))
"""
passed, patch = verifier.verify_candidate(orig, bypass_cand, "python", "cand_bypass")
print("verify_candidate passed:", passed)
if patch:
    print("Patch passed gates:", patch.passed_gates)
else:
    g6 = verifier.verify_gate_6_sast_rescan(bypass_cand, "python")
    print("Gate 6 caught it:", g6.passed, g6.details)
