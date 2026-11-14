import pytest
from pathlib import Path
from codedee.core.pipeline import CodeDEEPipeline
from codedee.core.verifier import MultiGateVerifier

class TestSemester2Integration:
    """Test suite for Semester 2 Phase 1-3 features."""

    def test_pipeline_with_project_root_indexing(self):
        pipeline = CodeDEEPipeline(project_root=Path("codedee"), enable_neural_oracle=False)
        assert pipeline.resolver is not None
        assert len(pipeline.resolver.symbols) > 100
        assert pipeline.call_graph is not None
        assert pipeline.call_graph.graph.number_of_nodes() > 100

    def test_dynamic_sandbox_pass(self):
        good_patch = """
def sanitize_path(filename: str) -> str:
    import os
    return os.path.basename(filename)
"""
        test_assertion = "assert sanitize_path('../../etc/passwd') == 'passwd'"
        res = MultiGateVerifier.run_sandbox_assertion(good_patch, "python", test_assertion)
        assert res.passed is True
        assert "verified in isolated sandbox" in res.details

    def test_dynamic_sandbox_assertion_failure(self):
        bad_patch = """
def sanitize_path(filename: str) -> str:
    return filename
"""
        test_assertion = "assert sanitize_path('../../etc/passwd') == 'passwd'"
        res = MultiGateVerifier.run_sandbox_assertion(bad_patch, "python", test_assertion)
        assert res.passed is False
        assert "Sandbox execution error" in res.details
