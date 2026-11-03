"""
Adversarial Test Suite 2: Pydantic Contract Boundaries & Strict Validation.
Tests app/models/contracts.py for:
1. confidence_score boundaries: ge=0.0, le=1.0, negative, >1.0, non-numeric.
2. risk_level handling: standard values vs arbitrary invalid strings.
3. MaintainabilityMetrics boundaries: CC >= 1, SLOC >= 1, comment_density [0.0, 1.0].
4. GeneratePatchesRequest bounds: candidate_count [1, 5].
5. SecurityNodeOutput schema completeness and mandatory field enforcement.
"""

import sys
from pathlib import Path
import pytest
from pydantic import ValidationError

# Add codedee_server to path
server_root = Path(r"d:\4th-year\Senior-Project\codedee\codedee_server")
sys.path.insert(0, str(server_root))

from app.models.contracts import (
    CodeLocation,
    GeneratePatchesRequest,
    MaintainabilityMetrics,
    NeuroAssessment,
    PipelineMetadata,
    SecurityNodeOutput,
    SymbolicFinding,
    TaintStep,
    VerifiedPatch,
)

# -----------------------------------------------------------------------------
# 1. NeuroAssessment Boundaries (confidence_score & risk_level)
# -----------------------------------------------------------------------------

def test_neuro_assessment_confidence_score_valid_boundaries():
    """Verify confidence_score exactly at 0.0 and 1.0 is valid."""
    assessment_0 = NeuroAssessment(
        confidence_score=0.0,
        risk_level="SAFE",
        sanitizer_detected=True,
        reasoning="Sanitizer present",
    )
    assert assessment_0.confidence_score == 0.0

    assessment_1 = NeuroAssessment(
        confidence_score=1.0,
        risk_level="CRITICAL",
        sanitizer_detected=False,
        reasoning="Direct injection flaw",
    )
    assert assessment_1.confidence_score == 1.0

