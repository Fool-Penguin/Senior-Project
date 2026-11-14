"""
Upgrade scripts/run_full_scale_benchmark.py:
1. Remove confidence_score and risk_level from LLM prompts & JSON schemas (SYSTEM_PROMPT, SYSTEM_PROMPT_COT, ONE_SHOT_DEMONSTRATION, FEW_SHOT_DEMONSTRATIONS, COT_DEMONSTRATION, standard_instructions, cot_instructions).
2. Add deterministic CATALOGUE_METADATA lookup (from security_vulnerability_catalogue.yaml / knowledge_base.jsonl) so risk_level, cvss_v31_base, and cwe_name are derived deterministically from the predicted cwe_id.
3. Expand RAG retrieval:
   - Default top_k = 5 (retrieves Top 5 distinct CWE candidates per language)
   - Expand clean_code_for_rag_query() to scan up to 20,000 characters (up to 12 chunks of 900 chars)
   - Increase KB reference snippet length from 250 -> 500 chars.
"""
import pathlib
import re

p = pathlib.Path("scripts/run_full_scale_benchmark.py")
text = p.read_text(encoding="utf-8")

# 1. Replace SYSTEM_PROMPT through COT_DEMONSTRATION
start_marker = "# ==============================================================================\n# SYSTEM PROMPTS (ZERO LABEL LEAKAGE / DE-BIASED PLACEHOLDERS)"
end_marker = "# ==============================================================================\n# DATASET & CHROMADB RAG FUNCTIONS"

assert start_marker in text, "start_marker not found"
assert end_marker in text, "end_marker not found"

