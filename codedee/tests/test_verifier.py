"""Unit tests for Stage 4 In-Memory Multi-Gate Verifier."""

import unittest
from codedee.core.verifier import MultiGateVerifier


class TestMultiGateVerifier(unittest.TestCase):

    def test_sql_injection_fix_passes_all_gates(self):
        original = """
def get_user(user_id):
    query = "SELECT * FROM users WHERE id = '" + user_id + "'"
    cursor.execute(query)
"""
        # Proper parameterized fix
        valid_fixed = """
def get_user(user_id):
    query = "SELECT * FROM users WHERE id = %s"
    cursor.execute(query, (user_id,))
"""
        verdict = MultiGateVerifier.verify_patch(
            original_code=original,
            fixed_code=valid_fixed,
            language="python",
            target_cwe="CWE-89",
        )
        self.assertTrue(verdict.gate1_syntax.passed)
        self.assertTrue(verdict.gate2_interface.passed)
        self.assertTrue(verdict.gate3_sink_neutralized.passed)
        self.assertTrue(verdict.gate4_maintainability.passed)
        self.assertTrue(verdict.gate6_sast_clean.passed)
        self.assertTrue(verdict.all_passed)

    def test_syntax_error_patch_rejected_at_gate1(self):
        original = "def foo(x):\n    return x\n"
        invalid_fixed = "def foo(x):\n    return x + \n"  # Syntax error

        verdict = MultiGateVerifier.verify_patch(
            original_code=original,
            fixed_code=invalid_fixed,
            language="python",
            target_cwe="CWE-89",
        )
        self.assertFalse(verdict.gate1_syntax.passed)
        self.assertFalse(verdict.all_passed)

    def test_interface_break_rejected_at_gate2(self):
        original = "def search(user_id):\n    pass\n"
        altered_interface = "def search(user_id, extra_param):\n    pass\n"

        verdict = MultiGateVerifier.verify_patch(
            original_code=original,
            fixed_code=altered_interface,
            language="python",
            target_cwe="CWE-89",
        )
        self.assertTrue(verdict.gate1_syntax.passed)
        self.assertFalse(verdict.gate2_interface.passed)
        self.assertFalse(verdict.all_passed)


if __name__ == "__main__":
    unittest.main()
