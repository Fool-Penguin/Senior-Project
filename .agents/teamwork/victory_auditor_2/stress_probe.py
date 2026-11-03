import sys
from pathlib import Path
sys.path.insert(0, r"d:\4th-year\Senior-Project\codedee\codedee_server")

from app.taint.walker import SymbolicTaintWalker
from app.neuro.oracle import NeuralOracle
from app.models.contracts import SymbolicFinding

walker = SymbolicTaintWalker()

# Test Case 1: Concatenation inside execute with multiple args (fake parameter bypass)
call1 = 'cursor.execute("SELECT * FROM tbl WHERE x = " + x, (1, 2))'
res1 = walker.is_sink_parameterized({}, call1)
print(f"Test 1 (fake parameter bypass concat): parameterized={res1} (Expected False)")
assert res1 is False

# Test Case 2: Direct f-string inside execute with multiple args
call2 = 'cursor.execute(f"SELECT * FROM tbl WHERE x = {x}", (1, 2))'
res2 = walker.is_sink_parameterized({}, call2)
print(f"Test 2 (fake parameter bypass fstring): parameterized={res2} (Expected False)")
assert res2 is False

# Test Case 3: Genuine parameterization with tuple
call3 = 'cursor.execute("SELECT * FROM tbl WHERE x = ?", (x,))'
res3 = walker.is_sink_parameterized({}, call3)
print(f"Test 3 (genuine tuple parameter): parameterized={res3} (Expected True)")
assert res3 is True

# Test Case 4: Genuine parameterization with list
call4 = 'db.query("SELECT * FROM tbl WHERE x = $1", [x])'
res4 = walker.is_sink_parameterized({}, call4)
print(f"Test 4 (genuine list parameter): parameterized={res4} (Expected True)")
assert res4 is True

# Test Case 5: Empty tuple bypass
call5 = 'cursor.execute("SELECT * FROM tbl WHERE x = %s", ())'
res5 = walker.is_sink_parameterized({}, call5)
print(f"Test 5 (empty tuple bypass): parameterized={res5} (Expected False)")
assert res5 is False

# Test Case 6: Neural Oracle offline fallback
oracle = NeuralOracle()
finding = SymbolicFinding(
    cwe_id="CWE-89",
    source_node={"file": "test.py", "line": 1, "symbol": "u", "expression": "u"},
    sink_node={"file": "test.py", "line": 2, "symbol": "cursor.execute", "expression": "cursor.execute(...)"},
    sanitized=False
)
assessment = oracle._deterministic_fallback_assessment(finding, "code_slice_text", "python")
print(f"Test 6 (Oracle fallback): risk={assessment.risk_level}, score={assessment.confidence_score}")
assert assessment.risk_level == "CRITICAL"
assert assessment.confidence_score == 1.0

# Test Case 7: Oracle query method fallback with unreachable port
oracle_offline = NeuralOracle(base_url="http://127.0.0.1:99999")
assessment7 = oracle_offline._query_ollama_assessment(
    code_slice="def f(): pass",
    language="python",
    rag_context="test context",
    taint_path_str="source -> sink",
    finding=finding
)
print(f"Test 7 (Oracle query fallback catch): risk={assessment7.risk_level}")
assert assessment7.risk_level == "CRITICAL"


print("ALL ADVERSARIAL STRESS PROBES PASSED!")