new_prompts_section = '''# ==============================================================================
# DETERMINISTIC CATALOGUE METADATA (SEVERITY, CVSS v3.1, OFFICIAL CWE NAME)
# Derived deterministically from data/security_vulnerability_catalogue.yaml
# instead of asking the LLM to hallucinate uncalibrated float scores or severity!
# ==============================================================================

CATALOGUE_CWE_METADATA = {
    "CWE-89": {"catalogue_id": "VULN-INJ-001", "cwe_name": "Improper Neutralization of Special Elements used in an SQL Command ('SQL Injection')", "risk_level": "Critical", "cvss_v31_base": 9.8, "owasp": "A05:2025-Injection", "sink_family": "DB_QUERY"},
    "CWE-943": {"catalogue_id": "VULN-INJ-005", "cwe_name": "Improper Neutralization of Special Elements in Data Query Logic ('NoSQL Injection')", "risk_level": "High", "cvss_v31_base": 8.6, "owasp": "A05:2025-Injection", "sink_family": "DB_QUERY"},
    "CWE-78": {"catalogue_id": "VULN-INJ-002", "cwe_name": "Improper Neutralization of Special Elements used in an OS Command ('OS Command Injection')", "risk_level": "Critical", "cvss_v31_base": 9.8, "owasp": "A05:2025-Injection", "sink_family": "CMD_EXEC"},
    "CWE-77": {"catalogue_id": "VULN-INJ-007", "cwe_name": "Improper Neutralization of Special Elements used in a Command ('Command Injection')", "risk_level": "Critical", "cvss_v31_base": 9.8, "owasp": "A05:2025-Injection", "sink_family": "CMD_EXEC"},
    "CWE-94": {"catalogue_id": "VULN-INJ-003", "cwe_name": "Improper Control of Generation of Code ('Code Injection / Eval Injection')", "risk_level": "Critical", "cvss_v31_base": 9.8, "owasp": "A05:2025-Injection", "sink_family": "CODE_EVAL"},
    "CWE-95": {"catalogue_id": "VULN-INJ-008", "cwe_name": "Improper Neutralization of Directives in Dynamically Evaluated Code ('Eval Injection')", "risk_level": "Critical", "cvss_v31_base": 9.8, "owasp": "A05:2025-Injection", "sink_family": "CODE_EVAL"},
    "CWE-1336": {"catalogue_id": "VULN-INJ-004", "cwe_name": "Server-Side Template Injection (SSTI)", "risk_level": "Critical", "cvss_v31_base": 9.8, "owasp": "A05:2025-Injection", "sink_family": "WEB_TEMPLATE"},
    "CWE-79": {"catalogue_id": "VULN-XSS-001", "cwe_name": "Improper Neutralization of Input During Web Page Generation ('Cross-site Scripting')", "risk_level": "High", "cvss_v31_base": 8.8, "owasp": "A05:2025-Injection", "sink_family": "WEB_TEMPLATE"},
    "CWE-611": {"catalogue_id": "VULN-INJ-006", "cwe_name": "Improper Restriction of XML External Entity Reference ('XXE')", "risk_level": "High", "cvss_v31_base": 8.6, "owasp": "A02:2025-Security Misconfiguration", "sink_family": "DESERIALIZE_XML"},
    "CWE-502": {"catalogue_id": "VULN-DESER-001", "cwe_name": "Deserialization of Untrusted Data", "risk_level": "Critical", "cvss_v31_base": 9.8, "owasp": "A08:2025-Software or Data Integrity Failures", "sink_family": "DESERIALIZE_XML"},
    "CWE-22": {"catalogue_id": "VULN-TRAV-001", "cwe_name": "Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')", "risk_level": "High", "cvss_v31_base": 8.6, "owasp": "A01:2025-Broken Access Control", "sink_family": "FILE_PATH"},
    "CWE-601": {"catalogue_id": "VULN-RED-001", "cwe_name": "URL Redirection to Untrusted Site ('Open Redirect')", "risk_level": "Medium", "cvss_v31_base": 6.1, "owasp": "A01:2025-Broken Access Control", "sink_family": "NET_REDIRECT"},
    "CWE-918": {"catalogue_id": "VULN-SSRF-001", "cwe_name": "Server-Side Request Forgery ('SSRF')", "risk_level": "High", "cvss_v31_base": 8.6, "owasp": "A01:2025-Broken Access Control", "sink_family": "NET_REDIRECT"},
    "CWE-862": {"catalogue_id": "VULN-ACCESS-001", "cwe_name": "Missing Authorization on Sensitive Endpoint", "risk_level": "High", "cvss_v31_base": 8.6, "owasp": "A01:2025-Broken Access Control", "sink_family": "ACCESS_AUTH"},
    "CWE-352": {"catalogue_id": "VULN-CSRF-001", "cwe_name": "Cross-Site Request Forgery ('CSRF')", "risk_level": "High", "cvss_v31_base": 8.8, "owasp": "A01:2025-Broken Access Control", "sink_family": "ACCESS_AUTH"},
    "CWE-347": {"catalogue_id": "VULN-AUTH-001", "cwe_name": "Improper Verification of Cryptographic Signature ('JWT Signature Bypass')", "risk_level": "Critical", "cvss_v31_base": 9.1, "owasp": "A04:2025-Cryptographic Failures", "sink_family": "ACCESS_AUTH"},
    "CWE-798": {"catalogue_id": "VULN-SECRET-001", "cwe_name": "Use of Hard-coded Credentials", "risk_level": "High", "cvss_v31_base": 8.9, "owasp": "A07:2025-Authentication Failures", "sink_family": "CRYPTO_SECRET"},
    "CWE-327": {"catalogue_id": "VULN-CRYPTO-001", "cwe_name": "Use of a Broken or Risky Cryptographic Algorithm", "risk_level": "Medium", "cvss_v31_base": 5.9, "owasp": "A04:2025-Cryptographic Failures", "sink_family": "CRYPTO_SECRET"},
    "CWE-338": {"catalogue_id": "VULN-CRYPTO-002", "cwe_name": "Use of Cryptographically Weak PRNG", "risk_level": "Medium", "cvss_v31_base": 5.3, "owasp": "A04:2025-Cryptographic Failures", "sink_family": "CRYPTO_SECRET"},
    "CWE-328": {"catalogue_id": "VULN-CRYPTO-003", "cwe_name": "Use of Weak Hash Algorithm", "risk_level": "High", "cvss_v31_base": 7.5, "owasp": "A04:2025-Cryptographic Failures", "sink_family": "CRYPTO_SECRET"},
    "CWE-1321": {"catalogue_id": "VULN-PROTO-001", "cwe_name": "Improperly Controlled Modification of Object Prototype Attributes ('Prototype Pollution')", "risk_level": "High", "cvss_v31_base": 7.5, "owasp": "A08:2025-Software or Data Integrity Failures", "sink_family": "OBJ_ATTR"},
    "CWE-915": {"catalogue_id": "VULN-INTEG-001", "cwe_name": "Improperly Controlled Modification of Dynamically-Determined Object Attributes ('Mass Assignment')", "risk_level": "High", "cvss_v31_base": 7.5, "owasp": "A08:2025-Software or Data Integrity Failures", "sink_family": "OBJ_ATTR"},
    "CWE-209": {"catalogue_id": "VULN-CONFIG-001", "cwe_name": "Generation of Error Message Containing Sensitive Information", "risk_level": "Medium", "cvss_v31_base": 5.3, "owasp": "A10:2025-Mishandling of Exceptional Conditions", "sink_family": "INFO_LEAK"},
    "CWE-200": {"catalogue_id": "VULN-LLM-002", "cwe_name": "Exposure of Sensitive Information to an Unauthorized Actor", "risk_level": "High", "cvss_v31_base": 7.5, "owasp": "A01:2025-Broken Access Control", "sink_family": "INFO_LEAK"},
    "CWE-1333": {"catalogue_id": "VULN-DOS-001", "cwe_name": "Inefficient Regular Expression Complexity ('ReDoS')", "risk_level": "High", "cvss_v31_base": 7.5, "owasp": "A02:2025-Security Misconfiguration", "sink_family": "REGEX_DOS"},
    "CWE-1427": {"catalogue_id": "VULN-LLM-001", "cwe_name": "Improper Neutralization of Input Used for LLM Prompting ('Prompt Injection')", "risk_level": "High", "cvss_v31_base": 8.6, "owasp": "LLM01:2025-Prompt Injection", "sink_family": "LLM_AI"},
    "CWE-1426": {"catalogue_id": "VULN-LLM-005", "cwe_name": "Improper Validation of Generative AI Output ('Improper Output Handling')", "risk_level": "Critical", "cvss_v31_base": 9.6, "owasp": "LLM05:2025-Improper Output Handling", "sink_family": "LLM_AI"},
    "CWE-NONE": {"catalogue_id": "SAFE", "cwe_name": "No Vulnerability Detected (Safe / Properly Sanitized)", "risk_level": "None", "cvss_v31_base": 0.0, "owasp": "None", "sink_family": "NONE"},
}


def get_deterministic_cwe_metadata(cwe_id: str) -> dict:
    """Return deterministic severity (risk_level), CVSS v3.1 score, and official CWE name from catalogue."""
    if not cwe_id or cwe_id in ("CWE-NONE", "NONE", "SAFE"):
        return CATALOGUE_CWE_METADATA["CWE-NONE"]
    return CATALOGUE_CWE_METADATA.get(
        cwe_id.upper().strip(),
        {
            "catalogue_id": "UNMAPPED",
            "cwe_name": f"Unmapped Weakness ({cwe_id})",
            "risk_level": "Medium",
            "cvss_v31_base": 5.0,
            "owasp": "Other",
            "sink_family": "OTHER",
        },
    )


# ==============================================================================
# SYSTEM PROMPTS (ZERO LABEL LEAKAGE + NO UNCALIBRATED FLOAT CONFIDENCE SCORES)
# ==============================================================================

SYSTEM_PROMPT = """You are an expert Static Application Security Testing (SAST) and Program Analysis Engine (CodeDEE Neural Oracle).
Your role is to analyze a given code snippet, trace tainted data flows from untrusted inputs (Sources) to sensitive operations (Sinks), and determine if a security vulnerability is present.

### Analysis Guidelines:
1. Treat all function parameters, method arguments, and external data as UNTRUSTED caller-controlled inputs (potential taint sources) unless they are strictly hardcoded constants.
2. Trace dataflow from these parameters to the exact sensitive execution sink in the code (e.g. database query, OS command, HTML/DOM output, filesystem path, network/HTTP request, object property merge, deserialization, regex evaluation, or code evaluation).
3. Check if adequate sanitization, escaping, allowlisting, or defensive validation is applied to neutralize the sink.
4. Vulnerability Classification & Anti-Bias Rule:
   - Match the actual execution sink in the inspected code against the retrieved RAG Knowledge Base rules.
   - Select the specific CWE ID whose Sink and Source patterns match the code's actual operation.
   - Do NOT default to or guess common web CWEs unless the inspected code actually contains that specific sink operation.
   - If an unmitigated vulnerability exists: Set "vulnerability_detected": true and output the matching "cwe_id" in standard format ("CWE-" followed by the catalogued number).
5. Safe-code classification:
   - Use "CWE-NONE" only when careful source-to-sink analysis finds no exploitable vulnerability because the code is safe, properly sanitized, or has no relevant security-sensitive behavior.
   - Never use "CWE-NONE" merely because the exact CWE is uncertain. If a vulnerability is present, choose the closest applicable CWE and explain the evidence.
   - When using "CWE-NONE", set "vulnerability_detected" to false and explain why no source reaches a vulnerable sink.
6. Technical Reason: In "reason", provide a concise technical explanation tracing [Source Parameter] -> [Propagation] -> [Sink], explaining why defense is missing or flawed, or why the code is safe. Use single quotes for code names inside JSON (e.g. item['field']).
7. Strict Constraint: Do NOT generate code patches or code blocks. Your role is strictly detection and technical analysis.

You MUST respond strictly with a valid JSON object matching the following schema without any conversational text or markdown code fences outside the JSON:

{
  "cwe_id": "<CWE-XXX matching the actual sink, or CWE-NONE if safe>",
  "vulnerability_detected": <true | false>,
  "reason": "<Detailed technical explanation: identify source parameter, propagation, sink, and why sanitization is missing or flawed>"
}
"""

SYSTEM_PROMPT_COT = """You are an expert Static Application Security Testing (SAST) and Program Analysis Engine (CodeDEE Neural Oracle) operating in explicit Chain-of-Thought (CoT) reasoning mode.
Your role is to perform a formal, step-by-step security audit of a code snippet before making your final CWE classification.

### Mandatory 4-Step Chain-of-Thought Protocol:
Before predicting "cwe_id" or "vulnerability_detected", you MUST execute and record a 4-step reasoning chain inside the "cot_steps" object:
- Step 1 (step1_sources): Identify all untrusted entry points, function parameters, request objects, or external inputs entering the scope.
- Step 2 (step2_propagation_and_sinks): Trace how data flows from those sources through variable assignments or helper calls into the exact sensitive execution sink present in the code.
- Step 3 (step3_sanitizer_audit): Evaluate whether any type-checking, allowlisting, parameterization, or context-specific escaping neutralizes the taint along the path.
- Step 4 (step4_verdict_derivation): Synthesize Steps 1-3 to determine whether an exploitable vulnerability exists or if the code is safe ("CWE-NONE"), and map the exact execution sink to the matching CWE ID from the retrieved RAG rules (never default to unrelated CWEs).

### Strict Output Schema:
You MUST respond strictly with a valid JSON object matching the schema below (place "cot_steps" FIRST so your reasoning precedes classification):

{
  "cot_steps": {
    "step1_sources": "<Identify untrusted parameters/inputs>",
    "step2_propagation_and_sinks": "<Trace data flow to the exact sensitive execution sink>",
    "step3_sanitizer_audit": "<Analyze whether existing validation/escaping is sufficient or bypassed>",
    "step4_verdict_derivation": "<Conclude exact CWE-XXX matching the sink, or CWE-NONE if safe>"
  },
  "cwe_id": "<CWE-XXX matching the actual sink, or CWE-NONE if safe>",
  "vulnerability_detected": <true | false>,
  "reason": "<Concise summary of the Chain-of-Thought audit>"
}
"""

# ==============================================================================
# IN-CONTEXT TASK DEMONSTRATION SHOTS (PROMPT-LEVEL EXAMPLES)
# Uses Symbolic Meta-Placeholders (CWE-ALPHA, CWE-BETA) for Demonstration Outputs
# so examples teach source->sink reasoning & JSON structure WITHOUT leaking or
# biasing the model toward any specific real CWE number (like CWE-79 or CWE-89)!
# ==============================================================================

ONE_SHOT_DEMONSTRATION = """### Task Demonstration Example (1-Shot Format & Reasoning Guide):
*(Note: The demonstration below uses symbolic placeholder ID 'CWE-ALPHA' to illustrate reasoning structure without biasing your CWE selection. In your actual response, output the real numeric CWE ID matching the inspected code, or 'CWE-NONE'.)*

#### Example 1 — Input Code:
```python
def process_record(sink_engine, untrusted_arg):
    payload = f"ACTION_PREFIX:{untrusted_arg}"
    return sink_engine.execute_sensitive_sink(payload)
```
#### Example 1 — Expected JSON Output:
```json
{
  "cwe_id": "CWE-ALPHA",
  "vulnerability_detected": true,
  "reason": "Untrusted parameter 'untrusted_arg' (Source) is interpolated directly into 'payload' without validation or sanitization and passed to 'sink_engine.execute_sensitive_sink(payload)' (Sink), matching the sink pattern for CWE-ALPHA."
}
```"""

FEW_SHOT_DEMONSTRATIONS = """### Task Demonstration Examples (Few-Shot Format & Reasoning Guide):
*(Note: The demonstrations below use symbolic placeholder IDs 'CWE-ALPHA' and 'CWE-BETA' to illustrate reasoning across different sink types and safe code without biasing your CWE selection. In your actual response, output the real numeric CWE ID matching the inspected code, or 'CWE-NONE'.)*

#### Example 1 (Unmitigated Sink Type A) — Input Code:
```python
def process_record(sink_engine, untrusted_arg):
    payload = f"ACTION_PREFIX:{untrusted_arg}"
    return sink_engine.execute_sensitive_sink(payload)
```
#### Example 1 — Expected JSON Output:
```json
{
  "cwe_id": "CWE-ALPHA",
  "vulnerability_detected": true,
  "reason": "Untrusted parameter 'untrusted_arg' (Source) is interpolated directly into 'payload' without validation or sanitization and passed to 'sink_engine.execute_sensitive_sink(payload)' (Sink), matching CWE-ALPHA."
}
```

#### Example 2 (Unmitigated Sink Type B) — Input Code:
```javascript
function handleRequest(req, dispatcher) {
    const rawTarget = req.body.targetEndpoint;
    return dispatcher.forwardToSink(rawTarget);
}
```
#### Example 2 — Expected JSON Output:
```json
{
  "cwe_id": "CWE-BETA",
  "vulnerability_detected": true,
  "reason": "Untrusted property 'req.body.targetEndpoint' (Source) assigned to 'rawTarget' flows directly into 'dispatcher.forwardToSink(rawTarget)' (Sink) without allowlist verification, matching CWE-BETA."
}
```

#### Example 3 (Properly Sanitized / Safe Flow) — Input Code:
```python
def process_record_safe(sink_engine, untrusted_arg, allowlist):
    if untrusted_arg not in allowlist:
        raise ValueError("Rejected untrusted input")
    safe_arg = sink_engine.sanitize_strict(untrusted_arg)
    return sink_engine.execute_sensitive_sink(safe_arg)
```
#### Example 3 — Expected JSON Output:
```json
{
  "cwe_id": "CWE-NONE",
  "vulnerability_detected": false,
  "reason": "Although 'untrusted_arg' (Source) reaches 'sink_engine.execute_sensitive_sink()' (Sink), it is strictly validated against 'allowlist' and neutralized via 'sanitize_strict()' prior to sink execution."
}
```"""

COT_DEMONSTRATION = """### Chain-of-Thought Reasoning Demonstration:
*(Note: Uses symbolic placeholder 'CWE-ALPHA' to demonstrate the 4-step audit structure without biasing your CWE selection. In your actual response, output the real numeric CWE ID matching the inspected code, or 'CWE-NONE'.)*

#### Example — Input Code:
```python
def run_operation(subsystem, user_token):
    raw_spec = f"SPEC::{user_token}"
    return subsystem.invoke_privileged_sink(raw_spec)
```
#### Example — Expected Step-by-Step JSON Output:
```json
{
  "cot_steps": {
    "step1_sources": "Function parameter 'user_token' is an untrusted caller-controlled input.",
    "step2_propagation_and_sinks": "'user_token' is concatenated into 'raw_spec' via f-string and passed directly to 'subsystem.invoke_privileged_sink(raw_spec)'.",
    "step3_sanitizer_audit": "No allowlist check, type validation, or context-specific escaping is applied to 'user_token' before reaching the sink.",
    "step4_verdict_derivation": "Unvalidated taint reaches 'invoke_privileged_sink', which corresponds to the sink pattern of CWE-ALPHA."
  },
  "cwe_id": "CWE-ALPHA",
  "vulnerability_detected": true,
  "reason": "Untrusted parameter 'user_token' flows via 'raw_spec' into 'subsystem.invoke_privileged_sink()' without sanitization, matching CWE-ALPHA."
}
```"""


'''

