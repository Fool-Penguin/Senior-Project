import sys, os
from pydantic import BaseModel, Field
from typing import List, Dict

class GateVerificationResult(BaseModel):
    gate_1_syntax: bool
    gate_2_interface: bool
    gate_3_neutralization: bool
    gate_4_maintainability: bool
    gate_6_sast_rescan: bool
    is_100_percent_verified: bool
    delta_cc: int = 0
    passed_gates: List[str] = Field(default_factory=list)
    gate_details: Dict[str, str] = Field(default_factory=dict)

# Inject into app.models.contracts for testing
sys.path.insert(0, os.path.abspath("codedee/codedee_server"))
import app.models.contracts
app.models.contracts.GateVerificationResult = GateVerificationResult

sys.path.insert(0, os.path.abspath(".agents/teamwork/explorer_m3_3"))
from proposed_multi_gate import MultiGateVerifier

verifier = MultiGateVerifier()

orig = """def fetch_user(uid):
    cursor.execute("SELECT * FROM users WHERE id = " + uid)
"""
good_patch = """def fetch_user(uid):
    cursor.execute("SELECT * FROM users WHERE id = ?", (uid,))
"""
bad_patch_param_name = """def fetch_user(user_id):
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
"""
bad_patch_concat = """def fetch_user(uid):
    cursor.execute("SELECT * FROM users WHERE id = " + uid, (uid,))
"""
bad_patch_cc = """def fetch_user(uid):
    if uid:
        cursor.execute("SELECT * FROM users WHERE id = ?", (uid,))
"""

res_good = verifier.verify_patch(orig, good_patch, "python")
print("Good patch is_100:", res_good.is_100_percent_verified, res_good.passed_gates)

res_param = verifier.verify_patch(orig, bad_patch_param_name, "python")
print("Bad param name Gate 2:", res_param.gate_2_interface, "is_100:", res_param.is_100_percent_verified)

res_concat = verifier.verify_patch(orig, bad_patch_concat, "python")
print("Bad concat Gate 3:", res_concat.gate_3_neutralization, "is_100:", res_concat.is_100_percent_verified)

res_cc = verifier.verify_patch(orig, bad_patch_cc, "python")
print("Bad CC Gate 4:", res_cc.gate_4_maintainability, "delta_cc:", res_cc.delta_cc, "is_100:", res_cc.is_100_percent_verified)