@pytest.mark.parametrize("invalid_score", [-0.001, -1.0, -100.0, 1.001, 1.5, 999.0])
def test_neuro_assessment_confidence_score_out_of_bounds(invalid_score):
    """Adversarial: confidence_score < 0.0 or > 1.0 must be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        NeuroAssessment(
            confidence_score=invalid_score,
            risk_level="HIGH",
            sanitizer_detected=False,
            reasoning="Testing boundary",
        )
    errors = exc_info.value.errors()
    assert any("confidence_score" in str(err["loc"]) for err in errors)

@pytest.mark.parametrize("bad_type_score", ["not_a_float", None, [0.5], {"score": 0.5}])
def test_neuro_assessment_confidence_score_invalid_types(bad_type_score):
    """Adversarial: non-numeric confidence_score must raise ValidationError."""
    with pytest.raises(ValidationError):
        NeuroAssessment(
            confidence_score=bad_type_score,
            risk_level="HIGH",
            sanitizer_detected=False,
            reasoning="Testing bad types",
        )

def test_neuro_assessment_risk_level_validation_check():
    """
    Adversarial & Empirical check: Check how risk_level behaves.
    Documented valid risk levels: CRITICAL, HIGH, MEDIUM, LOW, SAFE.
    Does Pydantic enforce this set or allow arbitrary strings?
    """
    valid_levels = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "SAFE"]
    for lvl in valid_levels:
        n = NeuroAssessment(
            confidence_score=0.9,
            risk_level=lvl,
            sanitizer_detected=False,
            reasoning=f"Risk level {lvl}",
        )
        assert n.risk_level == lvl

    # Check invalid string
    # If risk_level is typed as 'str' without Enum or Literal, this will instantiate without error.
    # We record whether contracts.py has strict enum or unconstrained string.
    arbitrary_level = "SUPER_EXTREME_DOOM"
    n_arbitrary = NeuroAssessment(
        confidence_score=0.9,
        risk_level=arbitrary_level,
        sanitizer_detected=False,
        reasoning="Test arbitrary risk",
    )
    # If this succeeds, it proves risk_level is an unconstrained string in contracts.py!
    is_unconstrained = (n_arbitrary.risk_level == arbitrary_level)
    print(f"\n[EMPIRICAL OBSERVATION] risk_level unconstrained: {is_unconstrained}")
    assert is_unconstrained is True, "Expected contracts.py risk_level to be str type"

# -----------------------------------------------------------------------------
# 2. MaintainabilityMetrics Boundaries (8 ISO/IEC 25010 Metrics)
# -----------------------------------------------------------------------------

def test_maintainability_metrics_valid_defaults():
    m = MaintainabilityMetrics()
    assert m.cyclomatic_complexity == 1
    assert m.cognitive_complexity == 0
    assert m.parameter_count == 0
    assert m.function_sloc == 1
    assert m.file_sloc == 1
    assert m.module_coupling_ce == 0
    assert m.module_coupling_ca == 0
    assert m.duplicated_blocks == 0
    assert m.comment_density == 0.0

@pytest.mark.parametrize("bad_cc", [0, -1, -99])
def test_maintainability_metrics_invalid_cyclomatic_complexity(bad_cc):
    """Adversarial: Cyclomatic complexity must be >= 1."""
    with pytest.raises(ValidationError):
        MaintainabilityMetrics(cyclomatic_complexity=bad_cc)

@pytest.mark.parametrize("bad_cognitive", [-1, -10])
def test_maintainability_metrics_invalid_cognitive_complexity(bad_cognitive):
    """Adversarial: Cognitive complexity must be >= 0."""
    with pytest.raises(ValidationError):
        MaintainabilityMetrics(cognitive_complexity=bad_cognitive)

@pytest.mark.parametrize("bad_density", [-0.01, 1.01, 2.5, -5.0])
def test_maintainability_metrics_invalid_comment_density(bad_density):
    """Adversarial: comment_density must be in [0.0, 1.0]."""
    with pytest.raises(ValidationError):
        MaintainabilityMetrics(comment_density=bad_density)

@pytest.mark.parametrize("bad_sloc", [0, -1, -50])
def test_maintainability_metrics_invalid_slocs(bad_sloc):
    """Adversarial: function_sloc and file_sloc must be >= 1."""
    with pytest.raises(ValidationError):
        MaintainabilityMetrics(function_sloc=bad_sloc)
    with pytest.raises(ValidationError):
        MaintainabilityMetrics(file_sloc=bad_sloc)

def test_maintainability_metrics_summary_dict():
    """Verify ISO/IEC 25010 summary formatting and instability calculation."""
    m = MaintainabilityMetrics(
        cyclomatic_complexity=5,
        cognitive_complexity=3,
        parameter_count=2,
        function_sloc=20,
        file_sloc=100,
        module_coupling_ce=3,
        module_coupling_ca=1,
        duplicated_blocks=0,
        comment_density=0.25,
    )
    summary = m.to_summary_dict()
    assert summary["cyclomatic_complexity"] == 5
    assert summary["module_coupling"]["Ce"] == 3
    assert summary["module_coupling"]["Ca"] == 1
    # instability = Ce / (Ce + Ca) = 3 / 4 = 0.75
    assert summary["module_coupling"]["instability"] == 0.75

# -----------------------------------------------------------------------------
# 3. GeneratePatchesRequest Boundaries (candidate_count)
# -----------------------------------------------------------------------------

def test_generate_patches_request_valid():
    req = GeneratePatchesRequest(issue_id="ISSUE_123", candidate_count=3)
    assert req.candidate_count == 3

    # Alias reconciliation num_candidates -> candidate_count
    req2 = GeneratePatchesRequest(issue_id="ISSUE_123", num_candidates=4)
    assert req2.candidate_count == 4

@pytest.mark.parametrize("bad_count", [0, -1, 6, 10, 100])
def test_generate_patches_request_out_of_bounds(bad_count):
    """Adversarial: candidate_count must be between 1 and 5."""
    with pytest.raises(ValidationError):
        GeneratePatchesRequest(issue_id="ISSUE_123", candidate_count=bad_count)

# -----------------------------------------------------------------------------
# 4. SymbolicFinding & SecurityNodeOutput Mandatory Fields
# -----------------------------------------------------------------------------

def test_symbolic_finding_confidence_boundaries():
    """Verify symbolic_confidence is bounded between 0.0 and 1.0."""
    sf_valid = SymbolicFinding(symbolic_confidence=0.5)
    assert sf_valid.symbolic_confidence == 0.5

    with pytest.raises(ValidationError):
        SymbolicFinding(symbolic_confidence=-0.1)

    with pytest.raises(ValidationError):
        SymbolicFinding(symbolic_confidence=1.1)

def test_symbolic_finding_reconciliation():
    """Verify that 'source' and 'sink' are reconciled into 'source_node' and 'sink_node'."""
    sf = SymbolicFinding(
        source={"file": "vuln.py", "line": 10, "symbol": "user_id"},
        sink={"file": "vuln.py", "line": 25, "symbol": "query"},
    )
    assert sf.source_node["symbol"] == "user_id"
    assert sf.sink_node["symbol"] == "query"

def test_security_node_output_missing_required_fields():
    """Adversarial: Missing mandatory fields in Stage 3B contract must fail."""
    with pytest.raises(ValidationError):
        # Missing target_file, symbolic_finding, pipeline_metadata
        SecurityNodeOutput(issue_id="TEST_001")

def test_security_node_output_full_contract_compliance():
    """Verify that a fully populated SecurityNodeOutput satisfies the Stage 3B contract."""
    output = SecurityNodeOutput(
        issue_id="SEC_PY_001_12",
        target_file="/app/routes/vuln.py",
        symbolic_finding=SymbolicFinding(
            cwe_id="CWE-89",
            severity="HIGH",
            source_node={"file": "/app/routes/vuln.py", "line": 5, "symbol": "req.args"},
            sink_node={"file": "/app/routes/vuln.py", "line": 12, "symbol": "cursor.execute"},
            taint_path=[{"step": 1, "symbol": "user_input"}],
        ),
        neuro_assessment=NeuroAssessment(
            confidence_score=0.98,
            risk_level="HIGH",
            sanitizer_detected=False,
            reasoning="Unparameterized SQL string formatting detected.",
        ),
        pipeline_metadata=PipelineMetadata(
            file_path="/app/routes/vuln.py",
            language="python",
            maintainability_metrics=MaintainabilityMetrics().to_summary_dict(),
        ),
    )
    assert output.issue_id == "SEC_PY_001_12"
    assert output.neuro_assessment.confidence_score == 0.98
    assert output.symbolic_finding.cwe_id == "CWE-89"

if __name__ == "__main__":
    pytest.main(["-v", "-s", __file__])