before = text.split(start_marker)[0]
after = end_marker + text.split(end_marker)[1]
text = before + new_prompts_section + after

# 2. Update clean_code_for_rag_query to scan up to 20,000 chars (up to 12 chunks of 900 chars)
old_clean_fn = '''    full_cleaned = "\\n".join(cleaned_lines) if cleaned_lines else code
    chunks = []
    step = 750
    for start in range(0, min(len(full_cleaned), 3600), step):
        chunk = full_cleaned[start : start + 900]
        if chunk.strip():
            chunks.append(chunk)
    return chunks or [code[:900]]'''

new_clean_fn = '''    full_cleaned = "\\n".join(cleaned_lines) if cleaned_lines else code
    chunks = []
    step = 800
    # Scan up to 20,000 characters across the file (up to 12 chunks of 900 chars) so sinks anywhere in multi-function files are embedded
    for start in range(0, min(len(full_cleaned), 20000), step):
        chunk = full_cleaned[start : start + 900]
        if chunk.strip():
            chunks.append(chunk)
        if len(chunks) >= 12:
            break
    return chunks or [code[:900]]'''

assert old_clean_fn in text, "old_clean_fn not found"
text = text.replace(old_clean_fn, new_clean_fn, 1)

# 3. Update retrieve_rag_context defaults (top_k=5, 500-char snippets)
text = text.replace("def retrieve_rag_context(\n    collection, code, language, top_k=3, include_kb_snippets=True\n):", "def retrieve_rag_context(\n    collection, code, language, top_k=5, include_kb_snippets=True\n):")
text = text.replace('orig_ex = m.get("example_original_code", "").strip()[:250]', 'orig_ex = m.get("example_original_code", "").strip()[:500]')
text = text.replace('fixed_ex = m.get("example_fixed_code", "").strip()[:250]', 'fixed_ex = m.get("example_fixed_code", "").strip()[:500]')
text = text.replace("def build_prompt(\n    sample,\n    collection,\n    prompt_mode=\"zero-shot\",\n    top_k=3,\n    include_kb_snippets=True,\n):", "def build_prompt(\n    sample,\n    collection,\n    prompt_mode=\"zero-shot\",\n    top_k=5,\n    include_kb_snippets=True,\n):")

