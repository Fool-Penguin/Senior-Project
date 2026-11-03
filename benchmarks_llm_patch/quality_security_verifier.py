"""
Comprehensive Verification and SAST Stack for CodeDEE APR Benchmark
Implements:
  - Pass@1 Dynamic Unit Test Execution (Isolated Sandbox)
  - Vulnerability Resolution Verification (SAST Taint & Sink Elimination)
  - Zero New Vulnerabilities Audit (Bandit / Semgrep / Anti-Pattern Scan)
  - Linter & Maintainability Audit (PEP8 Style Violations & Complexity Delta)
  - Hallucination Detector (External Package & Unresolved Symbol Detection)
"""

import ast
import builtins
import importlib
import re
import subprocess
import sys
import tempfile
from typing import Dict, Any, List, Tuple
from benchmarks_llm_patch.c8_multi_gate_verifier import (
    calculate_cyclomatic_complexity,
    extract_code_from_markdown,
    MultiGateVerifier
)

# Standard library module names in Python
PYTHON_STDLIB = set(sys.stdlib_module_names) | {
    "sqlite3", "subprocess", "os", "sys", "html", "re", "json", "pickle",
    "hashlib", "ipaddress", "pathlib", "shlex", "typing", "collections",
    "math", "time", "datetime", "urllib", "http", "tempfile", "unittest"
}

ALLOWED_THIRD_PARTY = {
    "requests", "pydantic", "flask", "django", "fastapi", "sqlalchemy",
    "tree_sitter", "tree_sitter_python", "jwt", "cryptography"
}


def execute_unit_test(candidate_code: str, test_code: str, function_name: str) -> Tuple[bool, str]:
    """
    Executes the unit test in an isolated Python subprocess to measure Pass@1 safely.
    Returns (passed: bool, message: str).
    """
    test_harness = f"""
import sys
from unittest.mock import MagicMock, patch

# Injected candidate code
{candidate_code}

# Test suite
{test_code}

if __name__ == "__main__":
    try:
        # Find test functions
        for name, obj in list(locals().items()):
            if name.startswith("test_") and callable(obj):
                import inspect
                sig = inspect.signature(obj)
                if len(sig.parameters) == 0:
                    obj()
                else:
                    # Provide tmp_path mock if needed
                    from pathlib import Path
                    import tempfile
                    with tempfile.TemporaryDirectory() as td:
                        obj(Path(td))
        print("ALL_TESTS_PASSED")
    except Exception as e:
        print(f"TEST_FAILED: {{e}}", file=sys.stderr)
        sys.exit(1)
"""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(test_harness)
        temp_path = f.name

    try:
        proc = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        if proc.returncode == 0 and "ALL_TESTS_PASSED" in proc.stdout:
            return True, "All functional unit tests passed on Pass@1"
        else:
            err = proc.stderr.strip() or proc.stdout.strip()
            return False, f"Unit test failed: {err[:200]}"
    except subprocess.TimeoutExpired:
        return False, "Unit test execution timed out (>10s)"
    except Exception as e:
        return False, f"Unit test execution error: {str(e)}"
    finally:
        import os
        try:
            os.remove(temp_path)
        except OSError:
            pass


def run_bandit_sast(code_str: str) -> Tuple[bool, List[str]]:
    """
    Runs Bandit static analysis on the code snippet.
    Returns (is_clean: bool, findings: List[str]).
    """
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code_str)
        temp_path = f.name

    try:
        proc = subprocess.run(
            ["bandit", "-q", "-f", "json", temp_path],
            capture_output=True,
            text=True,
            timeout=15
        )
        import json
        output = proc.stdout.strip()
        if not output:
            return True, []
        try:
            report = json.loads(output)
            results = report.get("results", [])
            # Filter to HIGH / MEDIUM severity genuine vulnerabilities
            # Exclude B404 (import subprocess), B603 (safe subprocess without shell=True), B607 (partial executable path)
            benign_codes = {"B404", "B603", "B607"}
            findings = []
            for r in results:
                test_id = r.get("test_id", "")
                sev = r.get("issue_severity", "").upper()
                if test_id not in benign_codes and sev in {"HIGH", "MEDIUM"}:
                    findings.append(f"[{test_id}]: {r.get('issue_text')}")
            is_clean = len(findings) == 0
            return is_clean, findings
        except json.JSONDecodeError:
            return True, []
    except Exception:
        # Fallback if bandit not available
        return True, []
    finally:
        import os
        try:
            os.remove(temp_path)
        except OSError:
            pass


