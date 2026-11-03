"""
test_adversarial_maintainability.py
Adversarial stress-testing of ISO/IEC 25010 Maintainability Engine (Stage 2).

Tests:
1. Empty functions (Python, JS, TS).
2. Huge single-line files (minified code / long statement sequences).
3. 100% comment files (no executable code).
4. Multiple identical duplicated functions.
5. Strict verification that NO forbidden metrics exist (SQALE, LCOM4, DIT, NOM, Raw LOC, Nesting Depth).
"""

import sys
from pathlib import Path
import pytest

# Ensure codedee_server is on sys.path
SERVER_ROOT = Path(r"D:\4th-year\Senior-Project\codedee\codedee_server")
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.maintainability.engine import MaintainabilityEngine
from app.models.contracts import MaintainabilityMetrics


@pytest.fixture
def engine():
    return MaintainabilityEngine()


def test_empty_function_python(engine):
    """Empty Python function with pass or docstring."""
    code_single = "def empty_fn(): pass"
    m_single = engine.analyze_code(code_single, "python")
    assert m_single.cyclomatic_complexity == 1
    assert m_single.cognitive_complexity == 0
    assert m_single.parameter_count == 0
    assert m_single.function_sloc == 1
    assert m_single.file_sloc == 1

    code_multi = """
def empty_fn():
    pass
"""
    m_multi = engine.analyze_code(code_multi, "python")
    assert m_multi.function_sloc == 2
    assert m_multi.file_sloc == 2


def test_empty_function_javascript(engine):
    """Empty JavaScript function."""
    code_single = "function emptyJs() {}"
    m_single = engine.analyze_code(code_single, "javascript")
    assert m_single.cyclomatic_complexity == 1
    assert m_single.cognitive_complexity == 0
    assert m_single.parameter_count == 0
    assert m_single.function_sloc == 1

    code_multi = """
function emptyJs() {
}
"""
    m_multi = engine.analyze_code(code_multi, "javascript")
    assert m_multi.function_sloc == 2


def test_empty_function_typescript(engine):
    """Empty TypeScript function with return type annotation."""
    code_single = "function emptyTs(a: number, b?: string): void {}"
    m_single = engine.analyze_code(code_single, "typescript")
    assert m_single.cyclomatic_complexity == 1
    assert m_single.cognitive_complexity == 0
    assert m_single.parameter_count == 2
    assert m_single.function_sloc == 1

    code_multi = """
function emptyTs(a: number, b?: string): void {
}
"""
    m_multi = engine.analyze_code(code_multi, "typescript")
    assert m_multi.parameter_count == 2
    assert m_multi.function_sloc == 2


def test_huge_single_line_file(engine):
    """A minified file with 50 statements on a single line (>5,000 chars)."""
    statements = [f"x{i} = {i} + 1" for i in range(100)]
    huge_line = "; ".join(statements)
    code = huge_line

    # Must not crash, recurse infinitely, or raise exception
    m = engine.analyze_code(code, "python")
    assert m.file_sloc == 1  # Exactly 1 line
    assert m.cyclomatic_complexity >= 1
    assert m.comment_density == 0.0


def test_100_percent_comments_python(engine):
    """A file consisting purely of comments and blank lines."""
    code = """
# Header comment
# Line 1
# Line 2
# Line 3

# Another comment block
# Footer comment
"""
    m = engine.analyze_code(code, "python")
    # Must not raise ZeroDivisionError
    assert m.file_sloc >= 1  # Safe floor to prevent div by zero
    assert m.comment_density > 0.8  # Vast majority is comments
    assert m.duplicated_blocks == 0


def test_100_percent_comments_javascript(engine):
    """A JS file consisting purely of block and line comments."""
    code = """
// Single line comment
/*
 Multi-line comment block
 Line 2
*/
// End of file
"""
    m = engine.analyze_code(code, "javascript")
    assert m.file_sloc >= 1
    assert m.comment_density > 0.5


def test_identical_duplicated_functions(engine):
    """File containing 5 identical non-trivial functions."""
    fn_template = """
def duplicate_target_{i}(val, factor):
    res = 0
    for step in range(val):
        if step % 2 == 0:
            res += step * factor
        else:
            res -= step
    return res
"""
    code = "\n".join(fn_template.format(i=i) for i in range(5))
    m = engine.analyze_code(code, "python")
    # Should detect duplicated blocks across identical function implementations
    assert m.duplicated_blocks >= 1
    assert m.cyclomatic_complexity >= 3


def test_strict_compliance_zero_forbidden_metrics(engine):
    """
    CRITICAL COMPLIANCE ASSERTION:
    Assert strict compliance that NO forbidden metrics exist:
    - SQALE (sqale, sqale_rating, sqale_index)
    - LCOM4 (lcom, lcom4, lack_of_cohesion)
    - DIT (dit, depth_of_inheritance_tree)
    - NOM (nom, number_of_methods)
    - Raw LOC (raw_loc, loc, lines_of_code, physical_loc)
    - Nesting Depth (nesting_depth, max_nesting_depth)
    """
    code = """
class Base:
    def method_one(self): pass

class Derived(Base):
    def method_two(self, x):
        if x > 0:
            if x > 10:
                return x
        return 0
"""
    metrics = engine.analyze_code(code, "python")
    summary = metrics.to_summary_dict()

    # The 8 authorized metrics
    AUTHORIZED_METRICS = {
        "cyclomatic_complexity",
        "cognitive_complexity",
        "parameter_count",
        "function_sloc",
        "file_sloc",
        "module_coupling",
        "duplicated_blocks",
        "comment_density",
    }
    assert set(summary.keys()) == AUTHORIZED_METRICS, f"Mismatch in metrics keys: {summary.keys()}"

    # Check forbidden metrics patterns
    FORBIDDEN_NAMES = [
        "sqale", "sqale_rating", "sqale_index",
        "lcom", "lcom4", "lack_of_cohesion",
        "dit", "depth_of_inheritance", "depth_of_inheritance_tree",
        "nom", "number_of_methods",
        "raw_loc", "loc", "physical_loc", "lines_of_code",
        "nesting_depth", "max_nesting_depth", "depth",
    ]

    # Verify on summary dict keys
    for key in summary.keys():
        for forbidden in FORBIDDEN_NAMES:
            assert key.lower() != forbidden, f"Forbidden metric found in summary: {key}"

    # Verify on MaintainabilityMetrics model fields
    model_field_names = set(MaintainabilityMetrics.model_fields.keys())
    for f in model_field_names:
        for forbidden in FORBIDDEN_NAMES:
            assert f.lower() != forbidden, f"Forbidden metric found in Pydantic schema: {f}"

    # Verify on instance attributes
    inst_attrs = dir(metrics)
    for attr in inst_attrs:
        for forbidden in FORBIDDEN_NAMES:
            assert attr.lower() != forbidden, f"Forbidden metric found as attribute: {attr}"

    # Verify engine class methods do not offer forbidden calculators
    engine_methods = dir(engine)
    for m_name in engine_methods:
        for forbidden in ["sqale", "lcom4", "compute_dit", "compute_nom", "compute_raw_loc", "compute_nesting_depth"]:
            assert forbidden not in m_name.lower(), f"Forbidden calculation method in engine: {m_name}"
