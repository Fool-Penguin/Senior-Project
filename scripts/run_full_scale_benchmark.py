"""
CodeDEE - Full-Scale Master Evaluation Benchmark Runner
Separates RAG Retrieval from Prompting Strategy:
  - RAG Block: Retrieved identically across all modes from ChromaDB (Top-K rules with Sources, Sinks, Sanitizers, and Reference Snippets).
  - Prompting Mode (--prompt-mode): Controls the Prompt Template & In-Context Task Demonstrations (Input Code -> Expected JSON Output):
      1. zero-shot : 0 task demonstrations in the prompt (Direct instructions + JSON schema).
      2. one-shot  : 1 complete Input Code -> Expected JSON Output demonstration in the prompt.
      3. few-shot  : 3 complete Input Code -> Expected JSON Output demonstrations in the prompt (covering Vulnerable SQLi, Vulnerable XSS, and Safe/Sanitized CWE-NONE).
      4. cot       : Chain-of-Thought Prompting (Mandatory 4-Step Audit reasoning + CoT Input -> Step-by-Step JSON Output demonstration).
      *  all       : Runs all 4 prompting modes sequentially per model (Model-First Loop).

========================================================================================
HOW TO RUN THE SCRIPT (CLI USAGE EXAMPLES):
========================================================================================

1. Run ALL 4 prompt modes across ALL 13 models (Model-First Loop):
   python scripts/run_full_scale_benchmark.py --prompt-mode all --dataset v4 --checkpoint-tag master_v4_ablation

2. Run ALL 4 prompt modes on specific models:
   python scripts/run_full_scale_benchmark.py --prompt-mode all --models qwen2.5-coder:7b llama3.1:8b --dataset v4

3. Run a single prompt mode:
   python scripts/run_full_scale_benchmark.py --prompt-mode zero-shot --dataset v3
   python scripts/run_full_scale_benchmark.py --prompt-mode one-shot --dataset v3
   python scripts/run_full_scale_benchmark.py --prompt-mode few-shot --dataset v3
   python scripts/run_full_scale_benchmark.py --prompt-mode cot --dataset v3
========================================================================================
"""

import argparse
import csv
import json
import math
import os
import pathlib
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict

import chromadb
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).parent.parent
COMBINED_DIR = ROOT / "datasets" / "combined"
DATASET_PATH = COMBINED_DIR / "dataset.jsonl"

DATASET_VERSIONS = {
    "v1": COMBINED_DIR / "dataset_v1_raw_unfiltered_1208.jsonl",
    "v2": COMBINED_DIR / "dataset_v2_filtered_30to4000_vuln_only_928.jsonl",
    "v3": COMBINED_DIR / "dataset_v3_multifunc_30to20000_vuln_only_967.jsonl",
    "v4": COMBINED_DIR / "dataset_v4_multifunc_with_safe_patches_1911.jsonl",
    "cyberseceval": COMBINED_DIR / "dataset_cyberseceval_external_507.jsonl",
}

CORE_PROMPT_MODES = [
    "zero-shot",
    "one-shot",
    "few-shot",
    "cot",
]

VALID_PROMPT_ARG_CHOICES = CORE_PROMPT_MODES + ["all"]

PROMPT_MODE_LABELS = {
    "zero-shot": "Zero-Shot Prompting (0 Task Demos + RAG)",
    "one-shot": "One-Shot Prompting (1 Task Demo + RAG)",
    "few-shot": "Few-Shot Prompting (3 Task Demos + RAG)",
    "cot": "Chain-of-Thought Prompting (4-Step Audit + RAG)",
}

CHROMA_DIR = ROOT / "data" / "chromadb_kb"
BENCHMARK_FULL_DIR = ROOT / "benchmarks_full_scale"
BENCHMARK_FULL_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR = BENCHMARK_FULL_DIR / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)

ALL_MODELS = [
    "IHA089/drana-infinity-3b:3b",
    "qwen2.5-coder:7b",
    "moayadterro/vulntune-qwen2.5-coder-7b:latest",
    "IHA089/drana-infinity-7b:7b",
    "moayadterro/vulntune-deepseek-coder-6.7b:latest",
    "llama3.1:8b",
    "Foundation-Sec-8B-Instruct:latest",
    "Foundation-Sec-8B-Reasoning:latest",
    "deepseek-r1:8b",
    "qwen2.5-coder:14b",
    "deepseek-r1:14b",
    "qwen2.5-coder:32b",
    "deepseek-r1:32b",
]

# ==============================================================================
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


# ==============================================================================
# DATASET & CHROMADB RAG FUNCTIONS (RAG IS PULLED SEPARATELY AND IDENTICALLY)
# ==============================================================================

def resolve_dataset_path(dataset_arg=None):
    """Resolve dataset version key (v1, v2, v3, v4, cyberseceval) or custom path."""
    if not dataset_arg:
        return DATASET_VERSIONS["v3"]
    key = str(dataset_arg).strip().lower()
    if key in DATASET_VERSIONS:
        return DATASET_VERSIONS[key]
    custom_path = pathlib.Path(dataset_arg)
    if not custom_path.is_absolute():
        custom_path = ROOT / custom_path
    return custom_path


