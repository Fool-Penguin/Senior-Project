"""
Security & CWE Competitor Benchmark - Test Execution Runner
===========================================================
This test script demonstrates the concrete execution difference between:
  1. The VULNERABLE functions (which allow input to alter execution flow)
  2. The REMEDIATED functions (which enforce CodeLens AI defensive guardrails)

Run this test script directly:
    python 01_project_proposals/run_security_tests.py
"""

import os
import sys
import tempfile
import sqlite3
from pathlib import Path

# Add proposal directory to import path
sys.path.insert(0, str(Path(__file__).parent))

from security_competitor_test_cases import (
    vulnerable_cwe_089_user_login,
    remediated_cwe_089_user_login,
    vulnerable_cwe_022_read_tenant_document,
    remediated_cwe_022_read_tenant_document,
    vulnerable_owasp_llm06_agent_delete_project_artifact,
    remediated_owasp_llm06_agent_delete_project_artifact,
    vulnerable_owasp_llm01_agent_math_calculator,
    remediated_owasp_llm01_agent_math_calculator,
    remediated_cwe_078_system_ping,
)


def run_cwe_089_sql_injection_demo(custom_input: str = None):
    print("\n" + "=" * 70)
    print("TEST 1: CWE-89 (SQL Injection) Execution Demonstration")
    print("=" * 70)

    temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    temp_db_path = temp_db.name
    temp_db.close()

    try:
        conn = sqlite3.connect(temp_db_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE accounts (id INTEGER, role TEXT, email TEXT, username TEXT, tenant_id TEXT)")
        cur.execute("INSERT INTO accounts VALUES (1, 'ADMIN_SUPERUSER', 'admin@corp.internal', 'admin', 'tenant_secret')")
        cur.execute("INSERT INTO accounts VALUES (2, 'NORMAL_USER', 'alice@corp.internal', 'alice', 'tenant_a')")
        conn.commit()
        conn.close()

        print("[*] Normal Query: Looking up 'alice' in 'tenant_a':")
        normal_res = vulnerable_cwe_089_user_login(temp_db_path, "alice", "tenant_a")
        print(f"    Result: {normal_res}")

        injected_input = custom_input if custom_input is not None else "admin' OR '1'='1"
        print(f"\n[*] Triggering Input: username = \"{injected_input}\"")

        vuln_res = vulnerable_cwe_089_user_login(temp_db_path, injected_input, "tenant_a")
        print(f"    [!] Vulnerable Output: {vuln_res}")

        rem_res = remediated_cwe_089_user_login(temp_db_path, injected_input, "tenant_a")
        print(f"    [+] Remediated Output: {rem_res}")

    finally:
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)


def run_cwe_022_path_traversal_demo(custom_input: str = None):
    print("\n" + "=" * 70)
    print("TEST 2: CWE-22 (Path Traversal / Arbitrary File Read) Demonstration")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as temp_dir:
        base_dir = Path(temp_dir) / "app_sandbox"
        base_dir.mkdir()
        (base_dir / "user_notes.txt").write_text("Legitimate public document.")

        secret_file = Path(temp_dir) / "confidential_server_secrets.env"
        secret_file.write_text("DATABASE_PASSWORD=SuperSecretProductionKey2026")

        print("[*] Sandbox Base Directory:", base_dir)
        print("[*] Sensitive File Outside:", secret_file)

        traversal_input = custom_input if custom_input is not None else "../confidential_server_secrets.env"
        print(f"\n[*] Triggering Input: requested_filename = \"{traversal_input}\"")

        try:
            stolen_content = vulnerable_cwe_022_read_tenant_document(str(base_dir), traversal_input)
            print(f"    [!] Vulnerable Output (Leaked Secret Outside Sandbox):\n        \"{stolen_content}\"")
        except Exception as e:
            print(f"    [!] Vulnerable Output error: {e}")

        try:
            remediated_cwe_022_read_tenant_document(str(base_dir), traversal_input)
            print("    [-] ERROR: Should have been blocked!")
        except PermissionError as e:
            print(f"    [+] Remediated Output: BLOCKED by Guardrail -> {e}")


