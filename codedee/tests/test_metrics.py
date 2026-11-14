"""Unit tests for Stage 3A Maintainability Engine."""

import unittest
from codedee.core.metrics import MaintainabilityEngine


class TestMaintainabilityEngine(unittest.TestCase):

    def test_python_maintainability_metrics(self):
        code = """
import os
import sys

# Compute something complex
def complex_function(a, b, c):
    total = a + b
    if a > 0:
        if b > 0:
            total += c
    elif a < 0:
        total -= c
    return total
"""
        metrics = MaintainabilityEngine.analyze_code(code, "python")
        self.assertEqual(metrics.language, "python")
        self.assertTrue(metrics.file_sloc > 0)
        self.assertTrue(metrics.comment_density > 0.0)
        self.assertEqual(metrics.module_coupling_ce, 2)  # os, sys
        self.assertEqual(len(metrics.functions), 1)

        fn = metrics.functions[0]
        self.assertEqual(fn.name, "complex_function")
        self.assertEqual(fn.parameter_count, 3)
        self.assertTrue(fn.cyclomatic_complexity >= 3)
        self.assertTrue(fn.cognitive_complexity >= 3)

    def test_javascript_maintainability_metrics(self):
        code = """
const fs = require('fs');
const path = require('path');

// Process request
function handle(req, res) {
    if (req.query) {
        res.send(req.query.id);
    }
}
"""
        metrics = MaintainabilityEngine.analyze_code(code, "javascript")
        self.assertEqual(metrics.language, "javascript")
        self.assertEqual(metrics.module_coupling_ce, 2)  # require fs, require path
        self.assertEqual(len(metrics.functions), 1)
        self.assertEqual(metrics.functions[0].parameter_count, 2)


if __name__ == "__main__":
    unittest.main()