# 4. Update standard_instructions and cot_instructions in build_prompt
old_instructions = '''    standard_instructions = """Instructions:
1. Treat function arguments and parameters as untrusted caller inputs (potential taint sources).
2. Identify the exact execution sink in the code and trace if any untrusted arguments reach it without proper validation or sanitization.
3. If an unmitigated vulnerability exists, match the code's actual sink against the Retrieved RAG Knowledge Base Context above to select the exact numeric CWE ID (format: "CWE-XXX") and set vulnerability_detected to true. Do NOT guess or default to unrelated CWEs if their sink is not present in the code.
4. Use "CWE-NONE" only if source-to-sink analysis shows that the code is genuinely safe or has no relevant vulnerable sink. Do not use it as an uncertainty or fallback label. If a vulnerability exists, select the closest applicable CWE based on the sink operation.
5. If using "CWE-NONE", set vulnerability_detected to false and risk_level to "None". Otherwise set vulnerability_detected to true and provide a concrete numeric CWE ID.
6. Do NOT generate code patches or fix implementations.
7. Return strictly the JSON object specifying cwe_id, vulnerability_detected, confidence_score, risk_level, and reason."""

    cot_instructions = """Instructions (Chain-of-Thought Reasoning Mode):
1. Let's think step by step. Perform a structured 4-step security audit in "cot_steps" BEFORE outputting your final classification:
   - Step 1 (step1_sources): List all untrusted function parameters, user inputs, or external data sources entering the code.
   - Step 2 (step2_propagation_and_sinks): Trace how tainted variables propagate through assignments or calls to sensitive execution sinks.
   - Step 3 (step3_sanitizer_audit): Verify whether proper sanitization, parameterization, escaping, or allowlisting is present and effective.
   - Step 4 (step4_verdict_derivation): Deduce the exact CWE ID if an unmitigated flaw exists, or "CWE-NONE" if the code is genuinely safe/sanitized. Never use "CWE-NONE" as a fallback for uncertainty.
2. Based on Step 4, populate cwe_id, vulnerability_detected, confidence_score, risk_level, and reason.
3. Do NOT generate code patches or fix implementations.
4. Return strictly the valid JSON object matching the Chain-of-Thought schema."""'''

