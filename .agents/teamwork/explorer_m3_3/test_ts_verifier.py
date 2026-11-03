import sys, os
sys.path.insert(0, os.path.abspath("codedee/codedee_server"))
from app.verifier.multi_gate import MultiGateVerifier

verifier = MultiGateVerifier()
orig_ts = """async function getUserById(userId: string): Promise<User | null> {
    const sql = `SELECT * FROM users WHERE id = '${userId}'`;
    const result = await db.query(sql);
    return result.rows[0];
}
"""
cand_ts = """async function getUserById(userId: string): Promise<User | null> {
    const sql = "SELECT * FROM users WHERE id = $1";
    const result = await db.query(sql, [userId]);
    return result.rows[0];
}
"""
passed, patch = verifier.verify_candidate(orig_ts, cand_ts, "typescript", "cand_ts_01", "users.ts")
print("TS candidate verify passed:", passed)
if patch:
    print("Passed gates:", patch.passed_gates)
    print("Delta CC:", patch.delta_cc)
else:
    print("TS verification failed!")
