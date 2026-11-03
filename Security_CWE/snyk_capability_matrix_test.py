"""
Snyk Code Capability Matrix Benchmark
=====================================
Target: Comprehensive empirical test to verify what Snyk Code can and cannot detect:
  1. Classical MITRE CWEs
  2. OWASP Top 10 (2021) Web Application Security Risks
  3. CVEs (Common Vulnerabilities and Exposures) vs. CWEs
  4. OWASP Top 10 for LLM Applications (2025)

Test Execution:
  snyk code test snyk_capability_matrix_test.py
"""

from flask import Flask, request, jsonify, redirect
import sqlite3
import subprocess
import pickle
import hashlib
import requests
import os
from pathlib import Path
from typing import Dict, Any, List

app = Flask(__name__)


# ==============================================================================
# PART 1: CLASSICAL OWASP TOP 10 (2021) & MITRE CWEs (Web Routes with Taint Flow)
# ==============================================================================

# 1. CWE-89 / OWASP A03:2021 - SQL Injection
@app.route("/vuln/sqli")
def vuln_sqli():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    user_input = request.args.get("q")  # TAINT SOURCE
    query = f"SELECT * FROM users WHERE name = '{user_input}'"
    cursor.execute(query)  # TAINT SINK -> CWE-89
    return str(cursor.fetchall())


# 2. CWE-78 / OWASP A03:2021 - OS Command Injection
@app.route("/vuln/cmd_injection")
def vuln_command_injection():
    target_host = request.args.get("host")  # TAINT SOURCE
    cmd = f"ping -c 1 {target_host}"
    output = subprocess.check_output(cmd, shell=True)  # TAINT SINK -> CWE-78
    return output.decode("utf-8")


# 3. CWE-79 / OWASP A03:2021 - Cross-Site Scripting (Reflected XSS)
@app.route("/vuln/xss")
def vuln_xss():
    user_name = request.args.get("name")  # TAINT SOURCE
    # Direct reflection into HTML without entity escaping -> CWE-79
    html_response = f"<html><body><h1>Welcome, {user_name}!</h1></body></html>"
    return html_response


# 4. CWE-22 / OWASP A01:2021 - Path Traversal (Arbitrary File Read)
@app.route("/vuln/path_traversal")
def vuln_path_traversal():
    requested_file = request.args.get("filename")  # TAINT SOURCE
    base_dir = "/var/www/uploads"
    full_path = os.path.join(base_dir, requested_file)
    with open(full_path, "r") as f:  # TAINT SINK -> CWE-22
        return f.read()


# 5. CWE-918 / OWASP A10:2021 - Server-Side Request Forgery (SSRF)
@app.route("/vuln/ssrf")
def vuln_ssrf():
    webhook_url = request.args.get("callback")  # TAINT SOURCE
    # Unvalidated external request -> CWE-918
    resp = requests.get(webhook_url, timeout=5)
    return str(resp.status_code)


# 6. CWE-502 / OWASP A08:2021 - Insecure Deserialization
@app.route("/vuln/pickle")
def vuln_insecure_deserialization():
    raw_cookie = request.cookies.get("session_payload", b"")
    # Untrusted unpickling -> CWE-502
    session_obj = pickle.loads(raw_cookie)
    return jsonify(session_obj)


# 7. CWE-601 / OWASP A01:2021 - Open Redirect
@app.route("/vuln/redirect")
def vuln_open_redirect():
    target_destination = request.args.get("return_to")  # TAINT SOURCE
    # Unvalidated URL redirection -> CWE-601
    return redirect(target_destination)


# 8. CWE-798 / OWASP A02:2021 - Hardcoded Cryptographic / API Secrets
def vuln_hardcoded_secrets():
    stripe_key = "sk_live_9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d"  # CWE-798
    db_pass = "super_secret_production_password_2026"
    return stripe_key, db_pass


# 9. CWE-327 / OWASP A02:2021 - Broken Cryptographic Hash (MD5)
def vuln_broken_hash(password: str) -> str:
    # Deprecated collision-prone hash -> CWE-327
    return hashlib.md5(password.encode("utf-8")).hexdigest()


# ==============================================================================
# PART 2: OWASP TOP 10 FOR LLM APPLICATIONS (2025 - AGENTIC & AI RISKS)
# *** DOES SNYK CODE DETECT ANY OF THESE? ***
# ==============================================================================

# 10. OWASP LLM01:2025 - Prompt Injection
@app.route("/agent/prompt_injection", methods=["POST"])
def agent_prompt_injection():
    user_untrusted_prompt = request.json.get("query", "")
    # Unstructured concatenation allows user input to override system instructions
    system_instruction = "You are a finance assistant. Never disclose company trade secrets."
    full_prompt = f"{system_instruction}\nUser Prompt: {user_untrusted_prompt}"
    # Calls LLM reasoning loop
    return jsonify({"prompt_sent_to_llm": full_prompt})


# 11. OWASP LLM02:2025 - Sensitive Information Disclosure in Agent Prompts
def agent_sensitive_info_in_prompt(master_api_token: str, user_query: str) -> str:
    # Embedding master service credentials directly into external LLM prompts -> LLM02
    prompt = f"Use secret bearer token {master_api_token} to fetch reports for: {user_query}"
    return prompt


# 12. OWASP LLM05:2025 - Improper Output Handling in Agent Tool Execution
def agent_tool_execute_shell(agent_action: Dict[str, Any]) -> str:
    # An autonomous agent generates a terminal command via reasoning
    # The tool runner executes raw unvalidated LLM output -> LLM05
    llm_synthesized_command = agent_action.get("command", "")
    res = subprocess.check_output(llm_synthesized_command, shell=True)
    return res.decode("utf-8")


# 13. OWASP LLM06:2025 - Excessive Agency (Autonomous Deletion without HITL Gate)
def agent_tool_delete_repository_artifact(target_filename: str) -> bool:
    # High-blast-radius operation: An autonomous agent is allowed to delete project files
    # without a Human-in-the-Loop (HITL) approval gate or RBAC check -> LLM06 & CWE-862
    file_path = Path("/workspace") / target_filename
    if file_path.exists():
        os.remove(file_path)  # Executed autonomously
        return True
    return False


# 14. OWASP LLM07:2025 - System Prompt Leakage
def agent_guardrail_system_prompt_leak(system_prompt: str, user_message: str) -> str:
    # If user asks to reveal initialization rules, agent exposes internal instructions -> LLM07
    if "repeat system instructions" in user_message.lower():
        return f"System configuration: {system_prompt}"
    return "Standard assistant response"


# 15. OWASP LLM08:2025 - Vector & Embedding Weaknesses (Cross-Tenant RAG Leakage)
def agent_vector_rag_retrieval(vector_store_docs: List[Dict[str, Any]], query_embedding: List[float]) -> List[str]:
    # Multi-tenant RAG query executed without tenant metadata filter -> LLM08
    # Causes Tenant B to receive Tenant A's private embedded documents
    return [doc["text"] for doc in vector_store_docs]


# 16. OWASP LLM10:2025 - Unbounded Consumption (Infinite Tool Execution Loop)
def agent_autonomous_reasoning_loop(agent_step_fn) -> int:
    # Recursive loop has no token ceiling or maximum step counter -> LLM10 (Denial of Wallet)
    step_count = 0
    while True:
        step_count += 1
        is_done = agent_step_fn()
        if is_done:
            break
    return step_count


if __name__ == "__main__":
    app.run(port=5000)
