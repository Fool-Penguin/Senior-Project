import sys
import os

# Add codedee_server to path
sys.path.insert(0, os.path.abspath("codedee/codedee_server"))

from app.taint.walker import SymbolicTaintWalker
from app.maintainability.engine import MaintainabilityEngine
from app.oracle.neural_oracle import NeuralOracle

code = """def login_user(request):
    username = request.args.get('username')
    cursor = db.cursor()
    query = f"SELECT id, role, email FROM accounts WHERE username = '{username}'"
    cursor.execute(query)
    return cursor.fetchall()
"""

walker = SymbolicTaintWalker()
findings = walker.analyze_code(code, "python", "auth_controller.py")
print("Findings count:", len(findings))
if findings:
    f = findings[0]
    print("Finding CWE:", f.cwe_id, "Severity:", f.severity)
    print("Source:", f.source_node)
    print("Sink:", f.sink_node)
    print("Taint path steps:", len(f.taint_path))

engine = MaintainabilityEngine()
metrics = engine.analyze_code(code, "python", "auth_controller.py")
print("Maintainability metrics:", metrics.to_summary_dict())

oracle = NeuralOracle()
assessment = oracle.assess_finding(findings[0], code, "python")
print("NeuroAssessment:", assessment.risk_level, assessment.confidence_score, assessment.reasoning[:60])
