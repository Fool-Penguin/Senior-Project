"""Unit tests for Stage 3B Symbolic Taint Walker."""

import unittest
from codedee.core.graph_builder import GraphBuilder
from codedee.core.taint_walker import SymbolicTaintWalker


class TestSymbolicTaintWalker(unittest.TestCase):

    def test_sql_injection_detection(self):
        code = """
def search_user(username):
    sql = "SELECT * FROM users WHERE name = '" + username + "'"
    cursor.execute(sql)
"""
        graphs = GraphBuilder.build_all(code, "python")
        findings = SymbolicTaintWalker.find_vulnerability_candidates(graphs, code)

        self.assertTrue(len(findings) >= 1)
        finding = findings[0]
        self.assertEqual(finding.candidate_cwe, "CWE-89")
        self.assertEqual(finding.source_param, "username")
        self.assertEqual(finding.sink_callee, "cursor.execute")
        self.assertFalse(finding.has_sanitizer)

    def test_command_injection_detection(self):
        code = """
function pingHost(host) {
    const cmd = "ping -c 1 " + host;
    child_process.exec(cmd);
}
"""
        graphs = GraphBuilder.build_all(code, "javascript")
        findings = SymbolicTaintWalker.find_vulnerability_candidates(graphs, code)

        self.assertTrue(len(findings) >= 1)
        finding = findings[0]
        self.assertEqual(finding.candidate_cwe, "CWE-78")
        self.assertEqual(finding.source_param, "host")
        self.assertEqual(finding.sink_callee, "child_process.exec")


if __name__ == "__main__":
    unittest.main()
