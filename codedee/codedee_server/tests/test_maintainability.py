"""
test_maintainability.py - Unit tests for ISO/IEC 25010 Maintainability Engine.

Verifies calculation of EXACTLY 8 ISO/IEC 25010 metrics:
Function-level:
  1. Cyclomatic Complexity (CC)
  2. Cognitive Complexity
  3. Parameter Count
  4. Function SLOC
File-level:
  5. File SLOC
  6. Module Coupling (Ce / Ca)
  7. Duplicated Blocks
  8. Comment Density

Verifies strict exclusion of: SQALE, LCOM4, DIT, NOM, Raw LOC, and Nesting Depth.
"""

import pytest
from app.maintainability.engine import MaintainabilityEngine
from app.models.contracts import MaintainabilityMetrics


@pytest.fixture
def engine():
    return MaintainabilityEngine()


def test_metric_schema_exactly_eight_metrics(engine):
    """Confirm the maintainability output schema exposes exactly the 8 authorized metrics."""
    code = """
def simple_add(a, b):
    # Sum two numbers
    return a + b
"""
    metrics = engine.analyze_code(code, "python")
    summary = metrics.to_summary_dict()

    expected_keys = {
        "cyclomatic_complexity",
        "cognitive_complexity",
        "parameter_count",
        "function_sloc",
        "file_sloc",
        "module_coupling",
        "duplicated_blocks",
        "comment_density",
    }
    assert set(summary.keys()) == expected_keys

    # Confirm prohibited metrics are completely absent
    prohibited = ["sqale_rating", "lcom4", "dit", "nom", "raw_loc", "nesting_depth"]
    for p in prohibited:
        assert p not in summary
        assert not hasattr(metrics, p)


def test_metric_1_cyclomatic_complexity(engine):
    """Test Cyclomatic Complexity (CC) calculation across branches."""
    # CC = 1 (base) + 2 (if, elif) + 1 (for) = 4
    code = """
def grade_classifier(score, items):
    if score >= 90:
        res = "A"
    elif score >= 80:
        res = "B"
    else:
        res = "C"

    for i in items:
        print(i)

    return res
"""
    metrics = engine.analyze_code(code, "python")
    assert metrics.cyclomatic_complexity == 4


def test_metric_2_cognitive_complexity(engine):
    """Test SonarQube Cognitive Complexity calculation with nesting penalty."""
    # Outer if: +1 (nesting=0)
    # Inner for: +1 + 1 (nesting=1) = +2
    # Inner if: +1 + 2 (nesting=2) = +3
    # Total cognitive complexity = 1 + 2 + 3 = 6
    code = """
def complex_logic(flag, matrix):
    if flag:
        for row in matrix:
            if len(row) > 0:
                print(row)
    return True
"""
    metrics = engine.analyze_code(code, "python")
    assert metrics.cognitive_complexity == 6


def test_metric_3_parameter_count(engine):
    """Test parameter count, verifying self/cls are excluded for methods."""
    code_fn = """
def multi_param(a, b, c, d=10, *args, **kwargs):
    return a + b + c + d
"""
    m_fn = engine.analyze_code(code_fn, "python")
    assert m_fn.parameter_count == 6

    code_method = """
class Handler:
    def process(self, request, response, options=None):
        return True
"""
    m_method = engine.analyze_code(code_method, "python")
    # 'self' must be excluded -> request, response, options = 3
    assert m_method.parameter_count == 3


def test_metric_4_function_sloc(engine):
    """Test function SLOC excluding comments and blank lines."""
    code = """
def sample_func(x):
    # This is a comment

    y = x + 1

    # Another comment
    return y
"""
    # Total function lines = 8
    # Non-comment, non-empty: def line, y = x + 1, return y -> 3 SLOC
    metrics = engine.analyze_code(code, "python")
    assert metrics.function_sloc == 3


def test_metric_5_file_sloc(engine):
    """Test file SLOC across entire script excluding comments and blanks."""
    code = """
# Header comment
# License MIT

import os
import sys

def foo():
    return 1

# Trailing comment
"""
    # Non-comment non-empty: import os, import sys, def foo():, return 1 -> 4
    metrics = engine.analyze_code(code, "python")
    assert metrics.file_sloc == 4


def test_metric_6_module_coupling(engine):
    """Test Efferent Coupling (Ce), Afferent Coupling (Ca), and Instability."""
    code = """
import os
import sys
from pathlib import Path
from math import sqrt, ceil

def do_work():
    pass
"""
    metrics = engine.analyze_code(code, "python", ca_coupling=2)
    summary = metrics.to_summary_dict()
    coupling = summary["module_coupling"]

    # os, sys, pathlib, math = 4 distinct external imports
    assert coupling["Ce"] >= 4
    assert coupling["Ca"] == 2
    # Instability = Ce / (Ce + Ca)
    expected_instability = round(coupling["Ce"] / (coupling["Ce"] + 2), 3)
    assert coupling["instability"] == expected_instability


def test_metric_7_duplicated_blocks(engine):
    """Test detection of duplicated statement sequences."""
    code = """
def first_block():
    a = 1
    b = 2
    c = a + b
    d = c * 2
    return d

def second_block():
    a = 1
    b = 2
    c = a + b
    d = c * 2
    return d
"""
    metrics = engine.analyze_code(code, "python")
    assert metrics.duplicated_blocks >= 1


def test_metric_8_comment_density(engine):
    """Test comment density calculation (comment lines / total volume)."""
    code = """
# Line 1 comment
# Line 2 comment
def run():
    x = 10
    return x
"""
    # 2 comment lines, 3 code lines -> density = 2 / (3 + 2) = 0.4
    metrics = engine.analyze_code(code, "python")
    assert metrics.comment_density == 0.4


def test_maintainability_javascript_metrics(engine):
    """Verify all 8 metrics for JavaScript code."""
    js_code = """
// Utility math module
import { helper } from './utils';
import lodash from 'lodash';

function calculateTax(income, rate, deductions) {
    // Check income threshold
    if (income > 50000) {
        if (rate > 0.2) {
            return (income - deductions) * rate;
        }
    }
    return income * 0.1;
}
"""
    metrics = engine.analyze_code(js_code, "javascript")
    assert metrics.cyclomatic_complexity >= 3
    assert metrics.cognitive_complexity >= 3
    assert metrics.parameter_count == 3
    assert metrics.module_coupling_ce == 2
    assert metrics.comment_density > 0.0