def load_dataset(dataset_arg=None):
    """Load evaluation samples from the specified dataset version or path."""
    target_path = resolve_dataset_path(dataset_arg)
    if not target_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {target_path}")
    samples = []
    with open(target_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    return samples, target_path


def get_chroma_collection():
    """Connect to ChromaDB vector store."""
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    embedding_fn = ONNXMiniLM_L6_V2()
    return client.get_collection(
        name="codedee_knowledge_base", embedding_function=embedding_fn
    )


# Map of CWE -> characteristic sink / API signatures in code (Python, JS, TS)
# Used by Hybrid ChromaDB RAG retrieval to combine dense vector similarity with lexical sink matching
CWE_SINK_SIGNATURES = {
    "CWE-89": [r"\.execute\s*\(", r"\.query\s*\(", r"SELECT\s+.+FROM", r"INSERT\s+INTO", r"UPDATE\s+.+SET", r"DELETE\s+FROM", r"raw_sql", r"sequelize\.query", r"cursor\.execute"],
    "CWE-78": [r"subprocess\.", r"shell\s*=\s*True", r"child_process", r"execSync\s*\(", r"spawn\s*\(", r"os\.system\s*\(", r"os\.popen\s*\(", r'exec\s*\(\s*[`\'"]'],
    "CWE-77": [r"os\.system\s*\(", r"os\.popen\s*\(", r"subprocess\.Popen", r"child_process\.exec", r"execSync"],
    "CWE-79": [r"innerHTML", r"outerHTML", r"document\.write", r"dangerouslySetInnerHTML", r"render_template_string", r"Markup\s*\(", r"res\.send\s*\(", r"res\.write\s*\(", r"<script", r"<img", r"data:text/html"],
    "CWE-94": [r"\beval\s*\(", r"\bexec\s*\(", r"new\s+Function\s*\(", r"compile\s*\(", r"vm\.runIn"],
    "CWE-95": [r"\beval\s*\(", r"new\s+Function\s*\("],
    "CWE-1336": [r"jinja2\.Template", r"render_template_string", r"ejs\.render", r"nunjucks\.renderString", r"handlebars\.compile", r"pug\.render"],
    "CWE-943": [r"\.find\s*\(\s*\{", r"\.findOne\s*\(\s*\{", r"\$where", r"\$gt", r"\$ne", r"mongodb", r"mongoose"],
    "CWE-611": [r"ElementTree\.fromstring", r"lxml\.etree", r"parseXml", r"DOMParser", r"xml2js", r"resolve_entities", r"noent\s*:\s*true"],
    "CWE-22": [r"\bopen\s*\(", r"send_file\s*\(", r"send_from_directory", r"fs\.readFile", r"fs\.readFileSync", r"fs\.createReadStream", r"path\.join", r"os\.path\.join", r"shutil\.copy", r"Path\s*\("],
    "CWE-601": [r"\bredirect\s*\(", r"res\.redirect", r"window\.location", r"location\.href", r"HttpResponseRedirect"],
    "CWE-862": [r"has_permission", r"is_admin", r"check_auth", r"authorize", r"permission", r"@login_required", r"req\.user", r"current_user", r"role"],
    "CWE-352": [r"csrf", r"CSRFProtect", r"SameSite", r"csurf", r"@csrf_exempt"],
    "CWE-502": [r"pickle\.loads", r"_pickle\.loads", r"yaml\.load\s*\(", r"yaml\.unsafe_load", r"unserialize\s*\(", r"jsonpickle", r"marshal\.loads"],
    "CWE-915": [r"setattr\s*\(", r"Object\.assign\s*\(", r"\*\*request\.json", r"\*\*req\.body", r"update_attributes"],
    "CWE-1321": [r"__proto__", r"constructor\.prototype", r"Object\.assign", r"merge\s*\(", r"deepMerge", r"setattr\s*\(", r"__dict__"],
    "CWE-918": [r"requests\.get\s*\(", r"requests\.post\s*\(", r"requests\.request\s*\(", r"urllib\.request\.urlopen", r"httpx\.", r"aiohttp\.", r"fetch\s*\(", r"axios\."],
    "CWE-798": [r"API_KEY\s*=", r"SECRET_KEY\s*=", r"PASSWORD\s*=", r'password\s*=\s*[\'"]', r'jwt\.sign\s*\([^,]+,\s*[\'"]', r"aws_secret_access_key"],
    "CWE-327": [r"DES\b", r"ARC4", r"Blowfish", r"MODE_ECB", r'createCipheriv\s*\(\s*[\'"]des', r"rc4", r"aes-\d+-ecb"],
    "CWE-338": [r"random\.random\s*\(", r"random\.randint\s*\(", r"random\.choice\s*\(", r"Math\.random\s*\("],
    "CWE-328": [r"hashlib\.md5", r"hashlib\.sha1", r'createHash\s*\(\s*[\'"]md5', r'createHash\s*\(\s*[\'"]sha1', r"MD5\.new", r"SHA\.new"],
    "CWE-347": [r"jwt\.decode\s*\(", r"verify_signature\s*:\s*False", r"options\s*=\s*\{[^}]*verify_signature", r"jwt\.verify", r"alg.*none"],
    "CWE-209": [r"traceback\.format_exc", r"debug\s*=\s*True", r"err\.stack", r"error\.stack", r"printStackTrace"],
    "CWE-1333": [r"re\.compile\s*\(", r"re\.search\s*\(", r"re\.match\s*\(", r"new\s+RegExp\s*\(", r"\.match\s*\(\s*new\s+RegExp"],
    "CWE-1427": [r"chat\.completions\.create", r"llm\.invoke", r"PromptTemplate", r"system_prompt", r"messages\s*=\s*\["],
    "CWE-1426": [r"chat\.completions\.create", r"llm\.invoke", r"openai\.", r"anthropic\."],
    "CWE-200": [r"jsonify\s*\(", r"res\.json\s*\(", r"logging\.", r"console\.log", r"system_instructions", r"confidential"],
}


def clean_code_for_rag_query(code: str) -> list:
    """
    1. Strip leading '123| ' line number prefixes (present in GHSA multi-function samples).
    2. Strip pure import / comment lines so ONNXMiniLM_L6_V2's 256-token window focuses on executable statements & sinks.
    3. Return up to 4 overlapping chunks of 900 chars (~220 tokens) so multi-function files are not truncated at line 35.
    """
    cleaned_lines = []
    for line in code.splitlines():
        line_no_num = re.sub(r"^\s*\d+\|\s?", "", line)
        stripped = line_no_num.strip()
        if not stripped:
            continue
        if stripped.startswith(("import ", "from ", "#", "//", "/*", "*", "*/")):
            continue
        cleaned_lines.append(line_no_num)

    full_cleaned = "\n".join(cleaned_lines) if cleaned_lines else code
    chunks = []
    step = 800
    # Scan up to 20,000 characters across the file (up to 12 chunks of 900 chars) so sinks anywhere in multi-function files are embedded
    for start in range(0, min(len(full_cleaned), 20000), step):
        chunk = full_cleaned[start : start + 900]
        if chunk.strip():
            chunks.append(chunk)
        if len(chunks) >= 12:
            break
    return chunks or [code[:900]]


def retrieve_rag_context(
    collection, code, language, top_k=5, include_kb_snippets=True
):
    """
    Retrieve top-k relevant security catalogue entries from ChromaDB for language
    using Hybrid Multi-Chunk Vector Search + Lexical Sink-Signature Reranking,
    deduplicated by cwe_id so top_k always provides distinct CWE candidates.
    Note: RAG is pulled identically regardless of whether the prompt mode is
    zero-shot, one-shot, few-shot, or cot.
    """
    lang = language.lower()
    chunks = clean_code_for_rag_query(code)
    candidate_pool_size = max(top_k * 4, 28)

    try:
        results = collection.query(
            query_texts=chunks,
            where={"language": lang},
            n_results=candidate_pool_size,
            include=["metadatas", "documents", "distances"],
        )
    except Exception:
        results = collection.query(
            query_texts=chunks,
            n_results=candidate_pool_size,
            include=["metadatas", "documents", "distances"],
        )

    best_score_by_kb = {}
    meta_by_kb = {}
    all_metadatas = results.get("metadatas") or []
    all_distances = results.get("distances") or []

    for chunk_idx in range(len(all_metadatas)):
        metas = all_metadatas[chunk_idx]
        dists = all_distances[chunk_idx] if chunk_idx < len(all_distances) else [1.0] * len(metas)
        for m, d in zip(metas, dists):
            kid = m.get("kb_id") or m.get("catalogue_id") or str(id(m))
            meta_by_kb[kid] = m
            if kid not in best_score_by_kb or d < best_score_by_kb[kid]:
                best_score_by_kb[kid] = d

    # Apply Sink-Signature Reranking Boost when explicit sink APIs appear in the code
    for kid, m in meta_by_kb.items():
        cwe = m.get("cwe_id", "")
        patterns = CWE_SINK_SIGNATURES.get(cwe, [])
        if patterns:
            match_count = sum(1 for pat in patterns if re.search(pat, code, re.IGNORECASE))
            if match_count > 0:
                best_score_by_kb[kid] -= min(0.35, 0.12 * match_count)

    # Sort by hybrid score and deduplicate by cwe_id so top_k contains distinct CWE rules
    ranked_kids = sorted(best_score_by_kb.keys(), key=lambda k: best_score_by_kb[k])
    selected_metadatas = []
    seen_cwes = set()
    for kid in ranked_kids:
        m = meta_by_kb[kid]
        cwe = m.get("cwe_id", "")
        if cwe and cwe in seen_cwes:
            continue
        if cwe:
            seen_cwes.add(cwe)
        selected_metadatas.append(m)
        if len(selected_metadatas) >= top_k:
            break

    context_lines = [f"### Retrieved RAG Knowledge Base Context ({lang}, top_k={top_k}):"]

    for m in selected_metadatas:
        cid = m.get("catalogue_id", "")
        cwe = m.get("cwe_id", "")
        name = m.get("cwe_name", "")
        sources = m.get("sources", "N/A")
        sinks = m.get("sinks", "N/A")
        sanitizers = m.get("sanitizers", "N/A")

        rule_block = (
            f"- [{cid}] {cwe} ({name}):\n"
            f"  * Sources: {sources}\n"
            f"  * Sinks: {sinks}\n"
            f"  * Valid Sanitizers: {sanitizers}"
        )
        if include_kb_snippets and m.get("has_example"):
            orig_ex = m.get("example_original_code", "").strip()[:500]
            fixed_ex = m.get("example_fixed_code", "").strip()[:500]
            if orig_ex:
                rule_block += f"\n  * KB Reference Flaw Pattern:\n```\n{orig_ex}\n```"
            if fixed_ex:
                rule_block += f"\n  * KB Reference Remediation Pattern:\n```\n{fixed_ex}\n```"

        context_lines.append(rule_block)

    return "\n\n".join(context_lines)


def build_prompt(
    sample,
    collection,
    prompt_mode="zero-shot",
    top_k=5,
    include_kb_snippets=True,
):
    """
    Construct the prompt for the selected Prompting Mode while pulling RAG separately:
      1. RAG Context is pulled first via retrieve_rag_context() (identical across all 4 modes).
      2. The Prompt Template varies by mode:
         - zero-shot : 0 task demonstrations (Direct instructions only)
         - one-shot  : 1 task demonstration (ONE_SHOT_DEMONSTRATION: 1 Input Code -> Expected JSON Output)
         - few-shot  : 3 task demonstrations (FEW_SHOT_DEMONSTRATIONS: 3 Input Code -> Expected JSON Outputs)
         - cot       : Explicit 4-step Chain-of-Thought instructions + COT_DEMONSTRATION
    """
    lang = sample.get("language", "python")
    code = sample.get("original_code", "")
    mode = prompt_mode.lower().strip()

    # Step 1: Pull RAG context separately (constant across all prompt modes)
    rag_block = retrieve_rag_context(
        collection=collection,
        code=code,
        language=lang,
        top_k=top_k,
        include_kb_snippets=include_kb_snippets,
    )

    standard_instructions = """### Step-by-Step Analysis Instructions:
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
2. Populate "cwe_id", "vulnerability_detected", and "reason" directly from your Step 4 conclusion."""

    # Step 2: Assemble mode-specific prompt
    if mode == "zero-shot":
        prompt = f"""{rag_block}

### Code to Inspect ({lang}):
```{lang}
{code}
```

{standard_instructions}
"""
    elif mode == "one-shot":
        prompt = f"""{rag_block}

{ONE_SHOT_DEMONSTRATION}

### Code to Inspect ({lang}):
```{lang}
{code}
```

{standard_instructions}
"""
    elif mode == "few-shot":
        prompt = f"""{rag_block}

{FEW_SHOT_DEMONSTRATIONS}

### Code to Inspect ({lang}):
```{lang}
{code}
```

{standard_instructions}
"""
    elif mode == "cot":
        prompt = f"""{rag_block}

{COT_DEMONSTRATION}

### Code to Inspect ({lang}):
```{lang}
{code}
```

{cot_instructions}
"""
    else:
        raise ValueError(f"Unsupported prompt_mode: {prompt_mode}")

    return prompt


def call_ollama_with_retry(
    prompt,
    model,
    system=SYSTEM_PROMPT,
    base_url="http://localhost:11434",
    timeout=180,
    max_retries=3,
):
    """
    Call Ollama with multi-attempt retry and fallback without format='json' if a reasoning
    model fails to emit valid JSON on the final retry.
    """
    for attempt in range(1, max_retries + 1):
        payload = {
            "model": model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "format": "json" if attempt < max_retries else "",
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "num_predict": 1024,
                "num_ctx": 8192,
            },
        }
        if not payload["format"]:
            del payload["format"]

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        start_time = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                latency = time.time() - start_time
                res_json = json.loads(response.read().decode("utf-8"))
                return res_json, latency, None
        except Exception as e:
            latency = time.time() - start_time
            if attempt < max_retries:
                time.sleep(2 * attempt)
            else:
                return None, latency, str(e)


