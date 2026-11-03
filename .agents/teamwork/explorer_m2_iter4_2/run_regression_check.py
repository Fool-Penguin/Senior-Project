import sys
import pytest

# Pre-import and patch before tests run
sys.path.insert(0, 'codedee/codedee_server')
from app.graphs.dfg import DFGBuilder
from prototype_fix import _extract_pattern_targets, patched_process_statement

DFGBuilder._extract_pattern_targets = _extract_pattern_targets
DFGBuilder._process_statement = patched_process_statement

# Run existing server tests
res = pytest.main(["codedee/codedee_server/tests", "-v", "--tb=short"])
print("Server tests exit code:", res)

# Run adversarial tests (expect only Defect 1 to fail, and all others including Defect 2 to pass)
res2 = pytest.main([".agents/teamwork/challenger_m2_iter3_2/test_adversarial_cross_language.py", "-v", "--tb=short"])
print("Adversarial tests exit code:", res2)
