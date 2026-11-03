import sys
from pathlib import Path

SERVER_ROOT = Path(r"D:\4th-year\Senior-Project\codedee\codedee_server")
sys.path.insert(0, str(SERVER_ROOT))

import app.taint.walker
from prototype_dfg_fix import FixedDFGBuilder
app.taint.walker.DFGBuilder = FixedDFGBuilder

from app.taint.walker import SymbolicTaintWalker

walker = SymbolicTaintWalker()

# Test 1: Python % tuple formatting evasion test (the defect reproduction test)
code = """
from flask import request

def search_account():
    username = request.args.get("username")
    sql = "SELECT * FROM accounts WHERE name = '%s'" % (username,)
    cursor.execute(sql)
"""
findings = walker.analyze_code(code, "python", "percent_tuple.py")
print("Percent tuple findings:", len(findings))
vulns = [f for f in findings if not f.sanitized and f.severity == "CRITICAL"]
print("Critical vulns:", len(vulns))
assert len(vulns) >= 1, "Vulnerability must be detected!"
print("Defect 1 is completely resolved!")