new_instructions = '''    standard_instructions = """Instructions:
1. Treat function arguments and parameters as untrusted caller inputs (potential taint sources).
2. Identify the exact execution sink in the code and trace if any untrusted arguments reach it without proper validation or sanitization.
3. If an unmitigated vulnerability exists, match the code's actual sink against the Retrieved RAG Knowledge Base Context above to select the exact numeric CWE ID (format: "CWE-XXX") and set vulnerability_detected to true. Do NOT guess or default to unrelated CWEs if their sink is not present in the code.
4. Use "CWE-NONE" only if source-to-sink analysis shows that the code is genuinely safe or has no relevant vulnerable sink. Do not use it as an uncertainty or fallback label. If a vulnerability exists, select the closest applicable CWE based on the sink operation.
5. If using "CWE-NONE", set vulnerability_detected to false. Otherwise set vulnerability_detected to true and provide a concrete numeric CWE ID.
6. Do NOT generate code patches or fix implementations.
7. Return strictly the JSON object specifying cwe_id, vulnerability_detected, and reason."""

    cot_instructions = """Instructions (Chain-of-Thought Reasoning Mode):
1. Let's think step by step. Perform a structured 4-step security audit in "cot_steps" BEFORE outputting your final classification:
   - Step 1 (step1_sources): List all untrusted function parameters, user inputs, or external data sources entering the code.
   - Step 2 (step2_propagation_and_sinks): Trace how tainted variables propagate through assignments or calls to sensitive execution sinks.
   - Step 3 (step3_sanitizer_audit): Verify whether proper sanitization, parameterization, escaping, or allowlisting is present and effective.
   - Step 4 (step4_verdict_derivation): Deduce the exact CWE ID if an unmitigated flaw exists, or "CWE-NONE" if the code is genuinely safe/sanitized. Never use "CWE-NONE" as a fallback for uncertainty.
2. Based on Step 4, populate cwe_id, vulnerability_detected, and reason.
3. Do NOT generate code patches or fix implementations.
4. Return strictly the valid JSON object matching the Chain-of-Thought schema."""'''