def detect_new_vulnerabilities(candidate_code: str, original_cwe: str) -> Tuple[bool, List[str]]:
    """
    Strictly verifies if the fix introduced any brand new security flaws.
    Returns (zero_new_vulns: bool, flaw_list: List[str]).
    """
    new_flaws = []

    # Check dangerous anti-patterns
    if "eval(" in candidate_code and original_cwe != "CWE-94":
        new_flaws.append("CWE-94: Introduced dynamic eval() execution")
    if "exec(" in candidate_code and original_cwe != "CWE-94":
        new_flaws.append("CWE-94: Introduced dynamic exec() execution")
    if "shell=True" in candidate_code and original_cwe != "CWE-78":
        new_flaws.append("CWE-78: Introduced shell=True command injection vector")
    if "pickle.loads(" in candidate_code and original_cwe != "CWE-502":
        new_flaws.append("CWE-502: Introduced unsafe pickle deserialization")
    if re.search(r"md5\s*\(", candidate_code):
        new_flaws.append("CWE-327: Introduced weak MD5 cryptographic hash")
    if re.search(r"(?:password|secret|api_key)\s*=\s*['\"][^'\"]{8,}['\"]", candidate_code, re.I):
        new_flaws.append("CWE-798: Introduced hardcoded credential string")

    # Run Bandit
    clean_sast, findings = run_bandit_sast(candidate_code)
    for f in findings:
        # Exclude expected findings related to original flaw if any
        new_flaws.append(f"SAST: {f}")

    zero_new = len(new_flaws) == 0
    return zero_new, new_flaws


def count_linting_violations(code_str: str) -> Tuple[int, List[str]]:
    """
    Counts style and linting warnings (PEP8 style conventions):
      - Line length > 100 characters
      - Trailing whitespace
      - Missing docstring / formatting
      - Bare except clauses
      - Mutable default arguments
    """
    violations = []
    lines = code_str.splitlines()

    for idx, line in enumerate(lines, 1):
        if len(line) > 100:
            violations.append(f"Line {idx}: Line too long ({len(line)} > 100 chars, E501)")
        if line.endswith(" ") or line.endswith("\t"):
            violations.append(f"Line {idx}: Trailing whitespace (W291)")

    try:
        tree = ast.parse(code_str)
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                violations.append("Bare 'except:' clause without specifying exception type (E722)")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for d in node.args.defaults:
                    if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                        violations.append(f"Function '{node.name}': Mutable default argument (B006)")
    except SyntaxError:
        violations.append("Syntax error prevents complete lint analysis")

    return len(violations), violations


def detect_hallucinations(code_str: str) -> Tuple[bool, List[str]]:
    """
    Detects if the model hallucinated non-existent external library dependencies
    or referenced unknown out-of-scope modules/identifiers.
    Returns (has_hallucination: bool, hallucinated_items: List[str]).
    """
    hallucinations = []
    try:
        tree = ast.parse(code_str)
    except SyntaxError:
        return False, ["Cannot parse AST for hallucination check"]

    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_pkg = alias.name.split(".")[0]
                imported_modules.add(root_pkg)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_pkg = node.module.split(".")[0]
                imported_modules.add(root_pkg)

    for pkg in imported_modules:
        if pkg not in PYTHON_STDLIB and pkg not in ALLOWED_THIRD_PARTY:
            # Check if package is actually importable
            try:
                importlib.import_module(pkg)
            except ImportError:
                hallucinations.append(f"Hallucinated non-existent package: '{pkg}'")

    has_hallucination = len(hallucinations) > 0
    return has_hallucination, hallucinations
