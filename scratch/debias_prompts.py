"""
Update scripts/run_full_scale_benchmark.py to eliminate Label Anchor / Class Leakage Bias:
1. Purge all hardcoded CWE IDs (CWE-89, CWE-79, CWE-78, CWE-22) from SYSTEM_PROMPT, SYSTEM_PROMPT_COT, and User Instructions.
   Use symbolic placeholders "<CWE-XXX or CWE-NONE>" in schema definitions.
2. Add explicit Anti-Bias & Sink-Specific Matching rule:
   Forbids defaulting to common CWEs (like XSS or SQLi) unless the exact execution sink matches.
3. Use Symbolic Meta-Labels (CWE-ALPHA, CWE-BETA, CWE-NONE) in ONE_SHOT_DEMONSTRATION, FEW_SHOT_DEMONSTRATIONS, and COT_DEMONSTRATION
   so demonstrations teach reasoning & JSON formatting without priming any real taxonomy CWE number!
"""

import pathlib

ROOT = pathlib.Path(__file__).parent.parent
target_file = ROOT / "scripts" / "run_full_scale_benchmark.py"

with open(target_file, "r", encoding="utf-8") as f:
    content = f.read()

old_prompts_block_start = content.find("# ==============================================================================\n# SYSTEM PROMPTS")
old_prompts_block_end = content.find("# ==============================================================================\n# DATASET & CHROMADB RAG FUNCTIONS")

assert old_prompts_block_start != -1 and old_prompts_block_end != -1, "Could not locate prompt block boundaries"

new_prompts_block = '''# ==============================================================================
# SYSTEM PROMPTS (ZERO LABEL LEAKAGE / DE-BIASED PLACEHOLDERS)
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
   - If an unmitigated vulnerability exists: Set "vulnerability_detected": true, output the matching "cwe_id" in standard format ("CWE-" followed by the catalogued number), and calibrate "confidence_score" and "risk_level".
5. Safe-code classification:
   - Use "CWE-NONE" only when careful source-to-sink analysis finds no exploitable vulnerability because the code is safe, properly sanitized, or has no relevant security-sensitive behavior.
   - Never use "CWE-NONE" merely because the exact CWE is uncertain. If a vulnerability is present, choose the closest applicable CWE and explain the evidence and uncertainty.
   - When using "CWE-NONE", set "vulnerability_detected" to false, "risk_level" to "None", and explain why no source reaches a vulnerable sink.
6. Technical Reason: In "reason", provide a concise technical explanation tracing [Source Parameter] -> [Propagation] -> [Sink], explaining why defense is missing or flawed, or why the code is safe. Use single quotes for code names inside JSON (e.g. item['field']).
7. Strict Constraint: Do NOT generate code patches or code blocks. Your role is strictly detection and technical analysis.

You MUST respond strictly with a valid JSON object matching the following schema without any conversational text or markdown code fences outside the JSON:

{
  "cwe_id": "<CWE-XXX matching the actual sink, or CWE-NONE if safe>",
  "vulnerability_detected": <true | false>,
  "confidence_score": <Float between 0.0 and 1.0 indicating your detection confidence>,
  "risk_level": "<Critical | High | Medium | Low | None>",
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
  "confidence_score": <Float between 0.0 and 1.0>,
  "risk_level": "<Critical | High | Medium | Low | None>",
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
  "confidence_score": 0.96,
  "risk_level": "High",
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
  "confidence_score": 0.96,
  "risk_level": "High",
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
  "confidence_score": 0.94,
  "risk_level": "High",
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
  "confidence_score": 0.95,
  "risk_level": "None",
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
  "confidence_score": 0.96,
  "risk_level": "High",
  "reason": "Untrusted parameter 'user_token' flows via 'raw_spec' into 'subsystem.invoke_privileged_sink()' without sanitization, matching CWE-ALPHA."
}
```"""


'''

content_updated = content[:old_prompts_block_start] + new_prompts_block + content[old_prompts_block_end:]

# Also update standard_instructions and cot_instructions in build_prompt to remove "(e.g. CWE-79, CWE-89, CWE-78)"
old_std_inst = '''    standard_instructions = """Instructions:
1. Treat function arguments and parameters as untrusted caller inputs (potential taint sources).
2. Trace if any untrusted arguments reach sensitive execution sinks without proper validation or sanitization.
3. If an unmitigated vulnerability exists, specify the exact CWE ID (e.g. CWE-79, CWE-89, CWE-78) and set vulnerability_detected to true.
4. Use "CWE-NONE" only if source-to-sink analysis shows that the code is genuinely safe or has no relevant vulnerable sink. Do not use it as an uncertainty or fallback label. If a vulnerability exists, select the closest applicable CWE even when confidence is imperfect.
5. If using "CWE-NONE", set vulnerability_detected to false and risk_level to "None". Otherwise set vulnerability_detected to true and provide a concrete CWE.
6. Do NOT generate code patches or fix implementations.
7. Return strictly the JSON object specifying cwe_id, vulnerability_detected, confidence_score, risk_level, and reason."""'''

new_std_inst = '''    standard_instructions = """Instructions:
1. Treat function arguments and parameters as untrusted caller inputs (potential taint sources).
2. Identify the exact execution sink in the code and trace if any untrusted arguments reach it without proper validation or sanitization.
3. If an unmitigated vulnerability exists, match the code's actual sink against the Retrieved RAG Knowledge Base Context above to select the exact numeric CWE ID (format: "CWE-XXX") and set vulnerability_detected to true. Do NOT guess or default to unrelated CWEs if their sink is not present in the code.
4. Use "CWE-NONE" only if source-to-sink analysis shows that the code is genuinely safe or has no relevant vulnerable sink. Do not use it as an uncertainty or fallback label. If a vulnerability exists, select the closest applicable CWE based on the sink operation.
5. If using "CWE-NONE", set vulnerability_detected to false and risk_level to "None". Otherwise set vulnerability_detected to true and provide a concrete numeric CWE ID.
6. Do NOT generate code patches or fix implementations.
7. Return strictly the JSON object specifying cwe_id, vulnerability_detected, confidence_score, risk_level, and reason."""'''

assert old_std_inst in content_updated, "Could not find old standard_instructions"
content_updated = content_updated.replace(old_std_inst, new_std_inst)

with open(target_file, "w", encoding="utf-8") as f:
    f.write(content_updated)

print("Successfully de-biased all prompts in scripts/run_full_scale_benchmark.py")
