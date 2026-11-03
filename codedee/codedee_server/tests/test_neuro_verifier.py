"""
test_neuro_verifier.py - Tests for ChromaDB RAG, Program Slicer, Neural Oracle, and Multi-Gate Verifier.
Covers Python, JavaScript, and TypeScript with full multi-gate contract conformance.
"""

from pathlib import Path
import pytest
from app.knowledge.chroma_kb import ChromaKnowledgeBase
from app.models.contracts import (
    GateVerificationResult,
    NeuroAssessment,
    SymbolicFinding,
    VerifiedPatch,
)
from app.oracle.neural_oracle import NeuralOracle
from app.slicer.program_slicer import ProgramSlicer
from app.verifier.multi_gate import MultiGateVerifier


def test_chroma_knowledge_base():
    """Verify ChromaDB seeds mini_test_knowledges.json and retrieves relevant patterns."""
    kb = ChromaKnowledgeBase.get_instance()
    count = kb.seed_knowledge()
    assert count >= 5

    # Query for Python SQLite parameterization
    results = kb.query_knowledge("sqlite3 cursor.execute with ? placeholder", language="python", n_results=2)
    assert len(results) > 0
    assert any("?" in r["document"] or "psycopg2" in r["document"] or "placeholder" in r["document"].lower() for r in results)

    # Query for JavaScript node-postgres parameterization
    js_results = kb.query_knowledge("node postgres client.query $1 parameters", language="javascript", n_results=2)
    assert len(js_results) > 0


def test_program_slicer_full_function_extraction():
    """Verify ProgramSlicer extracts the complete enclosing function."""
    slicer = ProgramSlicer()
    code = """
import sqlite3

def find_user_by_name(username):
    # Lookup in database
    conn = sqlite3.connect("test.db")
    cursor = conn.cursor()
    query = f"SELECT * FROM users WHERE name = '{username}'"
    cursor.execute(query)
    return cursor.fetchall()
"""
    slice_data = slicer.slice_context(code, "python", source_line=7, sink_line=8)
    assert slice_data["slice_type"] == "single_function"
    assert "find_user_by_name" in slice_data["function_names"]
    assert "def find_user_by_name(username):" in slice_data["slice_code"]
    assert "return cursor.fetchall()" in slice_data["slice_code"]


def test_program_slicer_decorated_python():
    """Verify ProgramSlicer extracts Python functions decorated with decorators."""
    slicer = ProgramSlicer()
    code = """
from flask import Flask, request

app = Flask(__name__)

@app.route("/profile/<uid>")
def user_profile(uid):
    q = f"SELECT * FROM profiles WHERE id = {uid}"
    cursor.execute(q)
    return "OK"
"""
    slice_data = slicer.slice_context(code, "python", source_line=7, sink_line=8)
    assert slice_data["slice_type"] == "single_function"
    assert "user_profile" in slice_data["function_names"]
    assert "def user_profile(uid):" in slice_data["slice_code"]
    assert "cursor.execute(q)" in slice_data["slice_code"]


def test_program_slicer_js_arrow_function():
    """Verify ProgramSlicer extracts JavaScript arrow functions assigned to variables."""
    slicer = ProgramSlicer()
    code = """
const { Client } = require('pg');

const handleSearch = async (req, res) => {
    const term = req.query.q;
    const query = `SELECT * FROM items WHERE name LIKE '%${term}%'`;
    const rows = await client.query(query);
    res.json(rows);
};
"""
    slice_data = slicer.slice_context(code, "javascript", source_line=5, sink_line=6)
    assert slice_data["slice_type"] == "single_function"
    assert "handleSearch" in slice_data["function_names"]
    assert "handleSearch" in slice_data["slice_code"]
    assert "client.query(query)" in slice_data["slice_code"]