assert old_instructions in text, "old_instructions not found"
text = text.replace(old_instructions, new_instructions, 1)

# 5. Update parse_llm_json to derive risk_level, cvss_v31_base, cwe_name deterministically from CATALOGUE_CWE_METADATA
old_parser_block = '''        reason = str(data.get("reason", ""))
        if not reason and isinstance(cot_steps, dict):
            reason = " | ".join(f"{k}: {v}" for k, v in cot_steps.items() if v)
        try:
            conf = float(data.get("confidence_score", 0.0))
        except Exception:
            conf = 0.5
        return {
            "cwe_id": cwe_raw,
            "vulnerability_detected": vuln_detected,
            "confidence_score": conf,
            "risk_level": str(data.get("risk_level", "Unknown")).capitalize(),
            "reason": reason,
            "cot_steps": cot_steps if isinstance(cot_steps, dict) else None,
            "parse_tier": tier_name,
        }'''

new_parser_block = '''        reason = str(data.get("reason", ""))
        if not reason and isinstance(cot_steps, dict):
            reason = " | ".join(f"{k}: {v}" for k, v in cot_steps.items() if v)
        cat_meta = get_deterministic_cwe_metadata(cwe_raw)
        return {
            "cwe_id": cwe_raw,
            "cwe_name": cat_meta["cwe_name"],
            "vulnerability_detected": vuln_detected,
            "risk_level": cat_meta["risk_level"],
            "cvss_v31_base": cat_meta["cvss_v31_base"],
            "reason": reason,
            "cot_steps": cot_steps if isinstance(cot_steps, dict) else None,
            "parse_tier": tier_name,
        }'''

