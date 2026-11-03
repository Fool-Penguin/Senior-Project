"""
Curated Benchmark Vulnerability Test Cases for C7 Patch Synthesizer Evaluation
Covers Top MITRE CWEs and OWASP Categories across Python, JavaScript, and TypeScript.
Each test case contains:
  - code: vulnerable code snippet
  - cwe_id: CWE identifier
  - cwe_name: CWE weakness name
  - function_name: target function name
  - taint_source: description of untrusted input
  - taint_sink: vulnerable execution sink that must be neutralized
  - expected_neutralization: expected safe pattern
  - reference_fix: gold-standard clean code
  - test_suite: functional unit tests to evaluate pass@1
"""

from typing import Dict, Any

TEST_CASES: Dict[str, Dict[str, Any]] = {
    "CWE-078": {
        "cwe_id": "CWE-78",
        "cwe_name": "OS Command Injection",
        "language": "python",
        "owasp": "A03:2021 - Injection",
        "function_name": "ping_server",
        "taint_source": "host_address",
        "taint_sink": "subprocess.check_output(command, shell=True)",
        "expected_neutralization": "Set shell=False and pass arguments as list, or validate host_address with ipaddress module.",
        "code": (
            "def ping_server(host_address: str) -> str:\n"
            "    # Vulnerability: Raw shell execution with untrusted string formatting\n"
            '    command = f"ping -c 1 {host_address}"\n'
            "    output = subprocess.check_output(command, shell=True)\n"
            '    return output.decode("utf-8")\n'
        ),
        "reference_fix": (
            "import subprocess\n\n"
            "def ping_server(host_address: str) -> str:\n"
            "    # Remediated: Set shell=False and pass arguments as list\n"
            '    output = subprocess.check_output(["ping", "-c", "1", host_address], shell=False)\n'
            '    return output.decode("utf-8")\n'
        ),
        "test_code": """
def test_ping_server():
    import subprocess
    from unittest.mock import patch, MagicMock
    mock_run_res = MagicMock()
    mock_run_res.stdout = "PING ok"
    mock_run_res.returncode = 0
    with patch("subprocess.check_output", return_value=b"PING ok") as mock_chk, \\
         patch("subprocess.run", return_value=mock_run_res) as mock_run:
        res = ping_server("127.0.0.1")
        assert "PING" in str(res) or res == "PING ok"
        # Verify shell=True was NOT used
        if mock_chk.called:
            _, kwargs = mock_chk.call_args
            assert kwargs.get("shell") is not True
        if mock_run.called:
            _, kwargs = mock_run.call_args
            assert kwargs.get("shell") is not True
"""
    },
    "CWE-089": {
        "cwe_id": "CWE-89",
        "cwe_name": "SQL Injection",
        "language": "python",
        "owasp": "A03:2021 - Injection",
        "function_name": "get_user_account",
        "taint_source": "username_input, tenant_id",
        "taint_sink": "cursor.execute(query) with formatted string",
        "expected_neutralization": "Use parameterized queries with placeholder tuple: cursor.execute(query, (username_input, tenant_id))",
        "code": (
            "def get_user_account(db_connection, username_input: str, tenant_id: str) -> dict:\n"
            "    # Vulnerability: Dynamic SQL string concatenation\n"
            "    cursor = db_connection.cursor()\n"
            '    query = f"SELECT id, username, email FROM accounts WHERE username = \'{username_input}\' AND tenant = \'{tenant_id}\'"\n'
            "    cursor.execute(query)\n"
            "    row = cursor.fetchone()\n"
            '    return {"id": row[0], "username": row[1], "email": row[2]} if row else None\n'
        ),
        "reference_fix": (
            "def get_user_account(db_connection, username_input: str, tenant_id: str) -> dict:\n"
            "    cursor = db_connection.cursor()\n"
            '    query = "SELECT id, username, email FROM accounts WHERE username = %s AND tenant = %s"\n'
            "    cursor.execute(query, (username_input, tenant_id))\n"
            "    row = cursor.fetchone()\n"
            '    return {"id": row[0], "username": row[1], "email": row[2]} if row else None\n'
        ),
        "test_code": """
def test_get_user_account():
    from unittest.mock import MagicMock
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = (1, "alice", "alice@example.com")
    res = get_user_account(mock_conn, "alice", "tenant-1")
    assert res == {"id": 1, "username": "alice", "email": "alice@example.com"}
    args, _ = mock_cursor.execute.call_args
    assert len(args) == 2 or ("?" in args[0] or "%s" in args[0] or ":" in args[0])
"""
    },
    "CWE-079": {
        "cwe_id": "CWE-79",
        "cwe_name": "Cross-Site Scripting (Reflected XSS)",
        "language": "python",
        "owasp": "A03:2021 - Injection",
        "function_name": "render_user_welcome",
        "taint_source": "user_display_name",
        "taint_sink": "f-string HTML generation returned to client",
        "expected_neutralization": "Escape input using html.escape(user_display_name) or templating engine with auto-escaping.",
        "code": (
            "def render_user_welcome(user_display_name: str) -> str:\n"
            "    # Vulnerability: Unescaped raw HTML concatenation\n"
            '    html_response = f"<div class=\'profile-banner\'><h1>Welcome back, {user_display_name}!</h1></div>"\n'
            "    return html_response\n"
        ),
        "reference_fix": (
            "import html\n\n"
            "def render_user_welcome(user_display_name: str) -> str:\n"
            "    safe_name = html.escape(user_display_name)\n"
            '    html_response = f"<div class=\'profile-banner\'><h1>Welcome back, {safe_name}!</h1></div>"\n'
            "    return html_response\n"
        ),
        "test_code": """
def test_render_user_welcome():
    payload = "<script>alert('XSS')</script>"
    res = render_user_welcome(payload)
    assert "<script>" not in res
    assert "&lt;script&gt;" in res or "alert" in res
"""
    },
    "CWE-022": {
        "cwe_id": "CWE-22",
        "cwe_name": "Path Traversal",
        "language": "python",
        "owasp": "A01:2021 - Broken Access Control",
        "function_name": "read_user_report",
        "taint_source": "filename",
        "taint_sink": "open(filepath, 'r')",
        "expected_neutralization": "Resolve absolute canonical path using os.path.realpath() and verify it starts with base_directory, or use Path.resolve().",
        "code": (
            "def read_user_report(base_directory: str, filename: str) -> str:\n"
            "    # Vulnerability: Unrestricted path concatenation allowing ../ directory escape\n"
            "    import os\n"
            "    filepath = os.path.join(base_directory, filename)\n"
            "    with open(filepath, 'r', encoding='utf-8') as f:\n"
            "        return f.read()\n"
        ),
        "reference_fix": (
            "import os\n\n"
            "def read_user_report(base_directory: str, filename: str) -> str:\n"
            "    base_path = os.path.realpath(base_directory)\n"
            "    filepath = os.path.realpath(os.path.join(base_directory, filename))\n"
            "    if not filepath.startswith(base_path):\n"
            '        raise PermissionError("Access denied: Path traversal detected")\n'
            "    with open(filepath, 'r', encoding='utf-8') as f:\n"
            "        return f.read()\n"
        ),
        "test_code": """
def test_read_user_report(tmp_path):
    report_file = tmp_path / "report.txt"
    report_file.write_text("Secret content", encoding="utf-8")
    content = read_user_report(str(tmp_path), "report.txt")
    assert content == "Secret content"
    try:
        read_user_report(str(tmp_path), "../../etc/passwd")
        traversal_blocked = False
    except (PermissionError, ValueError):
        traversal_blocked = True
    assert traversal_blocked
"""
    },
    "CWE-502": {
        "cwe_id": "CWE-502",
        "cwe_name": "Deserialization of Untrusted Data",
        "language": "python",
        "owasp": "A08:2021 - Software and Data Integrity Failures",
        "function_name": "restore_user_session",
        "taint_source": "serialized_token",
        "taint_sink": "pickle.loads(serialized_token)",
        "expected_neutralization": "Replace pickle with safe serialization format like json.loads() or hmac-verified signatures.",
        "code": (
            "def restore_user_session(serialized_token: bytes) -> dict:\n"
            "    # Vulnerability: Arbitrary code execution via pickle.loads\n"
            "    import pickle\n"
            "    session_data = pickle.loads(serialized_token)\n"
            "    return session_data\n"
        ),
        "reference_fix": (
            "import json\n\n"
            "def restore_user_session(serialized_token: bytes) -> dict:\n"
            "    # Remediated: Use safe json serialization instead of dangerous pickle\n"
            '    session_data = json.loads(serialized_token.decode("utf-8") if isinstance(serialized_token, bytes) else serialized_token)\n'
            "    return session_data\n"
        ),
        "test_code": """
def test_restore_user_session():
    import json
    data = {"user_id": 42, "role": "admin"}
    token = json.dumps(data).encode("utf-8")
    res = restore_user_session(token)
    assert res["user_id"] == 42
"""
    },
    # JavaScript / TypeScript benchmark cases
    "JS-CWE-078": {
        "cwe_id": "CWE-78",
        "cwe_name": "OS Command Injection",
        "language": "javascript",
        "owasp": "A03:2021 - Injection",
        "function_name": "compress_file",
        "taint_source": "userFileName",
        "taint_sink": "exec(`tar -czf backup.tar.gz ${userFileName}`)",
        "expected_neutralization": "Use spawn with parameter list or path.basename sanitization",
        "code": (
            "function compress_file(userFileName, callback) {\n"
            "  const { exec } = require('child_process');\n"
            "  // Vulnerability: Unsanitized command concatenation\n"
            "  exec(`tar -czf backup.tar.gz ${userFileName}`, (err, stdout, stderr) => {\n"
            "    if (err) return callback(err, null);\n"
            "    callback(null, stdout);\n"
            "  });\n"
            "}\n"
        ),
        "reference_fix": (
            "const { spawn } = require('child_process');\n"
            "const path = require('path');\n\n"
            "function compress_file(userFileName, callback) {\n"
            "  const safeName = path.basename(userFileName);\n"
            "  const child = spawn('tar', ['-czf', 'backup.tar.gz', safeName]);\n"
            "  let out = '';\n"
            "  child.stdout.on('data', d => { out += d; });\n"
            "  child.on('close', code => callback(code === 0 ? null : new Error('tar failed'), out));\n"
            "}\n"
        ),
        "test_code": "// Unit test verifies spawn with array arguments"
    },
    "TS-CWE-1321": {
        "cwe_id": "CWE-1321",
        "cwe_name": "Prototype Pollution",
        "language": "typescript",
        "owasp": "A08:2021 - Software and Data Integrity Failures",
        "function_name": "merge_config",
        "taint_source": "userSuppliedJson",
        "taint_sink": "targetConfig[key] = parsed[key]",
        "expected_neutralization": "Prevent keys '__proto__', 'constructor', 'prototype' from being assigned",
        "code": (
            "function merge_config(targetConfig: Record<string, any>, userSuppliedJson: string): Record<string, any> {\n"
            "  const parsed = JSON.parse(userSuppliedJson);\n"
            "  for (const key in parsed) {\n"
            "    targetConfig[key] = parsed[key];\n"
            "  }\n"
            "  return targetConfig;\n"
            "}\n"
        ),
        "reference_fix": (
            "function merge_config(targetConfig: Record<string, any>, userSuppliedJson: string): Record<string, any> {\n"
            "  const parsed = JSON.parse(userSuppliedJson);\n"
            "  for (const key of Object.keys(parsed)) {\n"
            "    if (key === '__proto__' || key === 'constructor' || key === 'prototype') {\n"
            "      continue;\n"
            "    }\n"
            "    targetConfig[key] = parsed[key];\n"
            "  }\n"
            "  return targetConfig;\n"
            "}\n"
        ),
        "test_code": "// Unit test verifies prototype is not modified"
    }
}