def test_program_slicer_statement_boundary_script():
    """Verify ProgramSlicer falls back to statement-boundary window for script-level code."""
    slicer = ProgramSlicer()
    code = """
import sys
import sqlite3

user_id = sys.argv[1]
conn = sqlite3.connect("test.db")
cursor = conn.cursor()
sql = "SELECT * FROM users WHERE id = " + user_id
cursor.execute(sql)
print(cursor.fetchall())
"""
    slice_data = slicer.slice_context(code, "python", source_line=4, sink_line=8)
    assert slice_data["slice_type"] in ("script_window", "statement_window", "single_function", "full_snippet", "statement_boundary_slice")
    assert "cursor.execute(sql)" in slice_data["slice_code"]
    assert slice_data["start_line"] >= 1
    assert slice_data["end_line"] >= slice_data["start_line"]


def test_multi_gate_verifier_all_gates_pass():
    """Verify MultiGateVerifier approves a 100% compliant parameterized patch."""
    verifier = MultiGateVerifier()
    orig = """
def fetch_account(user_id):
    query = f"SELECT * FROM accounts WHERE id = {user_id}"
    cursor.execute(query)
    return cursor.fetchone()
"""
    cand = """
def fetch_account(user_id):
    query = "SELECT * FROM accounts WHERE id = ?"
    cursor.execute(query, (user_id,))
    return cursor.fetchone()
"""
    passed, verified_patch = verifier.verify_candidate(orig, cand, "python", "cand_01", "account.py")
    assert passed is True
    assert verified_patch is not None
    assert verified_patch.delta_cc <= 0
    assert len(verified_patch.passed_gates) == 5
    assert "Gate 1" in verified_patch.passed_gates
    assert "Gate 2" in verified_patch.passed_gates
    assert "Gate 3" in verified_patch.passed_gates
    assert "Gate 4" in verified_patch.passed_gates
    assert "Gate 6" in verified_patch.passed_gates


def test_multi_gate_verifier_verify_patch_contract():
    """Verify MultiGateVerifier.verify_patch returns a conformant GateVerificationResult."""
    verifier = MultiGateVerifier()
    orig = """
def fetch_data(uid):
    q = "SELECT * FROM tbl WHERE id = " + uid
    cursor.execute(q)
    return cursor.fetchall()
"""
    cand_valid = """def fetch_data(uid):
    q = "SELECT * FROM tbl WHERE id = ?"
    cursor.execute(q, (uid,))
    return cursor.fetchall()"""
    cand_syntax_err = """def fetch_data(uid:
    pass"""
    cand_vuln = """def fetch_data(uid):
    q = "SELECT * FROM tbl WHERE id = " + str(uid)
    cursor.execute(q)
    return cursor.fetchall()"""

    # Test GateVerificationResult on valid patch
    res_valid = verifier.verify_patch(orig, cand_valid, "python")
    assert isinstance(res_valid, GateVerificationResult)
    assert res_valid.gate_1_syntax is True
    assert res_valid.gate_2_interface is True
    assert res_valid.gate_3_neutralization is True
    assert res_valid.gate_4_maintainability is True
    assert res_valid.gate_6_sast_rescan is True
    assert res_valid.is_100_percent_verified is True
    assert res_valid.delta_cc <= 0
    assert len(res_valid.passed_gates) == 5
    assert "Gate 1" in res_valid.passed_gates
    assert "gate_1" in res_valid.gate_details

    # Test GateVerificationResult on syntax error
    res_syntax = verifier.verify_patch(orig, cand_syntax_err, "python")
    assert isinstance(res_syntax, GateVerificationResult)
    assert res_syntax.gate_1_syntax is False
    assert res_syntax.is_100_percent_verified is False

    # Test GateVerificationResult on still vulnerable patch
    res_vuln = verifier.verify_patch(orig, cand_vuln, "python")
    assert isinstance(res_vuln, GateVerificationResult)
    assert res_vuln.gate_3_neutralization is False
    assert res_vuln.is_100_percent_verified is False

    # Test verify_candidate returns (True, VerifiedPatch)
    passed, best = verifier.verify_candidate(orig, cand_valid, "python", "cand_00", "data_svc.py")
    assert passed is True
    assert isinstance(best, VerifiedPatch)
    assert best.patch_id == "cand_00"
    assert "?" in best.remediated_code
    assert best.delta_cc <= 0
    assert len(best.passed_gates) == 5
    assert best.gate1_syntax is not None and best.gate1_syntax.passed is True
    assert best.gate2_interface is not None and best.gate2_interface.passed is True
    assert best.gate3_taint_neutralized is not None and best.gate3_taint_neutralized.passed is True
    assert best.gate4_maintainability is not None and best.gate4_maintainability.passed is True
    assert best.gate6_sast_rescan is not None and best.gate6_sast_rescan.passed is True