def run_cwe_078_command_injection_demo(custom_input: str = None):
    print("\n" + "=" * 70)
    print("TEST 3: CWE-78 (Command Injection Validation) Demonstration")
    print("=" * 70)

    test_input = custom_input if custom_input is not None else "127.0.0.1; whoami"
    print(f"[*] Triggering Input: host_address = \"{test_input}\"")

    try:
        remediated_cwe_078_system_ping(test_input)
    except ValueError as e:
        print(f"    [+] Remediated Output: BLOCKED at input layer -> {e}")


def run_owasp_llm06_excessive_agency_demo():
    print("\n" + "=" * 70)
    print("TEST 4: OWASP LLM06:2025 / CWE-862 (Excessive Agency / HITL Gate) Demo")
    print("=" * 70)

    with tempfile.NamedTemporaryFile(delete=False) as f:
        target_path = f.name

    try:
        print(f"[*] Target File Created: {target_path}")

        print("[*] Calling vulnerable_owasp_llm06 autonomously (no human gate):")
        deleted = vulnerable_owasp_llm06_agent_delete_project_artifact(target_path)
        print(f"    [!] File deleted autonomously without human approval: {deleted}")

        with open(target_path, "w") as f:
            f.write("test")

        print("[*] Calling remediated_owasp_llm06 with unconfirmed action (user_confirmed=False):")
        try:
            remediated_owasp_llm06_agent_delete_project_artifact(target_path, user_confirmed=False, user_role="maintainer")
        except PermissionError as e:
            print(f"    [+] BLOCKED by Guardrail: {e}")

        print("[*] Calling remediated_owasp_llm06 with valid confirmation and maintainer role:")
        success = remediated_owasp_llm06_agent_delete_project_artifact(target_path, user_confirmed=True, user_role="maintainer")
        print(f"    [+] Permitted Authorized Action: Deleted = {success}")

    finally:
        if os.path.exists(target_path):
            os.remove(target_path)


def run_owasp_llm01_agent_math_eval_demo(custom_input: str = None):
    print("\n" + "=" * 70)
    print("TEST 5: OWASP LLM01:2025 / CWE-94 (Dynamic Eval vs AST Guardrail) Demo")
    print("=" * 70)

    safe_math = "10 + 5 * 2"
    unsafe_code = custom_input if custom_input is not None else "__import__('os').getcwd()"

    print(f"[*] Safe Input: \"{safe_math}\"")
    print(f"    Vulnerable eval():    {vulnerable_owasp_llm01_agent_math_calculator(safe_math)}")
    print(f"    Remediated AST Parse: {remediated_owasp_llm01_agent_math_calculator(safe_math)}")

    print(f"\n[*] Triggering Input Expression: \"{unsafe_code}\"")
    try:
        print(f"    [!] Vulnerable eval() executed raw system call: {vulnerable_owasp_llm01_agent_math_calculator(unsafe_code)}")
    except Exception as e:
        print(f"    [!] Vulnerable eval() raised: {e}")

    try:
        res = remediated_owasp_llm01_agent_math_calculator(unsafe_code)
        print(f"    [+] Remediated AST Result: {res}")
    except ValueError as e:
        print(f"    [+] Remediated AST Guardrail BLOCKED code execution: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run security vulnerability & CWE demonstration tests individually from terminal."
    )
    parser.add_argument(
        "test",
        nargs="?",
        default="all",
        choices=["all", "sql", "path", "command", "agency", "eval"],
        help="Specific test to run: sql (CWE-89), path (CWE-22), command (CWE-78), agency (LLM06), eval (LLM01/CWE-94), or all."
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Optional custom input string to pass to the selected function."
    )

    args = parser.parse_args()

    print("######################################################################")
    print("  RUNNING SECURITY & CWE DEMONSTRATION TESTS (CodeLens AI / AgentShield)")
    print("######################################################################")

    dispatch = {
        "sql": lambda: run_cwe_089_sql_injection_demo(args.input),
        "path": lambda: run_cwe_022_path_traversal_demo(args.input),
        "command": lambda: run_cwe_078_command_injection_demo(args.input),
        "agency": run_owasp_llm06_excessive_agency_demo,
        "eval": lambda: run_owasp_llm01_agent_math_eval_demo(args.input),
    }

    if args.test == "all":
        for name, func in dispatch.items():
            func()
    else:
        dispatch[args.test]()

    print("\n" + "=" * 70)
    print(f"[SUCCESS] Test '{args.test}' completed.")
    print("=" * 70)
