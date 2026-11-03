import sys, os
sys.path.insert(0, os.path.abspath("codedee/codedee_server"))
from app.taint.walker import SymbolicTaintWalker

cand_js = """function searchProducts(req, res) {
    const term = req.query.term;
    const query = "SELECT * FROM products WHERE name LIKE $1";
    db.query(query, [`%${term}%`], function(err, results) {
        res.json(results);
    });
}
"""

walker = SymbolicTaintWalker()
findings = walker.analyze_code(cand_js, "javascript", "cand.js")
print("Findings:", len(findings))
for idx, f in enumerate(findings):
    print(f"Finding {idx}: sanitized={f.sanitized}, severity={f.severity}")
    print("  source:", f.source_node)
    print("  sink:", f.sink_node)
    print("  taint_path:", [(s["step_index"], s["symbol"], s["operation"]) for s in f.taint_path])