def test_multi_gate_verifier_gate1_syntax_error():
    """Verify Gate 1 fails on invalid CST syntax."""
    verifier = MultiGateVerifier()
    orig = "def run():\n    pass\n"
    cand = "def run(:\n    pass\n"  # syntax error
    passed, patch = verifier.verify_candidate(orig, cand, "python", "cand_bad", "test.py")
    assert passed is False
    assert patch is None


def test_multi_gate_verifier_gate2_interface_change():
    """Verify Gate 2 fails when function signature is altered."""
    verifier = MultiGateVerifier()
    orig = "def login(username, password):\n    pass\n"
    cand = "def login(user_data):\n    pass\n"  # altered param list
    passed, patch = verifier.verify_candidate(orig, cand, "python", "cand_bad", "test.py")
    assert passed is False
    assert patch is None


def test_multi_gate_verifier_gate2_param_name_mismatch():
    """Verify Gate 2 fails when parameter names differ."""
    verifier = MultiGateVerifier()
    orig = "def search(user_name, user_role):\n    pass\n"
    cand = "def search(name, role):\n    pass\n"  # different parameter names
    passed, patch = verifier.verify_candidate(orig, cand, "python", "cand_bad", "test.py")
    assert passed is False
    assert patch is None


def test_multi_gate_verifier_gate3_taint_not_neutralized():
    """Verify Gate 3 fails when string concatenation remains in SQL sink."""
    verifier = MultiGateVerifier()
    orig = "def query_db(uid):\n    cursor.execute('SELECT * FROM u WHERE id = ' + uid)\n"
    cand = "def query_db(uid):\n    cursor.execute('SELECT * FROM u WHERE id = ' + str(uid))\n"
    passed, patch = verifier.verify_candidate(orig, cand, "python", "cand_bad", "test.py")
    assert passed is False
    assert patch is None


def test_multi_gate_verifier_gate4_maintainability_regression():
    """Verify Gate 4 fails when patch introduces excessive cyclomatic complexity."""
    verifier = MultiGateVerifier()
    orig = """
def process(x):
    return x * 2
"""
    # Candidate introduces high cyclomatic complexity (3 branches)
    cand = """
def process(x):
    if x > 10:
        if x > 20:
            return x * 3
        return x * 2
    return x
"""
    passed, patch = verifier.verify_candidate(orig, cand, "python", "cand_complex", "test.py")
    assert passed is False
    assert patch is None


def test_multi_gate_verifier_gate6_sast_rescan_rejection():
    """Verify Gate 6 fails when candidate code still has an active taint path from source to sink."""
    verifier = MultiGateVerifier()
    orig = """
def query_user(req_val):
    sql = "SELECT * FROM users WHERE v = " + req_val
    cursor.execute(sql)
"""
    # Candidate changes variable name but retains vulnerable concatenation
    cand = """
def query_user(req_val):
    cleaned = req_val
    sql = "SELECT * FROM users WHERE v = " + cleaned
    cursor.execute(sql)
"""
    passed, patch = verifier.verify_candidate(orig, cand, "python", "cand_tainted", "test.py")
    assert passed is False
    assert patch is None


def test_multi_gate_verifier_javascript_full_verification():
    """Verify MultiGateVerifier approves a 100% compliant JavaScript parameterized patch."""
    verifier = MultiGateVerifier()
    orig = """
function getUser(userId) {
    const query = "SELECT * FROM users WHERE id = '" + userId + "'";
    return client.query(query);
}
"""
    cand = """
function getUser(userId) {
    const query = "SELECT * FROM users WHERE id = $1";
    return client.query(query, [userId]);
}
"""
    passed, verified_patch = verifier.verify_candidate(orig, cand, "javascript", "cand_js_01", "user.js")
    assert passed is True
    assert verified_patch is not None
    assert verified_patch.delta_cc <= 0
    assert len(verified_patch.passed_gates) == 5
    assert "$1" in verified_patch.remediated_code