def parse_llm_json(raw_text):
    """
    Multi-tier fault-tolerant parser with explicit parse_tier tracking:
      - tier 1: "strict_json" (Valid JSON directly after stripping <think> / code fences)
      - tier 2: "regex_json_block" (Extracted outermost {...} JSON block)
      - tier 3: "regex_cwe_fallback" (Regex extracted CWE-XXX or CWE-NONE from malformed text)
      - tier 4: "failed" (Unparseable / empty response)
    """
    default_res = {
        "cwe_id": "UNKNOWN",
        "cwe_name": "Unknown",
        "vulnerability_detected": False,
        "risk_level": "Unknown",
        "cvss_v31_base": 0.0,
        "reason": "",
        "cot_steps": None,
        "parse_tier": "failed",
    }
    if not raw_text:
        return default_res

    text = raw_text.strip()
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

    def normalize_cwe_label(value):
        if not value:
            return "UNKNOWN"
        label = str(value).upper().strip()
        if label in {"NONE", "CWE-NONE", "CWE_NONE", "SAFE", "BENIGN", "NO_VULNERABILITY"}:
            return "CWE-NONE"
        m = re.search(r"CWE-\d+", label)
        if m:
            return m.group(0)
        return label

    def extract_fields(data, tier_name):
        cwe_raw = normalize_cwe_label(
            data.get("cwe_id") or data.get("confirmed_cwe") or "UNKNOWN"
        )
        cot_steps = data.get("cot_steps")
        if cwe_raw == "UNKNOWN" and isinstance(cot_steps, dict):
            step4 = str(cot_steps.get("step4_verdict_derivation", ""))
            cwe_from_step4 = normalize_cwe_label(step4)
            if cwe_from_step4.startswith("CWE-"):
                cwe_raw = cwe_from_step4

        vuln_detected = bool(
            data.get("vulnerability_detected", cwe_raw not in ["CWE-NONE", "UNKNOWN"])
        )
        if cwe_raw == "CWE-NONE":
            vuln_detected = False
        reason = str(data.get("reason", ""))
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
        }

    # Tier 1: Standard JSON parsing
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return extract_fields(data, "strict_json")
    except Exception:
        pass

    # Tier 2: Extract outermost JSON {...} block via regex
    json_block = re.search(r"\{[\s\S]*\}", text)
    if json_block:
        try:
            data = json.loads(json_block.group(0))
            if isinstance(data, dict):
                return extract_fields(data, "regex_json_block")
        except Exception:
            pass

    # Tier 3: Regex fallback search for CWE identifier or CWE-NONE in raw text
    cwe_none_match = re.search(r"CWE-NONE", text, re.IGNORECASE)
    cwe_id_match = re.search(r"CWE-\d+", text, re.IGNORECASE)
    if cwe_none_match:
        cwe = "CWE-NONE"
    elif cwe_id_match:
        cwe = normalize_cwe_label(cwe_id_match.group(0))
    else:
        cwe = "UNKNOWN"

    cat_meta = get_deterministic_cwe_metadata(cwe)
    return {
        "cwe_id": cwe,
        "cwe_name": cat_meta["cwe_name"],
        "vulnerability_detected": cwe not in ["UNKNOWN", "CWE-NONE", "NONE"],
        "risk_level": cat_meta["risk_level"] if cwe != "UNKNOWN" else "Unknown",
        "cvss_v31_base": cat_meta["cvss_v31_base"] if cwe != "UNKNOWN" else 0.0,
        "reason": text[:250],
        "cot_steps": None,
        "parse_tier": "regex_cwe_fallback" if cwe != "UNKNOWN" else "failed",
    }


