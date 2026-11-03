"""
test_forensic_probes.py - Independent forensic stress testing probes by auditor_m2_iter4_1.
"""

import sys
from pathlib import Path

# Add server directory to path
SERVER_DIR = Path(__file__).resolve().parent.parent.parent.parent / "codedee" / "codedee_server"
sys.path.insert(0, str(SERVER_DIR))

from app.graphs.dfg import DFGBuilder
from app.taint.walker import SymbolicTaintWalker

def run_probes():
    walker = SymbolicTaintWalker()

    # Stress Probe 1: Arbitrary deep chained call
    code1 = """
def deep_chain_test(req):
    user = req.args.get('user')
    sql = f'SELECT * FROM t WHERE col = {user}'
    a.b().c().d().execute(sql)
"""
    f1 = walker.analyze_code(code1, 'python', 'deep_chain.py')
    vulns1 = [f for f in f1 if not f.sanitized and f.severity == 'CRITICAL']
    assert len(vulns1) == 1, f"Stress 1 failed: {len(vulns1)} vulns"
    print("Probe 1 (Deep chained call AST uniqueness) PASSED")

    # Stress Probe 2: Complex nested JS destructuring
    code2 = """
function complex_destruct(req) {
    const { a: { b: [c, { d: target }] } } = req.query;
    db.query(`SELECT * FROM t WHERE val = '${target}'`);
}
"""
    f2 = walker.analyze_code(code2, 'javascript', 'complex_destruct.js')
    vulns2 = [f for f in f2 if not f.sanitized and f.severity == 'CRITICAL']
    assert len(vulns2) >= 1, f"Stress 2 failed: {len(vulns2)} vulns"
    print(f"Probe 2 (Complex nested JS destructuring target extraction: {len(vulns2)} paths found) PASSED")

    # Stress Probe 3: Deep nested subscript assignment in Python
    code3 = """
def deep_sub(req):
    u = req.args.get('u')
    state = {'deep': {'nested': [{'field': None}]}}
    state['deep']['nested'][0]['field'] = u
    sql = f"SELECT * FROM t WHERE val = {state['deep']['nested'][0]['field']}"
    cursor.execute(sql)
"""
    f3 = walker.analyze_code(code3, 'python', 'deep_sub.py')
    vulns3 = [f for f in f3 if not f.sanitized and f.severity == 'CRITICAL']
    assert len(vulns3) == 1, f"Stress 3 failed: {len(vulns3)} vulns"
    print("Probe 3 (Deep nested subscript container unwinding) PASSED")

    # Stress Probe 4: Shortest path parameter bypass with multiple dummy args
    code4 = """
def bypass_multi_arg(req):
    u = req.args.get('u')
    cursor.execute('SELECT * FROM t WHERE val = ' + u, (u,), [u])
"""
    f4 = walker.analyze_code(code4, 'python', 'bypass_multi.py')
    vulns4 = [f for f in f4 if not f.sanitized and f.severity == 'CRITICAL']
    assert len(vulns4) == 1, f"Stress 4 failed: {len(vulns4)} vulns"
    print("Probe 4 (Shortest path bypass with multiple candidate arguments) PASSED")

    # Stress Probe 5: Genuine multi-key dictionary query in PEP 249
    code5 = """
def safe_pep249(req):
    u = req.args.get('u')
    cursor.execute('SELECT * FROM t WHERE val = %(u)s AND age = %(age)s', {'u': u, 'age': 25})
"""
    f5 = walker.analyze_code(code5, 'python', 'safe_dict.py')
    vulns5 = [f for f in f5 if not f.sanitized]
    assert len(vulns5) == 0, f"Stress 5 failed: false positive {vulns5}"
    assert all(f.sanitized for f in f5), "Stress 5 failed: not marked sanitized"
    print("Probe 5 (PEP 249 dictionary query recognized as sanitized) PASSED")

    # Stress Probe 6: Multi-line database call with trailing comment and indentation
    code6 = """
def multiline_complex(req):
    user = req.args.get('user')
    cursor.execute(
        # comment line
        "SELECT * FROM users WHERE name = %s",
        (user,)
    )
"""
    f6 = walker.analyze_code(code6, 'python', 'multiline_complex.py')
    vulns6 = [f for f in f6 if not f.sanitized]
    assert len(vulns6) == 0, f"Stress 6 failed: false positive on multiline {vulns6}"
    print("Probe 6 (Multi-line sink call with comment and indentation) PASSED")

    print("\n>>> ALL 6 INDEPENDENT FORENSIC STRESS PROBES PASSED! <<<")

if __name__ == "__main__":
    run_probes()