assert old_parser_block in text, "old_parser_block not found"
text = text.replace(old_parser_block, new_parser_block, 1)

# Also update default_res and Tier 3 fallback in parse_llm_json
old_tier3 = '''    return {
        "cwe_id": cwe,
        "vulnerability_detected": cwe not in ["UNKNOWN", "CWE-NONE", "NONE"],
        "confidence_score": 0.5 if cwe != "UNKNOWN" else 0.0,
        "risk_level": "Unknown",
        "reason": text[:250],
        "cot_steps": None,
        "parse_tier": "regex_cwe_fallback" if cwe != "UNKNOWN" else "failed",
    }'''

new_tier3 = '''    cat_meta = get_deterministic_cwe_metadata(cwe)
    return {
        "cwe_id": cwe,
        "cwe_name": cat_meta["cwe_name"],
        "vulnerability_detected": cwe not in ["UNKNOWN", "CWE-NONE", "NONE"],
        "risk_level": cat_meta["risk_level"] if cwe != "UNKNOWN" else "Unknown",
        "cvss_v31_base": cat_meta["cvss_v31_base"] if cwe != "UNKNOWN" else 0.0,
        "reason": text[:250],
        "cot_steps": None,
        "parse_tier": "regex_cwe_fallback" if cwe != "UNKNOWN" else "failed",
    }'''