def clean_path_component(value):
    """Make a user-provided model or run name safe for use as a path component."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value)).strip("_")
    return cleaned or "default"


def get_run_dir(tag=None):
    """Return the stable output directory for a tagged benchmark run."""
    return RUNS_DIR / clean_path_component(tag or "default")


def get_checkpoint_path(model_name, prompt_mode="zero-shot", tag=None):
    """Separate checkpoint path per (model_name, prompt_mode) so modes never overwrite each other."""
    clean_model = clean_path_component(model_name)
    clean_mode = clean_path_component(prompt_mode)
    checkpoint_dir = get_run_dir(tag) / "checkpoints" / clean_model / clean_mode
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    return checkpoint_dir / "checkpoint.json"


def load_checkpoint(model_name, prompt_mode="zero-shot", tag=None):
    cp_path = get_checkpoint_path(model_name, prompt_mode, tag)
    if cp_path.exists():
        try:
            with open(cp_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("completed_results", {}), cp_path
        except Exception:
            return {}, cp_path
    legacy_path = get_run_dir(tag) / "checkpoints" / clean_path_component(model_name) / "checkpoint.json"
    if prompt_mode == "zero-shot" and legacy_path.exists():
        try:
            with open(legacy_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("completed_results", {}), legacy_path
        except Exception:
            pass
    return {}, cp_path


def save_checkpoint(model_name, completed_results, prompt_mode="zero-shot", tag=None):
    cp_path = get_checkpoint_path(model_name, prompt_mode, tag)
    with open(cp_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "model": model_name,
                "prompt_mode": prompt_mode,
                "tag": tag or "default",
                "timestamp": int(time.time()),
                "total_completed": len(completed_results),
                "completed_results": completed_results,
            },
            f,
            indent=2,
        )


def compute_macro_f1(results):
    """Compute unweighted Macro-F1 across all true CWE classes present in the dataset."""
    true_classes = sorted({str(r.get("true_cwe", "UNKNOWN")) for r in results if r.get("true_cwe")})
    if not true_classes:
        return 0.0

    f1_sum = 0.0
    for c in true_classes:
        tp = sum(1 for r in results if r.get("true_cwe") == c and r.get("predicted_cwe") == c)
        fp = sum(1 for r in results if r.get("true_cwe") != c and r.get("predicted_cwe") == c)
        fn = sum(1 for r in results if r.get("true_cwe") == c and r.get("predicted_cwe") != c)
        prec = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rec = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        f1_sum += f1

    return f1_sum / len(true_classes)


def compute_percentile(values, percentile=95):
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = min(len(sorted_vals) - 1, max(0, math.ceil((percentile / 100.0) * len(sorted_vals)) - 1))
    return sorted_vals[idx]


def build_confusion_matrix(results):
    """Build a multiclass CWE confusion matrix from model results."""
    def label_for(result, field):
        value = result.get(field)
        return str(value) if value else "UNKNOWN"

    labels = sorted(
        {
            label
            for result in results
            for label in (label_for(result, "true_cwe"), label_for(result, "predicted_cwe"))
        }
    )
    matrix = {
        true_label: {predicted_label: 0 for predicted_label in labels}
        for true_label in labels
    }
    for result in results:
        true_label = label_for(result, "true_cwe")
        predicted_label = label_for(result, "predicted_cwe")
        matrix[true_label][predicted_label] += 1
    return {"labels": labels, "matrix": matrix}


def export_confusion_matrix(summary, output_dir):
    """Export one (model, prompt_mode) confusion matrix as JSON, CSV, and PNG."""
    model_name = clean_path_component(summary["model"])
    mode_name = clean_path_component(summary.get("prompt_mode", "zero-shot"))
    confusion_matrix = summary["confusion_matrix"]

    json_path = output_dir / f"confusion_matrix_{model_name}_{mode_name}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "model": summary["model"],
                "prompt_mode": summary.get("prompt_mode", "zero-shot"),
                "checkpoint_tag": summary["checkpoint_tag"],
                **confusion_matrix,
            },
            f,
            indent=2,
        )

    csv_path = output_dir / f"confusion_matrix_{model_name}_{mode_name}.csv"
    labels = confusion_matrix["labels"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["True CWE"] + labels)
        for true_label in labels:
            writer.writerow(
                [true_label]
                + [confusion_matrix["matrix"][true_label][predicted_label] for predicted_label in labels]
            )

    image_path = output_dir / f"confusion_matrix_{model_name}_{mode_name}.png"
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        values = [
            [confusion_matrix["matrix"][true_label][predicted_label] for predicted_label in labels]
            for true_label in labels
        ]
        size = max(8, min(18, 5 + len(labels) * 0.35))
        fig, ax = plt.subplots(figsize=(size, size * 0.85), dpi=160)
        image = ax.imshow(values, cmap="Blues", aspect="auto")
        fig.colorbar(image, ax=ax, label="Number of samples")
        ax.set(
            xticks=range(len(labels)),
            yticks=range(len(labels)),
            xticklabels=labels,
            yticklabels=labels,
            xlabel="Predicted CWE",
            ylabel="True CWE",
            title=f"CWE Confusion Matrix - {summary['model']} [{summary.get('prompt_mode', 'zero-shot').upper()}]",
        )
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
        threshold = max((max(row) for row in values), default=0) / 2
        for row_index, row in enumerate(values):
            for column_index, value in enumerate(row):
                ax.text(
                    column_index,
                    row_index,
                    str(value),
                    ha="center",
                    va="center",
                    color="white" if value > threshold else "black",
                    fontsize=8,
                )
        fig.tight_layout()
        fig.savefig(image_path, bbox_inches="tight")
        plt.close(fig)
    except Exception as exc:
        print(f"⚠️ Warning: Could not render confusion matrix PNG: {exc}")

    return json_path, csv_path, image_path


def build_report_findings(summary):
    """Create concise, report-ready findings from one (model, prompt_mode) run."""
    results = summary["results"]
    none_predictions = sum(
        1 for result in results if result.get("predicted_cwe") in {"CWE-NONE", "NONE"}
    )
    incorrect_pairs = Counter(
        (result.get("true_cwe", "UNKNOWN"), result.get("predicted_cwe", "UNKNOWN"))
        for result in results
        if not result.get("is_correct")
    )
    top_confusions = incorrect_pairs.most_common(5)
    none_rate = (none_predictions / len(results) * 100) if results else 0.0
    findings = [
        f"- **Prompting Mode:** `{summary.get('prompt_mode', 'zero-shot')}` ({PROMPT_MODE_LABELS.get(summary.get('prompt_mode', 'zero-shot'), '')})",
        f"- **Exact CWE Accuracy:** {summary['overall_accuracy_percent']} ({summary['correct_predictions']}/{summary['total_samples']}) | **Macro-F1:** {summary.get('macro_f1_percent', '0.00%')}",
        f"- **Binary Vulnerability Detection:** Precision: {summary.get('binary_precision_percent', 'N/A')} | Recall: {summary.get('binary_recall_percent', 'N/A')} | Binary F1: **{summary.get('binary_f1_percent', 'N/A')}** | FPR: {summary.get('false_positive_rate_percent', 'N/A')}",
        f"- **Speed & Token Metrics:** Avg Latency: {summary['avg_latency_sec']}s (P95: {summary.get('p95_latency_sec', 0)}s) | Gen Speed: **{summary['tokens_per_sec']} tok/s** | Prompt Eval Speed: {summary.get('prompt_tokens_per_sec', 0)} tok/s | Avg Tokens (In/Out): {summary.get('avg_prompt_tokens', 0)} / {summary.get('avg_output_tokens', 0)}",
        f"- **Reliability:** Strict JSON Rate: {summary.get('strict_json_rate_percent', '100.00%')} | Parse Fallback Rate: {summary.get('parse_fallback_rate_percent', '0.00%')} | CWE-NONE Predictions: {none_predictions}/{len(results)} ({none_rate:.2f}%)",
    ]
    if top_confusions:
        confusion_text = "; ".join(
            f"{true_cwe} -> {predicted_cwe} ({count})"
            for (true_cwe, predicted_cwe), count in top_confusions
        )
        findings.append(f"- **Most frequent misclassifications:** {confusion_text}.")
    else:
        findings.append("- **Most frequent misclassifications:** None.")
    return findings


def export_individual_model_prompt_report(summary, output_dir, confusion_image_path):
    """Save standalone Markdown and CSV report for a single (model, prompt_mode) pair."""
    clean_model = clean_path_component(summary["model"])
    clean_mode = clean_path_component(summary.get("prompt_mode", "zero-shot"))

    md_path = output_dir / f"report_{clean_model}_{clean_mode}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# CodeDEE Individual Evaluation Report: {summary['model']} ({summary.get('prompt_mode', 'zero-shot').upper()})\n\n")
        f.write("\n".join(build_report_findings(summary)) + "\n\n")
        f.write("## Summary Metrics Table\n\n")
        f.write("| Metric | Value |\n| :--- | :---: |\n")
        metrics_rows = [
            ("Model", summary["model"]),
            ("Prompting Mode", summary.get("prompt_mode", "zero-shot")),
            ("Total Samples Evaluated", summary["total_samples"]),
            ("Exact CWE Accuracy", summary["overall_accuracy_percent"]),
            ("Macro-F1 (28 CWEs)", summary.get("macro_f1_percent", "N/A")),
            ("Python CWE Accuracy", summary["python_accuracy"]),
            ("JavaScript CWE Accuracy", summary["javascript_accuracy"]),
            ("TypeScript CWE Accuracy", summary["typescript_accuracy"]),
            ("Binary Precision (Vuln vs Safe)", summary.get("binary_precision_percent", "N/A")),
            ("Binary Recall / TPR", summary.get("binary_recall_percent", "N/A")),
            ("Binary F1-Score", summary.get("binary_f1_percent", "N/A")),
            ("Specificity / TNR", summary.get("specificity_percent", "N/A")),
            ("False Positive Rate (FPR)", summary.get("false_positive_rate_percent", "N/A")),
            ("Avg Inference Latency (s)", f"{summary['avg_latency_sec']}s"),
            ("P95 Inference Latency (s)", f"{summary.get('p95_latency_sec', 0)}s"),
            ("Output Generation Speed (tok/s)", f"{summary['tokens_per_sec']} tok/s"),
            ("Prompt Evaluation Speed (tok/s)", f"{summary.get('prompt_tokens_per_sec', 0)} tok/s"),
            ("Avg Input Prompt Tokens", summary.get("avg_prompt_tokens", 0)),
            ("Avg Output Generated Tokens", summary.get("avg_output_tokens", 0)),
            ("Strict JSON Compliance Rate", summary.get("strict_json_rate_percent", "100.00%")),
            ("JSON Parse Fallback Rate", summary.get("parse_fallback_rate_percent", "0.00%")),
        ]
        for k, v in metrics_rows:
            f.write(f"| **{k}** | {v} |\n")
        f.write(f"\n## Confusion Matrix\n\n![Confusion Matrix]({confusion_image_path.name})\n")

    csv_path = output_dir / f"sample_predictions_{clean_model}_{clean_mode}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "sample_id",
            "language",
            "prompt_mode",
            "true_cwe",
            "predicted_cwe",
            "is_correct",
            "vulnerability_detected",
            "risk_level",
            "cvss_v31_base",
            "parse_tier",
            "latency_sec",
            "prompt_tokens",
            "tokens_generated",
            "tokens_per_sec",
            "reason",
        ])
        for r in summary["results"]:
            writer.writerow([
                r.get("sample_id", ""),
                r.get("language", ""),
                r.get("prompt_mode", ""),
                r.get("true_cwe", ""),
                r.get("predicted_cwe", ""),
                r.get("is_correct", False),
                r.get("vulnerability_detected", False),
                r.get("risk_level", ""),
                r.get("cvss_v31_base", 0.0),
                r.get("parse_tier", ""),
                round(r.get("latency_sec", 0.0), 3),
                r.get("prompt_tokens", 0),
                r.get("tokens_generated", 0),
                round(r.get("sample_tok_per_sec", 0.0), 2),
                r.get("reason", "")[:300],
            ])

    return md_path, csv_path


def evaluate_model_full_scale(
    model_name,
    samples,
    collection,
    prompt_mode="zero-shot",
    top_k=5,
    include_kb_snippets=True,
    save_interval=20,
    resume=False,
    fresh=False,
    checkpoint_tag=None,
):
    print(f"\n{'=' * 78}")
    print(f"🚀 EVALUATING MODEL: {model_name} | PROMPT MODE: {prompt_mode.upper()}")
    print(
        f"Total Samples: {len(samples)} | Mode: {PROMPT_MODE_LABELS.get(prompt_mode, prompt_mode)} | RAG Top-K: {top_k}"
    )
    if checkpoint_tag:
        print(f"🏷️ Run Tag: {checkpoint_tag}")
    print(f"{'=' * 78}")

    completed_map = {}
    cp_path = get_checkpoint_path(model_name, prompt_mode, checkpoint_tag)

    if fresh:
        if cp_path.exists():
            backup_old = cp_path.with_name(f"{cp_path.stem}_archived_{int(time.time())}.json")
            try:
                shutil.copy2(cp_path, backup_old)
                print(f"📦 Archived existing checkpoint to {backup_old.name}")
            except Exception:
                pass
        print(f"✨ Fresh run forced (--fresh). Starting from 0 samples.")
    elif resume:
        completed_map, loaded_path = load_checkpoint(model_name, prompt_mode, checkpoint_tag)
        if completed_map:
            print(f"🔄 Resuming from checkpoint ({loaded_path}): {len(completed_map)} samples already evaluated.")
        else:
            print(f"ℹ️ No existing checkpoint found for ({model_name}, {prompt_mode}). Starting fresh.")
    else:
        existing, loaded_path = load_checkpoint(model_name, prompt_mode, checkpoint_tag)
        if existing:
            sample_ids_set = {s.get("sample_id") for s in samples}
            evaluated_ids_set = set(existing.keys())
            overlap = evaluated_ids_set.intersection(sample_ids_set)

            print(f"\n{'!' * 70}")
            print(f"⚠️ Existing checkpoint found: {loaded_path}")
            print(f"   Saved samples in checkpoint: {len(existing)}")
            print(f"   Current dataset samples to run: {len(samples)} (Overlap: {len(overlap)})")
            print(f"{'!' * 70}")

            choice = "1"
            if sys.stdin.isatty():
                try:
                    user_input = input(
                        f"How would you like to handle checkpoint for '{model_name}' [{prompt_mode}]?\n"
                        f"  [1] Start FRESH run (archive old checkpoint) [Default]\n"
                        f"  [2] RESUME from existing checkpoint\n"
                        f"Select [1/2]: "
                    ).strip()
                    if user_input in ["2", "resume", "r", "y", "yes"]:
                        choice = "2"
                except Exception:
                    choice = "1"
            else:
                print("ℹ️ Non-interactive terminal: Defaulting to FRESH run [1]. (Pass --resume to resume)")

            if choice == "2":
                completed_map = existing
                print(f"🔄 Resumed {len(completed_map)} samples.")
            else:
                completed_map = {}
                backup_old = cp_path.with_name(f"{cp_path.stem}_archived_{int(time.time())}.json")
                try:
                    if cp_path.exists():
                        shutil.copy2(cp_path, backup_old)
                        print(f"📦 Archived old checkpoint to {backup_old.name}")
                except Exception:
                    pass

    valid_ids = {s.get("sample_id") for s in samples}
    completed_map = {k: v for k, v in completed_map.items() if k in valid_ids}

    results = list(completed_map.values())
    correct_count = sum(1 for r in results if r.get("is_correct"))
    total_latency = sum(r.get("latency_sec", 0.0) for r in results)
    total_tokens = sum(r.get("tokens_generated", 0) for r in results)

    start_run_time = time.time()

    active_system = SYSTEM_PROMPT_COT if prompt_mode.lower() == "cot" else SYSTEM_PROMPT

    for idx, s in enumerate(samples, 1):
        sid = s.get("sample_id")
        lang = s.get("language")
        true_cwe = s.get("cwe_id")

        if sid in completed_map:
            continue

        prompt = build_prompt(
            sample=s,
            collection=collection,
            prompt_mode=prompt_mode,
            top_k=top_k,
            include_kb_snippets=include_kb_snippets,
        )

        resp, latency, err = call_ollama_with_retry(prompt, model=model_name, system=active_system)
        total_latency += latency

        if err:
            print(
                f"[{idx}/{len(samples)}] {sid} ({lang} | {prompt_mode}) -> ❌ Error: {err} ({latency:.2f}s)"
            )
            item = {
                "sample_id": sid,
                "language": lang,
                "prompt_mode": prompt_mode,
                "true_cwe": true_cwe,
                "predicted_cwe": "ERROR",
                "is_correct": False,
                "vulnerability_detected": False,
                "risk_level": "Unknown",
                "cvss_v31_base": 0.0,
                "reason": err,
                "cot_steps": None,
                "parse_tier": "failed",
                "latency_sec": latency,
                "prompt_tokens": 0,
                "tokens_generated": 0,
                "eval_duration_sec": 0.0,
                "prompt_eval_duration_sec": 0.0,
                "sample_tok_per_sec": 0.0,
            }
        else:
            raw_text = resp.get("response", "")
            parsed = parse_llm_json(raw_text)
            tokens = int(resp.get("eval_count", 0) or 0)
            prompt_tokens = int(resp.get("prompt_eval_count", 0) or 0)
            eval_dur_sec = float(resp.get("eval_duration", 0) or 0) / 1e9
            prompt_dur_sec = float(resp.get("prompt_eval_duration", 0) or 0) / 1e9
            sample_tok_s = (tokens / eval_dur_sec) if eval_dur_sec > 0 else ((tokens / latency) if latency > 0 else 0.0)

            total_tokens += tokens

            is_match = parsed["cwe_id"] == true_cwe
            if is_match:
                correct_count += 1
                status = "✅ MATCH"
            else:
                status = f"⚠️ MISMATCH (Pred: {parsed['cwe_id']})"

            item = {
                "sample_id": sid,
                "language": lang,
                "prompt_mode": prompt_mode,
                "true_cwe": true_cwe,
                "predicted_cwe": parsed["cwe_id"],
                "is_correct": is_match,
                "vulnerability_detected": parsed["vulnerability_detected"],
                "cwe_name": parsed.get("cwe_name", ""),
                "risk_level": parsed["risk_level"],
                "cvss_v31_base": parsed.get("cvss_v31_base", 0.0),
                "reason": parsed["reason"],
                "cot_steps": parsed.get("cot_steps"),
                "parse_tier": parsed.get("parse_tier", "strict_json"),
                "latency_sec": latency,
                "prompt_tokens": prompt_tokens,
                "tokens_generated": tokens,
                "eval_duration_sec": round(eval_dur_sec, 4),
                "prompt_eval_duration_sec": round(prompt_dur_sec, 4),
                "sample_tok_per_sec": round(sample_tok_s, 2),
            }

            print(
                f"[{idx}/{len(samples)}] {sid} ({lang} | {prompt_mode} | True: {true_cwe}) -> {status} | {latency:.2f}s ({sample_tok_s:.1f} tok/s)"
            )

        completed_map[sid] = item
        results.append(item)

        if len(completed_map) % save_interval == 0 or idx == len(samples):
            save_checkpoint(model_name, completed_map, prompt_mode=prompt_mode, tag=checkpoint_tag)

    elapsed_time = time.time() - start_run_time
    n_total = len(results) if results else 1

    # 1. Multi-class CWE metrics
    accuracy = correct_count / n_total
    macro_f1 = compute_macro_f1(results)

    # 2. Binary Vulnerability Detection metrics (Vulnerable vs Safe CWE-NONE)
    tp = sum(1 for r in results if r.get("true_cwe") != "CWE-NONE" and r.get("predicted_cwe") not in ("CWE-NONE", "UNKNOWN", "ERROR"))
    fn = sum(1 for r in results if r.get("true_cwe") != "CWE-NONE" and r.get("predicted_cwe") in ("CWE-NONE", "UNKNOWN", "ERROR"))
    tn = sum(1 for r in results if r.get("true_cwe") == "CWE-NONE" and r.get("predicted_cwe") == "CWE-NONE")
    fp = sum(1 for r in results if r.get("true_cwe") == "CWE-NONE" and r.get("predicted_cwe") != "CWE-NONE")

    has_safe_samples = (tn + fp) > 0
    binary_precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    binary_recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    binary_f1 = (
        (2 * binary_precision * binary_recall / (binary_precision + binary_recall))
        if (binary_precision + binary_recall) > 0
        else 0.0
    )
    specificity = (tn / (tn + fp)) if has_safe_samples else 0.0
    fpr = (fp / (fp + tn)) if has_safe_samples else 0.0

    # 3. Latency & Token Speed metrics
    latencies = [float(r.get("latency_sec", 0.0)) for r in results]
    avg_latency = sum(latencies) / n_total
    p95_latency = compute_percentile(latencies, 95)

    total_eval_dur = sum(float(r.get("eval_duration_sec", 0.0)) for r in results)
    total_prompt_dur = sum(float(r.get("prompt_eval_duration_sec", 0.0)) for r in results)
    total_out_tokens = sum(int(r.get("tokens_generated", 0)) for r in results)
    total_in_tokens = sum(int(r.get("prompt_tokens", 0)) for r in results)

    tokens_per_sec = (
        (total_out_tokens / total_eval_dur)
        if total_eval_dur > 0
        else ((total_out_tokens / total_latency) if total_latency > 0 else 0.0)
    )
    prompt_tokens_per_sec = (total_in_tokens / total_prompt_dur) if total_prompt_dur > 0 else 0.0
    avg_prompt_tokens = round(total_in_tokens / n_total, 1)
    avg_output_tokens = round(total_out_tokens / n_total, 1)

    # 4. Reliability / Parse Tier metrics
    strict_json_count = sum(1 for r in results if r.get("parse_tier") == "strict_json")
    fallback_count = sum(1 for r in results if r.get("parse_tier") in ("regex_json_block", "regex_cwe_fallback", "failed"))
    strict_json_rate = strict_json_count / n_total
    fallback_rate = fallback_count / n_total

    # 5. Language breakdown
    lang_stats = defaultdict(lambda: {"total": 0, "correct": 0})
    for r in results:
        l = r.get("language", "unknown")
        lang_stats[l]["total"] += 1
        if r.get("is_correct"):
            lang_stats[l]["correct"] += 1

    summary = {
        "model": model_name,
        "prompt_mode": prompt_mode,
        "checkpoint_tag": checkpoint_tag or "default",
        "total_samples": len(results),
        "correct_predictions": correct_count,
        "overall_accuracy": round(accuracy, 4),
        "overall_accuracy_percent": f"{accuracy * 100:.2f}%",
        "macro_f1": round(macro_f1, 4),
        "macro_f1_percent": f"{macro_f1 * 100:.2f}%",
        "binary_precision_percent": f"{binary_precision * 100:.2f}%",
        "binary_recall_percent": f"{binary_recall * 100:.2f}%",
        "binary_f1": round(binary_f1, 4),
        "binary_f1_percent": f"{binary_f1 * 100:.2f}%",
        "specificity_percent": f"{specificity * 100:.2f}%" if has_safe_samples else "N/A (Vuln-Only)",
        "false_positive_rate_percent": f"{fpr * 100:.2f}%" if has_safe_samples else "N/A (Vuln-Only)",
        "avg_latency_sec": round(avg_latency, 2),
        "p95_latency_sec": round(p95_latency, 2),
        "total_elapsed_sec": round(elapsed_time, 2),
        "tokens_per_sec": round(tokens_per_sec, 2),
        "prompt_tokens_per_sec": round(prompt_tokens_per_sec, 2),
        "avg_prompt_tokens": avg_prompt_tokens,
        "avg_output_tokens": avg_output_tokens,
        "strict_json_rate_percent": f"{strict_json_rate * 100:.2f}%",
        "parse_fallback_rate_percent": f"{fallback_rate * 100:.2f}%",
        "python_accuracy": f"{(lang_stats['python']['correct'] / lang_stats['python']['total'] * 100):.2f}%"
        if lang_stats["python"]["total"]
        else "0.00%",
        "javascript_accuracy": f"{(lang_stats['javascript']['correct'] / lang_stats['javascript']['total'] * 100):.2f}%"
        if lang_stats["javascript"]["total"]
        else "0.00%",
        "typescript_accuracy": f"{(lang_stats['typescript']['correct'] / lang_stats['typescript']['total'] * 100):.2f}%"
        if lang_stats["typescript"]["total"]
        else "0.00%",
        "results": results,
    }

    summary["confusion_matrix"] = build_confusion_matrix(results)

    clean_name = clean_path_component(model_name)
    clean_mode = clean_path_component(prompt_mode)
    run_dir = get_run_dir(checkpoint_tag)
    results_dir = run_dir / "results" / clean_name / clean_mode
    results_dir.mkdir(parents=True, exist_ok=True)

    final_model_path = results_dir / f"full_eval_{clean_name}_{clean_mode}.json"
    with open(final_model_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    confusion_json_path, confusion_csv_path, confusion_image_path = export_confusion_matrix(
        summary, results_dir
    )
    indiv_md_path, indiv_csv_path = export_individual_model_prompt_report(
        summary, results_dir, confusion_image_path
    )

    print(f"\n🎯 Completed: {model_name} [{prompt_mode.upper()}]")
    print(
        f"   Exact CWE Acc: {summary['overall_accuracy_percent']} | Macro-F1: {summary['macro_f1_percent']} | Binary F1: {summary['binary_f1_percent']}"
    )
    print(
        f"   Avg Latency: {avg_latency:.2f}s (P95: {p95_latency:.2f}s) | Gen Speed: {summary['tokens_per_sec']} tok/s | Fallback Rate: {summary['parse_fallback_rate_percent']}"
    )
    print(f"   Individual Report: {indiv_md_path}")
    return summary


def export_reports(all_summaries, checkpoint_tag=None, dataset_name="v3"):
    """
    Export Master Markdown and CSV reports containing:
      1. Prompting Paradigm Comparison Matrix (Zero-Shot vs One-Shot vs Few-Shot vs CoT side-by-side)
      2. Ranked Overall Leaderboard (all Model x Prompt combinations with full metrics + token speed)
      3. Per-Prompt-Mode Sub-Leaderboards
      4. Per-(Model, Prompt) Confusion Matrices & Detailed Findings
    """
    if not all_summaries:
        return

    reports_dir = get_run_dir(checkpoint_tag) / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    md_latest = reports_dir / "master_benchmark_report_latest.md"
    csv_latest = reports_dir / "master_benchmark_report_latest.csv"

    by_model = defaultdict(dict)
    present_modes = []
    for s in all_summaries:
        m = s["model"]
        pm = s.get("prompt_mode", "zero-shot")
        by_model[m][pm] = s
        if pm not in present_modes:
            present_modes.append(pm)

    ordered_modes = [m for m in CORE_PROMPT_MODES if m in present_modes] + [
        m for m in present_modes if m not in CORE_PROMPT_MODES
    ]

    with open(md_latest, "w", encoding="utf-8") as f:
        f.write("# CodeDEE: Full-Scale Multi-Prompt & Multi-Model Evaluation Report\n\n")
        f.write(f"- **Dataset Evaluated:** `{dataset_name}` ({all_summaries[0]['total_samples']} Samples per run)\n")
        f.write(f"- **RAG Retrieval:** ChromaDB Vector Store (`top_k=5`, 500-char KB snippets, separated from prompt demonstrations)\n")
        f.write(f"- **Prompting Modes Evaluated:** {', '.join(f'`{m}`' for m in ordered_modes)}\n")
        f.write(f"- **Models Evaluated:** {len(by_model)} Models ({len(all_summaries)} total Model × Prompt runs)\n")
        f.write("- **Hardware Environment:** Intel Core Ultra 9 275HX, NVIDIA GeForce RTX 5080 Laptop GPU (16 GB VRAM)\n")
        f.write("- **Inference Platform:** Ollama (`num_ctx=8192`, `temperature=0.1`, `top_p=0.9`)\n\n")

        # SECTION 1: Model-by-Prompt Pivot Matrix
        f.write("## 1. Prompting Paradigm Comparison Matrix (Model × Prompt Mode)\n\n")
        f.write("Comparison of **Exact CWE Accuracy (Macro-F1)** and **Generation Speed (tok/s)** across prompting strategies:\n\n")
        header_cols = ["Model"] + [f"{m.upper()} Acc (Macro-F1)" for m in ordered_modes] + ["Best Mode", "Avg Speed (tok/s)"]
        f.write("| " + " | ".join(header_cols) + " |\n")
        f.write("| :--- | " + " | ".join([":---:"] * (len(header_cols) - 1)) + " |\n")

        for model_name in sorted(by_model.keys()):
            mode_dict = by_model[model_name]
            row_cells = [f"**{model_name}**"]
            best_mode = "-"
            best_acc = -1.0
            speeds = []
            for pm in ordered_modes:
                if pm in mode_dict:
                    s = mode_dict[pm]
                    acc_val = s["overall_accuracy"]
                    cell_str = f"{s['overall_accuracy_percent']} ({s.get('macro_f1_percent', '0%')})"
                    if acc_val > best_acc:
                        best_acc = acc_val
                        best_mode = f"`{pm}` ({s['overall_accuracy_percent']})"
                    speeds.append(s.get("tokens_per_sec", 0.0))
                    row_cells.append(cell_str)
                else:
                    row_cells.append("—")
            avg_spd = f"{(sum(speeds) / len(speeds)):.2f}" if speeds else "0.00"
            row_cells.append(best_mode)
            row_cells.append(avg_spd)
            f.write("| " + " | ".join(row_cells) + " |\n")

        # SECTION 2: Ranked Master Leaderboard
        f.write("\n## 2. Master Performance Leaderboard (All Model × Prompt Combinations)\n\n")
        f.write(
            "| Rank | Model | Prompt Mode | Exact CWE Acc | Macro-F1 | Binary F1 | Binary Prec / Rec | FPR | Py / JS / TS Acc | Avg Lat (P95) | Gen Speed (tok/s) | Prompt Speed (tok/s) | Avg Tokens (In/Out) | Fallback Rate |\n"
        )
        f.write(
            "| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n"
        )
        for rank_idx, s in enumerate(
            sorted(all_summaries, key=lambda x: (x["overall_accuracy"], x.get("macro_f1", 0)), reverse=True),
            1,
        ):
            f.write(
                f"| {rank_idx} | **{s['model']}** | `{s.get('prompt_mode', 'zero-shot')}` | "
                f"**{s['overall_accuracy_percent']}** | {s.get('macro_f1_percent', '0%')} | "
                f"{s.get('binary_f1_percent', 'N/A')} | {s.get('binary_precision_percent', 'N/A')} / {s.get('binary_recall_percent', 'N/A')} | "
                f"{s.get('false_positive_rate_percent', 'N/A')} | "
                f"{s['python_accuracy']} / {s['javascript_accuracy']} / {s['typescript_accuracy']} | "
                f"{s['avg_latency_sec']}s ({s.get('p95_latency_sec', 0)}s) | "
                f"**{s['tokens_per_sec']}** | {s.get('prompt_tokens_per_sec', 0)} | "
                f"{s.get('avg_prompt_tokens', 0)} / {s.get('avg_output_tokens', 0)} | "
                f"{s.get('parse_fallback_rate_percent', '0.00%')} |\n"
            )

        # SECTION 3: Per-Prompt-Mode Sub-Leaderboards
        f.write("\n## 3. Sub-Leaderboards by Prompting Paradigm\n\n")
        for pm in ordered_modes:
            mode_runs = [s for s in all_summaries if s.get("prompt_mode") == pm]
            if not mode_runs:
                continue
            f.write(f"### 3.{ordered_modes.index(pm) + 1} `{pm.upper()}` — {PROMPT_MODE_LABELS.get(pm, pm)}\n\n")
            f.write(
                "| Model | Exact CWE Acc | Macro-F1 | Binary F1 | Python Acc | JS Acc | TS Acc | Avg Latency (P95) | Gen Speed (tok/s) | Fallback Rate |\n"
            )
            f.write(
                "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n"
            )
            for s in sorted(mode_runs, key=lambda x: x["overall_accuracy"], reverse=True):
                f.write(
                    f"| **{s['model']}** | **{s['overall_accuracy_percent']}** | {s.get('macro_f1_percent', '0%')} | "
                    f"{s.get('binary_f1_percent', 'N/A')} | {s['python_accuracy']} | {s['javascript_accuracy']} | {s['typescript_accuracy']} | "
                    f"{s['avg_latency_sec']}s ({s.get('p95_latency_sec', 0)}s) | **{s['tokens_per_sec']}** | {s.get('parse_fallback_rate_percent', '0%')} |\n"
                )
            f.write("\n")

        # SECTION 4: Detailed Findings & Confusion Matrix Links
        f.write("## 4. Per-(Model, Prompt) Confusion Matrices & Diagnostic Findings\n\n")
        for summary in sorted(all_summaries, key=lambda x: x["overall_accuracy"], reverse=True):
            m_clean = clean_path_component(summary["model"])
            pm_clean = clean_path_component(summary.get("prompt_mode", "zero-shot"))
            image_rel = pathlib.Path("..") / "results" / m_clean / pm_clean / f"confusion_matrix_{m_clean}_{pm_clean}.png"
            f.write(f"### {summary['model']} — `{summary.get('prompt_mode', 'zero-shot').upper()}`\n\n")
            f.write(f"![{summary['model']} {pm_clean} confusion matrix]({image_rel.as_posix()})\n\n")
            f.write("\n".join(build_report_findings(summary)) + "\n\n")

    with open(csv_latest, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Model",
            "Prompt Mode",
            "Total Samples",
            "Correct Predictions",
            "Exact CWE Accuracy",
            "Macro-F1",
            "Binary Precision",
            "Binary Recall",
            "Binary F1",
            "Specificity",
            "False Positive Rate (FPR)",
            "Python Accuracy",
            "JavaScript Accuracy",
            "TypeScript Accuracy",
            "Avg Latency (s)",
            "P95 Latency (s)",
            "Output Gen Speed (tok/s)",
            "Prompt Eval Speed (tok/s)",
            "Avg Input Prompt Tokens",
            "Avg Output Tokens",
            "Strict JSON Rate",
            "Parse Fallback Rate",
        ])
        for s in sorted(all_summaries, key=lambda x: x["overall_accuracy"], reverse=True):
            writer.writerow([
                s["model"],
                s.get("prompt_mode", "zero-shot"),
                s["total_samples"],
                s["correct_predictions"],
                s["overall_accuracy_percent"],
                s.get("macro_f1_percent", "N/A"),
                s.get("binary_precision_percent", "N/A"),
                s.get("binary_recall_percent", "N/A"),
                s.get("binary_f1_percent", "N/A"),
                s.get("specificity_percent", "N/A"),
                s.get("false_positive_rate_percent", "N/A"),
                s["python_accuracy"],
                s["javascript_accuracy"],
                s["typescript_accuracy"],
                s["avg_latency_sec"],
                s.get("p95_latency_sec", 0),
                s["tokens_per_sec"],
                s.get("prompt_tokens_per_sec", 0),
                s.get("avg_prompt_tokens", 0),
                s.get("avg_output_tokens", 0),
                s.get("strict_json_rate_percent", "100.00%"),
                s.get("parse_fallback_rate_percent", "0.00%"),
            ])

    pivot_csv = reports_dir / "prompt_comparison_pivot_latest.csv"
    with open(pivot_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = ["Model"]
        for pm in ordered_modes:
            header.extend([f"{pm}_CWE_Acc", f"{pm}_Macro_F1", f"{pm}_Binary_F1", f"{pm}_Latency_s", f"{pm}_Tok_s"])
        writer.writerow(header)
        for model_name in sorted(by_model.keys()):
            row = [model_name]
            for pm in ordered_modes:
                s = by_model[model_name].get(pm)
                if s:
                    row.extend([
                        s["overall_accuracy_percent"],
                        s.get("macro_f1_percent", ""),
                        s.get("binary_f1_percent", ""),
                        s["avg_latency_sec"],
                        s["tokens_per_sec"],
                    ])
                else:
                    row.extend(["", "", "", "", ""])
            writer.writerow(row)

    print(f"📊 Master Markdown Report updated: {md_latest}")
    print(f"📊 Master CSV Leaderboard updated: {csv_latest}")
    print(f"📊 Prompt Comparison Pivot CSV updated: {pivot_csv}")


def resolve_prompt_modes(prompt_mode_args):
    """Expand '--prompt-mode all' or list of modes into ordered list of concrete modes."""
    expanded = []
    for m in prompt_mode_args:
        key = m.lower().strip()
        if key == "all":
            for cm in CORE_PROMPT_MODES:
                if cm not in expanded:
                    expanded.append(cm)
        elif key in VALID_PROMPT_ARG_CHOICES:
            if key not in expanded:
                expanded.append(key)
        else:
            raise ValueError(f"Invalid --prompt-mode '{m}'. Choose from {VALID_PROMPT_ARG_CHOICES}")
    return expanded


def main():
    parser = argparse.ArgumentParser(
        description="CodeDEE Full-Scale Master Evaluation Benchmark (RAG + Separate Zero-Shot, One-Shot, Few-Shot, and Chain-of-Thought Prompts)"
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=ALL_MODELS,
        help="List of Ollama models to run (default: all 13 models, or specify one/more)",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="v3",
        help="Dataset version to evaluate: 'v1' (1208 raw), 'v2' (928 <=4k), 'v3' (967 <=20k multifunc, default), 'v4' (1911 multifunc + safe patches), 'cyberseceval' (507 external), or a custom .jsonl path",
    )
    parser.add_argument(
        "--prompt-mode",
        nargs="+",
        default=["zero-shot"],
        choices=VALID_PROMPT_ARG_CHOICES,
        help="One or more prompting paradigms to evaluate, or 'all' to run [zero-shot, one-shot, few-shot, cot] sequentially per model.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of samples per model (default: None -> all samples in dataset)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Explicitly resume from existing checkpoint files without asking",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Force a brand new run, archiving any existing checkpoint files",
    )
    parser.add_argument(
        "--checkpoint-tag",
        type=str,
        default=None,
        help="Named tag/folder for checkpoints and output reports (e.g. --checkpoint-tag ablation_v4)",
    )
    parser.add_argument(
        "--top-k", type=int, default=5, help="Top-K rules retrieved from ChromaDB RAG"
    )
    parser.add_argument(
        "--no-kb-snippets",
        action="store_true",
        help="Optional: exclude reference flaw/remediation snippets inside the ChromaDB RAG block",
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=25,
        help="Save checkpoint every N samples",
    )

    args = parser.parse_args()
    active_modes = resolve_prompt_modes(args.prompt_mode)

    if args.checkpoint_tag:
        active_tag = args.checkpoint_tag
    elif len(active_modes) > 1:
        active_tag = f"{args.dataset}_multi_prompt_ablation"
    else:
        active_tag = f"{args.dataset}_{active_modes[0].replace('-', '_')}"

    print("==============================================================================")
    print("CodeDEE: Full-Scale Multi-Model × Multi-Prompt Evaluation Engine")
    print(f"Target Models ({len(args.models)}): {args.models}")
    print(f"Prompt Modes  ({len(active_modes)}): {active_modes} (RAG pulled separately)")
    print(f"Active Run Tag: {active_tag}")
    print("==============================================================================")

    collection = get_chroma_collection()
    samples, dataset_path = load_dataset(args.dataset)
    print(f"Active Dataset ({args.dataset}): {dataset_path.name}")

    if args.limit and args.limit < len(samples):
        samples = samples[: args.limit]
        print(f"⚠️ Limit applied: Running first {len(samples)} samples per (model, prompt_mode).")
    else:
        print(f"Loaded master evaluation dataset: {len(samples)} samples.")

    all_summaries = []
    # Model-First Loop: Keep model hot in GPU VRAM while cycling through all selected prompt modes!
    try:
        for model_idx, model_name in enumerate(args.models, 1):
            print(f"\n{'#' * 78}")
            print(f"🔥 MODEL [{model_idx}/{len(args.models)}]: {model_name} — Running {len(active_modes)} Prompt Mode(s): {active_modes}")
            print(f"{'#' * 78}")
            for prompt_mode in active_modes:
                try:
                    summary = evaluate_model_full_scale(
                        model_name=model_name,
                        samples=samples,
                        collection=collection,
                        prompt_mode=prompt_mode,
                        top_k=args.top_k,
                        include_kb_snippets=not args.no_kb_snippets,
                        save_interval=args.checkpoint_interval,
                        resume=args.resume,
                        fresh=args.fresh,
                        checkpoint_tag=active_tag,
                    )
                    all_summaries.append(summary)
                    export_reports(all_summaries, checkpoint_tag=active_tag, dataset_name=args.dataset)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(f"\n❌ Error during ({model_name}, {prompt_mode}): {e}")
    except KeyboardInterrupt:
        print(
            "\n⚠️ Process interrupted by user! All completed sample checkpoints and partial Master Reports are safely saved."
        )

    if all_summaries:
        export_reports(all_summaries, checkpoint_tag=active_tag, dataset_name=args.dataset)


if __name__ == "__main__":
    main()
