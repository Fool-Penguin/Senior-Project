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
passed, patch = verifier.verify_candidate(orig_js, cand_js, "javascript", "cand_js_01", "products.js")
print("JS candidate verify passed:", passed)
if patch:
    print("Passed gates:", patch.passed_gates)
    print("Delta CC:", patch.delta_cc)
    print("Diff:", patch.diff[:100])
else:
    print("Failed")