def test_multi_gate_verifier_typescript_full_verification():
    """Verify MultiGateVerifier approves a 100% compliant TypeScript parameterized patch."""
    verifier = MultiGateVerifier()
    orig = """
async function searchProduct(term: string): Promise<any[]> {
    const query = `SELECT * FROM products WHERE name LIKE '%${term}%'`;
    return await db.query(query);
}
"""
    cand = """
async function searchProduct(term: string): Promise<any[]> {
    const query = "SELECT * FROM products WHERE name LIKE $1";
    return await db.query(query, [`%${term}%`]);
}
"""
    passed, verified_patch = verifier.verify_candidate(orig, cand, "typescript", "cand_ts_01", "product.ts")
    assert passed is True
    assert verified_patch is not None
    assert verified_patch.delta_cc <= 0
    assert len(verified_patch.passed_gates) == 5
    assert "$1" in verified_patch.remediated_code


def test_neural_oracle_assessment():
    """Verify NeuralOracle produces a valid NeuroAssessment with live Ollama or fallback."""
    oracle = NeuralOracle()
    sample_code = """
def search_products(category):
    sql = f"SELECT * FROM items WHERE cat = '{category}'"
    cursor.execute(sql)
"""
    finding = SymbolicFinding(
        cwe_id="CWE-89",
        source_node={"file": "test.py", "line": 2, "symbol": "category", "expression": "category"},
        sink_node={"file": "test.py", "line": 4, "symbol": "SQL Sink", "expression": "cursor.execute(sql)"},
        sanitized=False,
    )
    assessment = oracle.assess_finding(finding, sample_code, "python")
    assert isinstance(assessment, NeuroAssessment)
    assert 0.0 <= assessment.confidence_score <= 1.0
    assert assessment.risk_level in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "SAFE")
    assert isinstance(assessment.reasoning, str)
    assert len(assessment.reasoning) > 0


def test_neural_oracle_deterministic_fallback():
    """Verify NeuralOracle._deterministic_fallback_assessment produces a valid offline assessment."""
    oracle = NeuralOracle()
    finding = SymbolicFinding(
        cwe_id="CWE-89",
        source_node={"file": "test.py", "line": 1, "symbol": "raw_input", "expression": "raw_input"},
        sink_node={"file": "test.py", "line": 3, "symbol": "cursor.execute", "expression": "cursor.execute(sql)"},
        sanitized=False,
    )
    code = "def query(raw_input): cursor.execute('SELECT * FROM u WHERE id=' + raw_input)"
    assessment = oracle._deterministic_fallback_assessment(finding, code, "python")
    assert isinstance(assessment, NeuroAssessment)
    assert assessment.confidence_score == 1.0
    assert assessment.risk_level == "CRITICAL"
    assert assessment.sanitizer_detected is False
    assert "parameterized" in assessment.suggested_remediation.lower() or "?" in assessment.suggested_remediation


def test_neural_oracle_generate_candidate_patches():
    """Verify NeuralOracle generates repair candidates for vulnerable code."""
    oracle = NeuralOracle()
    sample_code = "def query(uid): cursor.execute('SELECT * FROM u WHERE id=' + uid)"
    finding = SymbolicFinding(
        cwe_id="CWE-89",
        source_node={"file": "test.py", "line": 1, "symbol": "uid", "expression": "uid"},
        sink_node={"file": "test.py", "line": 1, "symbol": "cursor.execute", "expression": "cursor.execute(...)"},
        sanitized=False,
    )
    candidates = oracle.generate_candidate_patches(sample_code, finding, "python", count=3)
    assert len(candidates) >= 1
    assert any("?" in c or "%s" in c or "execute(" in c for c in candidates)


def test_seed_knowledge_script_execution():
    """Verify scripts/seed_knowledge.py executes successfully and seeds the knowledge base."""
    from scripts.seed_knowledge import seed_knowledge_base
    seeded_count = seed_knowledge_base()
    assert seeded_count >= 5
