import sys, os
sys.path.insert(0, os.path.abspath("codedee/codedee_server"))
from app.taint.walker import SymbolicTaintWalker

cand_js2 = """function searchProducts(req, res) {
    const term = req.query.term;
    const query = "SELECT * FROM products WHERE name LIKE $1";
    db.query(query, [term], function(err, results) {
        res.json(results);
    });
}
"""

walker = SymbolicTaintWalker()
findings = walker.analyze_code(cand_js2, "javascript", "cand2.js")
print("Findings count for [term]:", len(findings))
if findings:
    print("Sanitized:", findings[0].sanitized)