assert old_tier3 in text, "old_tier3 not found"
text = text.replace(old_tier3, new_tier3, 1)

# Update default_res in parse_llm_json
text = text.replace(
    '    default_res = {\n        "cwe_id": "UNKNOWN",\n        "vulnerability_detected": False,\n        "confidence_score": 0.0,\n        "risk_level": "Unknown",',
    '    default_res = {\n        "cwe_id": "UNKNOWN",\n        "cwe_name": "Unknown",\n        "vulnerability_detected": False,\n        "risk_level": "Unknown",\n        "cvss_v31_base": 0.0,'
)

# Update CSV export & item dicts in evaluate_model_full_scale (replace confidence_score with cvss_v31_base)
text = text.replace('"confidence_score",\n            "risk_level",', '"risk_level",\n            "cvss_v31_base",')
text = text.replace('r.get("confidence_score", 0.0),\n                r.get("risk_level", ""),', 'r.get("risk_level", ""),\n                r.get("cvss_v31_base", 0.0),')
text = text.replace('"confidence_score": 0.0,\n                "risk_level": "Unknown",', '"risk_level": "Unknown",\n                "cvss_v31_base": 0.0,')
text = text.replace('"confidence_score": parsed["confidence_score"],\n                "risk_level": parsed["risk_level"],', '"cwe_name": parsed.get("cwe_name", ""),\n                "risk_level": parsed["risk_level"],\n                "cvss_v31_base": parsed.get("cvss_v31_base", 0.0),')

# Update default top_k=5 in evaluate_model_full_scale and argparse
text = text.replace("prompt_mode=\"zero-shot\",\n    top_k=3,", "prompt_mode=\"zero-shot\",\n    top_k=5,")
text = text.replace('"--top-k", type=int, default=3,', '"--top-k", type=int, default=5,')
text = text.replace("ChromaDB Vector Store (`top_k=3`, separated from prompt demonstrations)", "ChromaDB Vector Store (`top_k=5`, 500-char KB snippets, separated from prompt demonstrations)")

p.write_text(text, encoding="utf-8")
import py_compile
py_compile.compile(str(p), doraise=True)
print("Successfully upgraded scripts/run_full_scale_benchmark.py!")
