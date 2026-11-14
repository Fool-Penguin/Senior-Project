"""Unit tests for Stage 3B Neural Oracle, Neuro-Symbolic Reconciliation, & Master Pipeline."""

import unittest
from codedee.core.pipeline import CodeDEEPipeline
from codedee.core.taint_walker import TaintFinding
from codedee.core.neural_oracle import NeuralOracle


class TestPipeline(unittest.TestCase):

    def test_pipeline_symbolic_mode(self):
        code = """
import os

def ping(host):
    # Missing sanitization
    cmd = "ping -c 1 " + host
    os.system(cmd)
    return True
"""
        pipeline = CodeDEEPipeline(enable_neural_oracle=False)
        report = pipeline.analyze(code, "python")

        self.assertEqual(report.language, "python")
        self.assertTrue(report.maintainability.file_sloc > 0)
        self.assertEqual(report.maintainability.module_coupling_ce, 1)  # os
        self.assertEqual(report.total_findings, 1)

        vuln = report.vulnerabilities[0]
        self.assertEqual(vuln.cwe_id, "CWE-78")
        self.assertEqual(vuln.risk_level, "Critical")
        self.assertEqual(vuln.cvss_v31_base, 9.8)
        self.assertEqual(vuln.source_param, "host")
        self.assertEqual(vuln.sink_callee, "os.system")
        self.assertEqual(vuln.status, "CONFIRMED")

    def test_neuro_symbolic_reconciliation_in_family_refinement(self):
        """Case A: Symbolic flags CWE-89 (DB_QUERY), Neural refines to CWE-943 (NoSQLi, same DB_QUERY family) -> CONFIRMED."""
        finding = TaintFinding(
            function_name="find_user",
            source_param="req_data",
            sink_callee="db.users.find",
            sink_line=5,
            candidate_cwe="CWE-89",
            owasp_category="A05:2025-Injection",
            taint_path=["req_data", "db.users.find"],
            has_sanitizer=False,
            code_slice="def find_user(req_data): return db.users.find({'username': req_data})",
        )
        v = NeuralOracle.reconcile_symbolic_and_neural(
            finding=finding,
            vulnerability_detected=True,
            neural_cwe="CWE-943",
            neural_reason="Unvalidated dict passed into MongoDB find() allows NoSQL operator injection.",
        )
        self.assertEqual(v.status, "CONFIRMED")
        self.assertEqual(v.cwe_id, "CWE-943")
        self.assertEqual(v.symbolic_cwe, "CWE-89")
        self.assertEqual(v.neural_cwe, "CWE-943")
        self.assertEqual(v.risk_level, "High")
        self.assertEqual(v.cvss_v31_base, 8.6)
        self.assertIn("NoSQL Injection", v.cwe_name)

    def test_neuro_symbolic_reconciliation_out_of_family_conflict(self):
        """Case C: Symbolic flags CWE-89 (DB_QUERY), Neural hallucinates CWE-79 (WEB_TEMPLATE) -> NEEDS_REVIEW anchored to CWE-89."""
        finding = TaintFinding(
            function_name="query_user",
            source_param="user_id",
            sink_callee="cursor.execute",
            sink_line=4,
            candidate_cwe="CWE-89",
            owasp_category="A05:2025-Injection",
            taint_path=["user_id", "sql", "cursor.execute"],
            has_sanitizer=False,
            code_slice="def query_user(user_id): cursor.execute('SELECT * FROM u WHERE id=' + user_id)",
        )
        v = NeuralOracle.reconcile_symbolic_and_neural(
            finding=finding,
            vulnerability_detected=True,
            neural_cwe="CWE-79",
            neural_reason="Tainted input reaches output.",
        )
        self.assertEqual(v.status, "NEEDS_REVIEW")
        self.assertEqual(v.cwe_id, "CWE-89")  # Kept anchored to physical AST sink!
        self.assertEqual(v.symbolic_cwe, "CWE-89")
        self.assertEqual(v.neural_cwe, "CWE-79")
        self.assertIn("Cross-Family Disagreement", v.reconciliation_note)

    def test_neuro_symbolic_reconciliation_sanitizer_rejected(self):
        """Case B: Symbolic flags CWE-89 candidate, Neural verifies parameterized query -> REJECTED (CWE-NONE)."""
        finding = TaintFinding(
            function_name="safe_query",
            source_param="user_id",
            sink_callee="cursor.execute",
            sink_line=4,
            candidate_cwe="CWE-89",
            owasp_category="A05:2025-Injection",
            taint_path=["user_id", "cursor.execute"],
            has_sanitizer=False,
            code_slice="def safe_query(user_id): cursor.execute('SELECT * FROM u WHERE id=%s', (user_id,))",
        )
        v = NeuralOracle.reconcile_symbolic_and_neural(
            finding=finding,
            vulnerability_detected=False,
            neural_cwe="CWE-NONE",
            neural_reason="Query uses parameterized tuple binding.",
        )
        self.assertEqual(v.status, "REJECTED")
        self.assertEqual(v.cwe_id, "CWE-NONE")
        self.assertEqual(v.risk_level, "None")
        self.assertEqual(v.cvss_v31_base, 0.0)


if __name__ == "__main__":
    unittest.main()
