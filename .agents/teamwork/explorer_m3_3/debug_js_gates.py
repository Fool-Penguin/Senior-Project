import sys, os
sys.path.insert(0, os.path.abspath("codedee/codedee_server"))
from app.verifier.multi_gate import MultiGateVerifier

verifier = MultiGateVerifier()
orig_js = """function searchProducts(req, res) {
    const term = req.query.term;
    const query = `SELECT * FROM products WHERE name LIKE '%${term}%'`;
    db.query(query, function(err, results) {
        res.json(results);
    });
}
"""
cand_js = """function searchProducts(req, res) {
    const term = req.query.term;
    const query = "SELECT * FROM products WHERE name LIKE $1";
    db.query(query, [`%${term}%`], function(err, results) {
        res.json(results);
    });
}
"""
g1 = verifier.verify_gate_1_syntax(cand_js, "javascript")
g2 = verifier.verify_gate_2_interface(orig_js, cand_js, "javascript")
g3 = verifier.verify_gate_3_taint_neutralized(orig_js, cand_js, "javascript")
g4, delta = verifier.verify_gate_4_maintainability(orig_js, cand_js, "javascript")
g6 = verifier.verify_gate_6_sast_rescan(cand_js, "javascript")

print("Gate 1:", g1.passed, g1.details)
print("Gate 2:", g2.passed, g2.details)
print("Gate 3:", g3.passed, g3.details)
print("Gate 4:", g4.passed, delta, g4.details)
print("Gate 6:", g6.passed, g6.details)
