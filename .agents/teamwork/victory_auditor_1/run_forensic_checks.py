import os
import re
from pathlib import Path

app_dir = Path("codedee/codedee_server/app")
findings = []

for p in app_dir.rglob("*.py"):
    content = p.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Check 1: single-line or trivial return True/False/mock
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped in ("return True", "return False", "return []", "return {}") and i > 0:
            prev = lines[i-1].strip()
            if prev.startswith("def ") or prev.endswith(":"):
                findings.append((str(p), i+1, f"Trivial return: {stripped} after {prev}"))

        if "unittest.mock" in stripped or "MagicMock" in stripped:
            findings.append((str(p), i+1, f"Mock in production code: {stripped}"))

print(f"Total production code findings: {len(findings)}")
for f in findings:
    print(f)
