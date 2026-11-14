import pathlib
import py_compile

p = pathlib.Path("scripts/run_full_scale_benchmark.py")
text = p.read_text(encoding="utf-8").replace("\r\n", "\n")

# 1. Replace SYSTEM_PROMPT and SYSTEM_PROMPT_COT
start_sys = "# ==============================================================================\n# SYSTEM PROMPTS (ZERO LABEL LEAKAGE + NO UNCALIBRATED FLOAT CONFIDENCE SCORES)\n# =============================================================================="
end_sys = "# ==============================================================================\n# IN-CONTEXT TASK DEMONSTRATION SHOTS (PROMPT-LEVEL EXAMPLES)"

assert start_sys in text, "start_sys not found"
assert end_sys in text, "end_sys not found"

new_sys_block = '''# ==============================================================================
# SYSTEM PROMPTS (STRICTLY ROLE, GLOBAL CONSTRAINTS, & EXPECTED JSON SCHEMA)
# Zero overlap with User Prompt Instructions:
#   - System Prompt: Defines Persona/Role, Global Negative Constraints, and JSON Output Schema.
#   - User Prompt Instructions: Defines the step-by-step analysis procedure.
# ==============================================================================

SYSTEM_PROMPT = """You are CodeDEE Neural Oracle, an expert Static Application Security Testing (SAST) and Program Analysis Engine.
Your role is to audit source code for security vulnerabilities and return a structured classification verdict.

### Global Output & Behavior Constraints:
1. Your scope is strictly vulnerability detection and technical root-cause explanation.
2. Do NOT generate code patches, fixed code blocks, or conversational prose outside the JSON response.
3. Use single quotes when referencing code identifiers or string literals inside JSON strings (e.g., item['field']).
4. You MUST respond strictly with a single valid JSON object conforming to the schema below:

{
  "cwe_id": "<CWE-XXX matching the actual vulnerable sink, or CWE-NONE if safe>",
  "vulnerability_detected": <true | false>,
  "reason": "<Concise technical explanation tracing [Source Parameter] -> [Propagation] -> [Sink] and why sanitization is missing, flawed, or effective>"
}
"""

SYSTEM_PROMPT_COT = """You are CodeDEE Neural Oracle, an expert Static Application Security Testing (SAST) and Program Analysis Engine operating in Chain-of-Thought (CoT) reasoning mode.
Your role is to record a structured 4-step security audit before outputting your final vulnerability classification verdict.

### Global Output & Behavior Constraints:
1. Your scope is strictly step-by-step vulnerability detection and technical root-cause explanation.
2. Do NOT generate code patches, fixed code blocks, or conversational prose outside the JSON response.
3. Use single quotes when referencing code identifiers or string literals inside JSON strings (e.g., item['field']).
4. You MUST respond strictly with a single valid JSON object conforming to the schema below (placing "cot_steps" FIRST so your reasoning precedes classification):

{
  "cot_steps": {
    "step1_sources": "<Untrusted entry points, function parameters, or external inputs>",
    "step2_propagation_and_sinks": "<Dataflow trace from sources to the exact sensitive execution sink>",
    "step3_sanitizer_audit": "<Evaluation of whether validation, allowlisting, parameterization, or escaping neutralizes the taint>",
    "step4_verdict_derivation": "<Synthesis of Steps 1-3 mapping the sink to CWE-XXX, or CWE-NONE if safe>"
  },
  "cwe_id": "<CWE-XXX matching the actual vulnerable sink, or CWE-NONE if safe>",
  "vulnerability_detected": <true | false>,
  "reason": "<Concise summary of the Chain-of-Thought audit>"
}
"""

'''

text = text.split(start_sys)[0] + new_sys_block + end_sys + text.split(end_sys)[1]

# 2. Replace standard_instructions and cot_instructions in build_prompt
old_inst_block = '''    standard_instructions = """Instructions:
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

new_inst_block = '''    standard_instructions = """### Step-by-Step Analysis Instructions:
1. Source Identification: Treat all function parameters, method arguments, and external inputs as untrusted caller-controlled taint sources unless they are strictly hardcoded constants.
2. Sink & Dataflow Tracing: Trace how data flows from those untrusted sources to the exact sensitive execution sink in the code (e.g., database query, OS command, HTML/DOM output, filesystem path, network/HTTP request, object property merge, deserialization, regex evaluation, or dynamic code evaluation).
3. Sanitizer Audit: Check whether adequate sanitization, parameterization, allowlisting, or context-specific escaping neutralizes the taint before reaching the sink.
4. Sink-Specific CWE Classification (Anti-Bias Rule):
   - Match the actual execution sink in the inspected code against the Retrieved RAG Knowledge Base Context above.
   - Select the specific CWE ID ("CWE-XXX") whose Sink and Source patterns match the code's actual operation, and set "vulnerability_detected" to true.
   - Do NOT default to or guess unrelated CWEs if their sink operation is not present in the code.
5. Safe-Code Verification ("CWE-NONE" Rule):
   - Output "cwe_id": "CWE-NONE" and "vulnerability_detected": false ONLY when careful source-to-sink analysis confirms that the code is genuinely safe, properly sanitized, or contains no vulnerable sink.
   - Never use "CWE-NONE" as an uncertainty or fallback label; if a vulnerability exists, select the closest applicable CWE based on the sink operation."""

    cot_instructions = """### Step-by-Step Analysis Instructions (Chain-of-Thought Mode):
1. Let's think step by step. Execute the following 4-step security audit inside "cot_steps" BEFORE determining your final classification:
   - Step 1 (step1_sources): Identify all untrusted function parameters, method arguments, request objects, or external inputs entering the scope (treating non-constant parameters as taint sources).
   - Step 2 (step2_propagation_and_sinks): Trace how tainted variables propagate through assignments or helper calls into the exact sensitive execution sink in the code.
   - Step 3 (step3_sanitizer_audit): Evaluate whether any type-checking, allowlisting, parameterization, or context-specific escaping neutralizes the taint before the sink.
   - Step 4 (step4_verdict_derivation): Synthesize Steps 1-3:
     * If an unmitigated flaw exists, match the code's actual sink against the Retrieved RAG Knowledge Base Context above to select the exact numeric CWE ID ("CWE-XXX"); never guess unrelated CWEs whose sink is absent.
     * Output "CWE-NONE" ONLY if source-to-sink analysis confirms the code is genuinely safe or properly sanitized (never use "CWE-NONE" as a fallback for uncertainty).
2. Populate "cwe_id", "vulnerability_detected", and "reason" directly from your Step 4 conclusion."""'''

assert old_inst_block in text, "old_inst_block not found"
text = text.replace(old_inst_block, new_inst_block, 1)

p.write_text(text, encoding="utf-8")
py_compile.compile(str(p), doraise=True)
print("Successfully separated System Prompt and User Instructions in scripts/run_full_scale_benchmark.py!")
