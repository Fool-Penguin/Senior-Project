import sys
sys.path.insert(0, "codedee/codedee_server")
from app.taint.walker import SymbolicTaintWalker

walker = SymbolicTaintWalker()

# Test 1: Python raw and query variables with NO SQL sink
code_py = '''from flask import request

def parse_raw_payload():
    raw_data = request.args.get("data")
    search_query = request.args.get("q")
    raw_text = request.form.get("content")
    user_query = request.values.get("term")
    combined = f"{raw_data} - {search_query} - {raw_text} - {user_query}"
    return combined.strip()
'''
findings_py = walker.analyze_code(code_py, "python")
print("Python non-SQL variables findings:", len(findings_py))

# Test 2: JavaScript non-SQL raw and query variables
code_js = '''function processSearchRequest(req, res) {
    const rawData = req.query.data;
    const searchQuery = req.query.q;
    const rawPayload = req.body.payload;
    const queryTerm = req.params.term;
    const summary = `Query: ${searchQuery}, Raw: ${rawData}, Term: ${queryTerm}`;
    return res.json({ summary: summary, raw: rawPayload });
}
'''
findings_js = walker.analyze_code(code_js, "javascript")
print("JavaScript non-SQL variables findings:", len(findings_js))

# Test 3: JavaScript template literal with constants into db.query
code_const = '''function getStaticConfig() {
    const limit = 50;
    const isApproved = true;
    const query = `SELECT * FROM items WHERE approved = ${isApproved} LIMIT ${limit}`;
    db.query(query);
}
'''
findings_const = walker.analyze_code(code_const, "javascript")
print("JavaScript constant query findings:", len(findings_const))

# Test 4: Genuine SQL injection with mixed variables
code_mixed = '''from flask import request

def handle_request():
    raw_data = request.args.get("data")
    search_term = request.args.get("term")
    sql = f"SELECT * FROM items WHERE name = '{search_term}'"
    cursor.execute(sql)
    return raw_data
'''
findings_mixed = walker.analyze_code(code_mixed, "python")
print("Mixed variables findings:", len(findings_mixed))
for f in findings_mixed:
    print(f"  Finding sink symbol: {f.sink_node.get('symbol')}, expr: {f.sink_node.get('expression')}")
