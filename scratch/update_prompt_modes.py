"""
Script to update scripts/run_full_scale_benchmark.py to support:
--prompt-mode {zero-shot,zero-shot-rag,one-shot,few-shot,cot}
"""
import pathlib

ROOT = pathlib.Path(__file__).parent.parent
script_path = ROOT / "scripts" / "run_full_scale_benchmark.py"

new_script = '''"""
CodeDEE - Full-Scale Master Evaluation Benchmark Runner
Supports 5 Prompting Paradigms for Preliminary Work & Ablation Studies:
  - zero-shot      : Pure LLM (No ChromaDB RAG, No code examples)
  - zero-shot-rag  : ChromaDB RAG rules (Sources/Sinks/Sanitizers) without code examples
  - one-shot       : ChromaDB RAG rules + Top-1 Flawed/Fixed Code Example Pair (k=1)
  - few-shot       : ChromaDB RAG rules + Top-K Flawed/Fixed Code Example Pairs (k=3, default)
  - cot            : Structured 4-Step Chain-of-Thought (Source -> Propagation -> Sanitizer -> Verdict) + Few-Shot RAG

========================================================================================
HOW TO RUN THE SCRIPT (CLI USAGE EXAMPLES):
========================================================================================

1. Run a specific Prompting Paradigm (Zero-Shot, One-Shot, Few-Shot, Chain-of-Thought):
   python scripts/run_full_scale_benchmark.py --prompt-mode zero-shot --dataset v4 --checkpoint-tag run_zeroshot_v4
   python scripts/run_full_scale_benchmark.py --prompt-mode zero-shot-rag --dataset v4 --checkpoint-tag run_zeroshot_rag_v4
   python scripts/run_full_scale_benchmark.py --prompt-mode one-shot --dataset v4 --checkpoint-tag run_oneshot_v4
   python scripts/run_full_scale_benchmark.py --prompt-mode few-shot --dataset v4 --checkpoint-tag run_fewshot_v4
   python scripts/run_full_scale_benchmark.py --prompt-mode cot --dataset v4 --checkpoint-tag run_cot_v4

2. Run all models on a specific number of samples (e.g. 50 samples):
   python scripts/run_full_scale_benchmark.py --prompt-mode cot --limit 50

3. Run a single specific model on all samples:
   python scripts/run_full_scale_benchmark.py --models qwen2.5-coder:7b --prompt-mode cot

----------------------------------------------------------------------------------------
CHECKPOINT CONTROL OPTIONS:
----------------------------------------------------------------------------------------
- Resume from previous checkpoint (if exists):
   python scripts/run_full_scale_benchmark.py --checkpoint-tag run_cot_v4 --resume

- Force a fresh run (ignores existing checkpoint):
   python scripts/run_full_scale_benchmark.py --checkpoint-tag run_cot_v4 --fresh
========================================================================================
"""

import argparse
import csv
import json
import os
import pathlib
import re
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
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).parent.parent
COMBINED_DIR = ROOT / "datasets" / "combined"
DATASET_PATH = COMBINED_DIR / "dataset.jsonl"

# Explicit Dataset Versions
DATASET_VERSIONS = {
    "v1": COMBINED_DIR / "dataset_v1_raw_unfiltered_1208.jsonl",
    "v2": COMBINED_DIR / "dataset_v2_filtered_30to4000_vuln_only_928.jsonl",
    "v3": COMBINED_DIR / "dataset_v3_multifunc_30to20000_vuln_only_967.jsonl",
    "v4": COMBINED_DIR / "dataset_v4_multifunc_with_safe_patches_1911.jsonl",
    "cyberseceval": COMBINED_DIR / "dataset_cyberseceval_external_507.jsonl",
}

PROMPT_MODES = [
    "zero-shot",
    "zero-shot-rag",
    "one-shot",
    "few-shot",
    "cot",
]

CHROMA_DIR = ROOT / "data" / "chromadb_kb"
BENCHMARK_FULL_DIR = ROOT / "benchmarks_full_scale"
BENCHMARK_FULL_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR = BENCHMARK_FULL_DIR / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)

# Default Target Models (including specialized cybersecurity & reasoning models)
ALL_MODELS = [
    "qwen2.5:1.5b",
    "qwen2.5-coder:1.5b",
    "qwen2.5-coder:7b",
    "deepseek-coder:6.7b",
    "codellama:7b",
    "llama3.1:8b",
    "hf.co/fdtn-ai/Foundation-Sec-8B-Instruct-Q8_0-GGUF:Q8_0",
    "hf.co/fdtn-ai/Foundation-Sec-8B-Reasoning-Q8_0-GGUF:Q8_0",
    "deepseek-r1:8b",
    "deepseek-r1:14b",
    "qwen2.5-coder:14b",
    "gpt-oss:20b",
    "qwen2.5-coder:32b",
]

# Official 28 Taxonomy CWE list for pure zero-shot reference
OFFICIAL_TAXONOMY_CWES = (
    "CWE-20, CWE-22, CWE-77, CWE-78, CWE-79, CWE-89, CWE-94, CWE-116, "
    "CWE-200, CWE-285, CWE-287, CWE-306, CWE-312, CWE-319, CWE-327, "
    "CWE-330, CWE-347, CWE-352, CWE-400, CWE-502, CWE-601, CWE-611, "
    "CWE-798, CWE-862, CWE-918, CWE-1321, CWE-1333, CWE-1427, or CWE-NONE (if safe)"
)

SYSTEM_PROMPT = """You are an expert Static Application Security Testing (SAST) and Program Analysis Engine (CodeDEE Neural Oracle).
Your role is to analyze a given code snippet, trace tainted data flows from untrusted inputs (Sources) to sensitive operations (Sinks), and determine if a security vulnerability is present.

### Analysis Guidelines:
1. Treat all function parameters, method arguments, and external data as UNTRUSTED caller-controlled inputs (potential taint sources) unless they are strictly hardcoded constants.
2. Trace dataflow from these parameters to sensitive execution sinks (e.g. SQL execution, shell command execution, HTML rendering/interpolation, file path access, regex compilation, code evaluation).
3. Check if adequate sanitization, escaping, or defensive validation is applied to neutralize the sink.
4. Vulnerability Classification:
   - If an unmitigated vulnerability exists: Set "vulnerability_detected": true, identify the exact catalogued "cwe_id" (e.g. CWE-89, CWE-79, CWE-78, CWE-22, etc.), and calibrate "confidence_score" and "risk_level".
5. Safe-code classification:
   - Use "CWE-NONE" only when careful source-to-sink analysis finds no exploitable vulnerability because the code is safe, properly sanitized, or has no relevant security-sensitive behavior.
   - Never use "CWE-NONE" merely because the exact CWE is uncertain. If a vulnerability is present, choose the closest applicable CWE and explain the evidence and uncertainty.
   - When using "CWE-NONE", set "vulnerability_detected" to false, "risk_level" to "None", and explain why no source reaches a vulnerable sink.
6. Technical Reason: In "reason", provide a concise technical explanation tracing [Source Parameter] -> [Propagation] -> [Sink], explaining why defense is missing or flawed, or why the code is safe. Use single quotes for code names inside JSON (e.g. item['field']).
7. Strict Constraint: Do NOT generate code patches or code blocks. Your role is strictly detection and technical analysis.

You MUST respond strictly with a valid JSON object matching the following schema without any conversational text or markdown code fences outside the JSON:

{
  "cwe_id": "<Predicted CWE ID, e.g. CWE-89, CWE-79, or CWE-NONE>",
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
- Step 1 (source_identification): Identify all untrusted entry points, function parameters, request objects, or external inputs entering the scope.
- Step 2 (sink_and_propagation_trace): Trace how data flows from those sources through variable assignments or helper calls into sensitive execution sinks (e.g., SQL queries, OS commands, DOM/HTML rendering, filesystem paths, network requests, eval/deserialization).
- Step 3 (sanitizer_and_guard_audit): Evaluate whether any type-checking, allowlisting, parameterization, or context-specific escaping neutralizes the taint along the path.
- Step 4 (cwe_derivation_verdict): Synthesize Steps 1-3 to determine whether an exploitable vulnerability exists or if the code is safe ("CWE-NONE"), and map the flaw to the exact CWE ID.

### Strict Output Schema:
You MUST respond strictly with a valid JSON object matching the schema below (place "cot_steps" FIRST so your reasoning precedes classification):

{
  "cot_steps": {
    "step1_sources": "<Identify untrusted parameters/inputs>",
    "step2_propagation_and_sinks": "<Trace data flow to sensitive execution sinks>",
    "step3_sanitizer_audit": "<Analyze whether existing validation/escaping is sufficient or bypassed>",
    "step4_verdict_derivation": "<Conclude exact CWE ID or CWE-NONE based on Steps 1-3>"
  },
  "cwe_id": "<Predicted CWE ID, e.g. CWE-89, CWE-79, or CWE-NONE>",
  "vulnerability_detected": <true | false>,
  "confidence_score": <Float between 0.0 and 1.0>,
  "risk_level": "<Critical | High | Medium | Low | None>",
  "reason": "<Concise summary of the Chain-of-Thought audit>"
}
"""

SYSTEM_PROMPT_FORCED_CWE = """You are an expert Static Application Security Testing (SAST) and Program Analysis Engine (CodeDEE Neural Oracle).
Your role is to analyze a given code snippet, trace tainted data flows from untrusted inputs to sensitive execution sinks, and classify the primary security vulnerability present.

### STRICT RULES & CONSTRAINTS:
1. Every code sample provided contains a real security weakness. You MUST identify the specific CWE ID.
2. Under NO circumstances should you output "CWE-NONE", "NONE", "UNKNOWN", or "SAFE". You MUST pick the most applicable catalogued CWE ID (e.g. CWE-79, CWE-89, CWE-78, CWE-22, CWE-918, CWE-1321, CWE-502, CWE-94, etc.).
3. Treat all function arguments, parameters, and external inputs as UNTRUSTED caller data (taint sources).
4. Always set "vulnerability_detected": true.
5. In "reason", explain why this specific CWE applies to the source->sink execution path.

You MUST respond strictly with a valid JSON object matching the following schema without any conversational text or markdown code fences outside the JSON:

{
  "cwe_id": "<Exact catalogued CWE ID, e.g. CWE-89, CWE-79, CWE-78, CWE-22 - NEVER CWE-NONE>",
  "vulnerability_detected": true,
  "confidence_score": <Float between 0.0 and 1.0 indicating your detection confidence>,
  "risk_level": "<Critical | High | Medium | Low>",
  "reason": "<Technical explanation of the tainted flow and why this CWE is the most applicable>"
}
"""


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


def retrieve_rag_context(
    collection, code, language, top_k=3, max_examples=3
):
    """
    Retrieve top-k relevant security catalogue entries for language.
    max_examples controls how many rules include concrete code demonstrations:
      - max_examples = 0 -> Zero-Shot RAG (Rule metadata only, no code examples)
      - max_examples = 1 -> One-Shot (Only the #1 closest rule includes Flawed/Safe example pair)
      - max_examples = k -> Few-Shot (All top-k rules include Flawed/Safe example pairs)
    """
    lang = language.lower()
    lines = code.splitlines()
    meaningful_lines = [l for l in lines if not l.strip().startswith(('import ', 'from ', '#', '//', '/*'))]
    query_text = "\\n".join(meaningful_lines)[:2000] if meaningful_lines else code[:2000]

    try:
        results = collection.query(
            query_texts=[query_text],
            where={"language": lang},
            n_results=top_k,
            include=["metadatas", "documents", "distances"],
        )
    except Exception:
        results = collection.query(
            query_texts=[query_text],
            n_results=top_k,
            include=["metadatas", "documents", "distances"],
        )

    context_lines = [f"### Relevant Security Catalogue & Rules ({lang}):"]
    metadatas = results["metadatas"][0] if results.get("metadatas") else []
    examples_added = 0

    for m in metadatas:
        cid = m.get("catalogue_id", "")
        cwe = m.get("cwe_id", "")
        name = m.get("cwe_name", "")
        sources = m.get("sources", "N/A")
        sinks = m.get("sinks", "N/A")
        sanitizers = m.get("sanitizers", "N/A")

        rule_block = (
            f"- [{cid}] {cwe} ({name}):\\n"
            f"  * Sources: {sources}\\n"
            f"  * Sinks: {sinks}\\n"
            f"  * Valid Sanitizers: {sanitizers}"
        )
        if examples_added < max_examples and m.get("has_example"):
            orig_ex = m.get("example_original_code", "").strip()[:250]
            fixed_ex = m.get("example_fixed_code", "").strip()[:250]
            if orig_ex or fixed_ex:
                if orig_ex:
                    rule_block += f"\\n  * Flawed Code Example:\\n```\\n{orig_ex}\\n```"
                if fixed_ex:
                    rule_block += f"\\n  * Safe/Fixed Example:\\n```\\n{fixed_ex}\\n```"
                examples_added += 1

        context_lines.append(rule_block)

    return "\\n\\n".join(context_lines)


def build_prompt(
    sample,
    collection,
    prompt_mode="few-shot",
    top_k=3,
    force_cwe=False,
):
    """
    Construct prompt according to the selected prompting paradigm:
      - zero-shot      : Pure LLM (No RAG rules, no examples; only target code + CWE taxonomy list)
      - zero-shot-rag  : RAG rules (Sources/Sinks/Sanitizers) with 0 code examples
      - one-shot       : RAG rules + exactly 1 Flawed/Fixed code example pair (from rank-1 match)
      - few-shot       : RAG rules + top_k (3) Flawed/Fixed code example pairs
      - cot            : Structured 4-step Chain-of-Thought instructions + Few-Shot RAG context
    """
    lang = sample.get("language", "python")
    code = sample.get("original_code", "")
    mode = prompt_mode.lower().strip()

    if mode == "zero-shot":
        rag_block = (
            f"### Target Security Taxonomy Scope ({lang}):\\n"
            f"Evaluate the code against the 28 official CodeDEE web vulnerability CWEs: "
            f"{OFFICIAL_TAXONOMY_CWES}."
        )
    elif mode == "zero-shot-rag":
        rag_block = retrieve_rag_context(
            collection=collection, code=code, language=lang, top_k=top_k, max_examples=0
        )
    elif mode == "one-shot":
        rag_block = retrieve_rag_context(
            collection=collection, code=code, language=lang, top_k=top_k, max_examples=1
        )
    elif mode in ("few-shot", "cot"):
        rag_block = retrieve_rag_context(
            collection=collection, code=code, language=lang, top_k=top_k, max_examples=top_k
        )
    else:
        raise ValueError(f"Unsupported prompt_mode: {prompt_mode}")

    if force_cwe:
        instructions = """Instructions:
1. Every code sample provided is KNOWN to contain a real vulnerability.
2. You MUST identify the single most applicable CWE ID (e.g. CWE-79, CWE-89, CWE-78, CWE-22, CWE-918, CWE-1321, CWE-502, CWE-94, etc.).
3. You are STRICTLY FORBIDDEN from answering "CWE-NONE", "NONE", or "UNKNOWN". You MUST predict a concrete CWE.
4. Treat function arguments and parameters as untrusted caller inputs (potential taint sources).
5. Always set vulnerability_detected to true.
6. Do NOT generate code patches or fix implementations.
7. Return strictly the JSON object specifying cwe_id, vulnerability_detected, confidence_score, risk_level, and reason."""
    elif mode == "cot":
        instructions = """Instructions (Chain-of-Thought Reasoning Mode):
1. Perform a structured 4-step security audit in "cot_steps" BEFORE outputting your final classification:
   - Step 1 (step1_sources): List all untrusted function parameters, user inputs, or external data sources.
   - Step 2 (step2_propagation_and_sinks): Trace how tainted variables propagate to sensitive execution sinks.
   - Step 3 (step3_sanitizer_audit): Verify whether proper sanitization, parameterization, escaping, or allowlisting is present and effective.
   - Step 4 (step4_verdict_derivation): Deduce the exact CWE ID if an unmitigated flaw exists, or "CWE-NONE" if the code is safe/sanitized.
2. Based on Step 4, populate cwe_id, vulnerability_detected, confidence_score, risk_level, and reason.
3. Do NOT generate code patches or fix implementations.
4. Return strictly the valid JSON object matching the Chain-of-Thought schema."""
    else:
        instructions = """Instructions:
1. Treat function arguments and parameters as untrusted caller inputs (potential taint sources).
2. Trace if any untrusted arguments reach sensitive execution sinks without proper validation or sanitization.
3. If an unmitigated vulnerability exists, specify the exact CWE ID (e.g. CWE-79, CWE-89, CWE-78) and set vulnerability_detected to true.
4. Use "CWE-NONE" only if source-to-sink analysis shows that the code is genuinely safe or has no relevant vulnerable sink. Do not use it as an uncertainty or fallback label. If a vulnerability exists, select the closest applicable CWE even when confidence is imperfect.
5. If using "CWE-NONE", set vulnerability_detected to false and risk_level to "None". Otherwise set vulnerability_detected to true and provide a concrete CWE.
6. Do NOT generate code patches or fix implementations.
7. Return strictly the JSON object specifying cwe_id, vulnerability_detected, confidence_score, risk_level, and reason."""

    prompt = f"""{rag_block}

### Code to Inspect ({lang}):
```{lang}
{code}
```

{instructions}
"""
    return prompt


def call_ollama_with_retry(
    prompt,
    model,
    system=SYSTEM_PROMPT,
    base_url="http://localhost:11434",
    timeout=180,
    max_retries=3,
):
    """Call Ollama with retry for large models or occasional timeouts."""
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1, "top_p": 0.9, "num_predict": 1024, "num_ctx": 8192},
    }
    data = json.dumps(payload).encode("utf-8")

    for attempt in range(1, max_retries + 1):
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
    default_res = {
        "cwe_id": "UNKNOWN",
        "vulnerability_detected": False,
        "confidence_score": 0.0,
        "risk_level": "Unknown",
        "reason": "",
        "cot_steps": None,
    }
    if not raw_text:
        return default_res

    text = raw_text.strip()
    # Strip <think>...</think> blocks emitted by reasoning models (e.g. DeepSeek-R1, Foundation-Sec-Reasoning)
    text = re.sub(r"<think>[\\s\\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\\n?", "", text)
        text = re.sub(r"\\n?```$", "", text)

    def normalize_cwe_label(value):
        label = str(value).upper().strip()
        if label in {"NONE", "CWE-NONE", "CWE_NONE", "SAFE"}:
            return "CWE-NONE"
        return label

    def extract_fields(data):
        cwe_raw = normalize_cwe_label(
            data.get("cwe_id") or data.get("confirmed_cwe") or "UNKNOWN"
        )
        vuln_detected = bool(
            data.get("vulnerability_detected", cwe_raw not in ["CWE-NONE", "UNKNOWN"])
        )
        if cwe_raw == "CWE-NONE":
            vuln_detected = False
        cot_steps = data.get("cot_steps")
        reason = str(data.get("reason", ""))
        if not reason and isinstance(cot_steps, dict):
            reason = " | ".join(f"{k}: {v}" for k, v in cot_steps.items() if v)
        return {
            "cwe_id": cwe_raw,
            "vulnerability_detected": vuln_detected,
            "confidence_score": float(data.get("confidence_score", 0.0)),
            "risk_level": str(data.get("risk_level", "Unknown")).capitalize(),
            "reason": reason,
            "cot_steps": cot_steps if isinstance(cot_steps, dict) else None,
        }

    # First attempt: standard JSON parsing
    try:
        data = json.loads(text)
        return extract_fields(data)
    except Exception:
        pass

    # Second attempt: Extract outermost JSON {...} block via regex
    json_block = re.search(r"\\{[\\s\\S]*\\}", text)
    if json_block:
        try:
            data = json.loads(json_block.group(0))
            return extract_fields(data)
        except Exception:
            pass

    # Fallback attempt: regex search for CWE identifier
    cwe_match = re.search(r"CWE-\\d+", text, re.IGNORECASE)
    cwe = normalize_cwe_label(cwe_match.group(0) if cwe_match else "UNKNOWN")
    return {
        "cwe_id": cwe,
        "vulnerability_detected": cwe not in ["UNKNOWN", "CWE-NONE", "NONE"],
        "confidence_score": 0.5 if cwe != "UNKNOWN" else 0.0,
        "risk_level": "Unknown",
        "reason": text[:250],
        "cot_steps": None,
    }


def clean_path_component(value):
    """Make a user-provided model or run name safe for use as a path component."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value)).strip("_")
    return cleaned or "default"


def get_run_dir(tag=None):
    """Return the stable output directory for a tagged benchmark run."""
    return RUNS_DIR / clean_path_component(tag or "default")


def get_checkpoint_path(model_name, tag=None):
    clean_name = clean_path_component(model_name)
    checkpoint_dir = get_run_dir(tag) / "checkpoints" / clean_name
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    return checkpoint_dir / "checkpoint.json"


def load_checkpoint(model_name, tag=None):
    cp_path = get_checkpoint_path(model_name, tag)
    if cp_path.exists():
        try:
            with open(cp_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("completed_results", {}), cp_path
        except Exception:
            return {}, cp_path
    return {}, cp_path


def save_checkpoint(model_name, completed_results, tag=None, prompt_mode="few-shot"):
    cp_path = get_checkpoint_path(model_name, tag)
    with open(cp_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "model": model_name,
                "tag": tag or "default",
                "prompt_mode": prompt_mode,
                "timestamp": int(time.time()),
                "total_completed": len(completed_results),
                "completed_results": completed_results,
            },
            f,
            indent=2,
        )


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
    """Export one model's confusion matrix as JSON, CSV, and PNG."""
    model_name = clean_path_component(summary["model"])
    confusion_matrix = summary["confusion_matrix"]
    json_path = output_dir / f"confusion_matrix_{model_name}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "model": summary["model"],
                "prompt_mode": summary.get("prompt_mode", "few-shot"),
                "checkpoint_tag": summary["checkpoint_tag"],
                **confusion_matrix,
            },
            f,
            indent=2,
        )

    csv_path = output_dir / f"confusion_matrix_{model_name}.csv"
    labels = confusion_matrix["labels"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["True CWE"] + labels)
        for true_label in labels:
            writer.writerow(
                [true_label]
                + [confusion_matrix["matrix"][true_label][predicted_label] for predicted_label in labels]
            )

    image_path = output_dir / f"confusion_matrix_{model_name}.png"
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "Confusion-matrix images require matplotlib. Install it with "
            "`python -m pip install matplotlib`."
        ) from exc

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
        title=f"CWE Confusion Matrix - {summary['model']} ({summary.get('prompt_mode', 'few-shot')})",
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
    return json_path, csv_path, image_path


def build_report_findings(summary):
    """Create concise, report-ready findings from one model's predictions."""
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
        f"- **Prompting Mode:** `{summary.get('prompt_mode', 'few-shot')}`",
        f"- **Accuracy:** {summary['overall_accuracy_percent']} "
        f"({summary['correct_predictions']}/{summary['total_samples']}).",
        f"- **CWE-NONE predictions:** {none_predictions}/{len(results)} ({none_rate:.2f}%).",
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


def evaluate_model_full_scale(
    model_name,
    samples,
    collection,
    prompt_mode="few-shot",
    top_k=3,
    save_interval=20,
    resume=False,
    fresh=False,
    checkpoint_tag=None,
    force_cwe=False,
):
    print(f"\\n{'=' * 70}")
    print(f"🚀 INITIATING FULL-SCALE BENCHMARK: {model_name}")
    print(
        f"Total Samples: {len(samples)} | Prompt Mode: {prompt_mode.upper()} | Top-K RAG: {top_k if prompt_mode != 'zero-shot' else 0}"
    )
    if checkpoint_tag:
        print(f"🏷️ Checkpoint Tag: {checkpoint_tag}")
    print(f"{'=' * 70}")

    completed_map = {}
    cp_path = get_checkpoint_path(model_name, checkpoint_tag)

    if fresh:
        print(f"✨ Fresh run forced (--fresh). Ignoring any existing checkpoint at {cp_path.name}.")
    elif resume:
        completed_map, _ = load_checkpoint(model_name, checkpoint_tag)
        if completed_map:
            print(f"🔄 Resuming from checkpoint ({cp_path.name}): {len(completed_map)} samples already evaluated.")
        else:
            print(f"ℹ️ No existing checkpoint found at {cp_path.name}. Starting fresh.")
    else:
        existing, _ = load_checkpoint(model_name, checkpoint_tag)
        if existing:
            sample_ids_set = {s.get("sample_id") for s in samples}
            evaluated_ids_set = set(existing.keys())
            overlap = evaluated_ids_set.intersection(sample_ids_set)

            print(f"\\n{'!' * 70}")
            print(f"⚠️ Existing checkpoint found: {cp_path.name}")
            print(f"   Saved samples in checkpoint: {len(existing)}")
            print(f"   Current dataset samples to run: {len(samples)} (Overlap: {len(overlap)})")
            print(f"{'!' * 70}")

            prompt_msg = (
                f"How would you like to handle checkpoint for '{model_name}'?\\n"
                f"  [1] Start FRESH run (New checkpoint, ignore old data) [Default]\\n"
                f"  [2] RESUME from existing checkpoint\\n"
                f"Select [1/2] (Default 1): "
            )

            choice = "1"
            if sys.stdin.isatty():
                try:
                    user_input = input(prompt_msg).strip()
                    if user_input in ["2", "resume", "r", "y", "yes"]:
                        choice = "2"
                except Exception:
                    choice = "1"
            else:
                print("ℹ️ Non-interactive terminal: Defaulting to FRESH run [1]. (Pass --resume explicitly to resume)")

            if choice == "2":
                completed_map = existing
                print(f"🔄 Resumed {len(completed_map)} samples from {cp_path.name}.")
            else:
                completed_map = {}
                print(f"✨ Starting brand new evaluation (old checkpoint will be archived on save).")
                backup_old = cp_path.with_name(f"{cp_path.stem}_archived_{int(time.time())}.json")
                try:
                    import shutil
                    shutil.copy2(cp_path, backup_old)
                    print(f"📦 Archived old checkpoint to {backup_old.name}")
                except Exception:
                    pass

    results = list(completed_map.values())
    correct_count = sum(1 for r in results if r.get("is_correct"))
    total_latency = sum(r.get("latency_sec", 0.0) for r in results)
    total_tokens = sum(r.get("tokens_generated", 0) for r in results)

    start_run_time = time.time()

    if force_cwe:
        active_system = SYSTEM_PROMPT_FORCED_CWE
    elif prompt_mode.lower() == "cot":
        active_system = SYSTEM_PROMPT_COT
    else:
        active_system = SYSTEM_PROMPT

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
            force_cwe=force_cwe,
        )

        resp, latency, err = call_ollama_with_retry(prompt, model=model_name, system=active_system)
        total_latency += latency

        if err:
            print(
                f"[{idx}/{len(samples)}] {sid} ({lang}) -> ❌ Error: {err} ({latency:.2f}s)"
            )
            item = {
                "sample_id": sid,
                "language": lang,
                "prompt_mode": prompt_mode,
                "true_cwe": true_cwe,
                "predicted_cwe": "ERROR",
                "is_correct": False,
                "confidence_score": 0.0,
                "risk_level": "Unknown",
                "reason": err,
                "cot_steps": None,
                "latency_sec": latency,
                "tokens_generated": 0,
            }
        else:
            raw_text = resp.get("response", "")
            parsed = parse_llm_json(raw_text)
            tokens = resp.get("eval_count", 0)
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
                "confidence_score": parsed["confidence_score"],
                "risk_level": parsed["risk_level"],
                "reason": parsed["reason"],
                "cot_steps": parsed.get("cot_steps"),
                "latency_sec": latency,
                "tokens_generated": tokens,
            }

            print(
                f"[{idx}/{len(samples)}] {sid} ({lang} | Mode: {prompt_mode} | True: {true_cwe}) -> {status} | Latency: {latency:.2f}s"
            )

        completed_map[sid] = item
        results.append(item)

        if len(completed_map) % save_interval == 0 or idx == len(samples):
            save_checkpoint(model_name, completed_map, tag=checkpoint_tag, prompt_mode=prompt_mode)

    elapsed_time = time.time() - start_run_time
    accuracy = (correct_count / len(samples)) if samples else 0.0
    avg_latency = (total_latency / len(samples)) if samples else 0.0
    tokens_per_sec = (total_tokens / total_latency) if total_latency > 0 else 0.0

    # Binary metrics (True Positive, False Positive, True Negative, False Negative) for V4 / mixed datasets
    tp = sum(1 for r in results if r["true_cwe"] != "CWE-NONE" and r.get("predicted_cwe") not in ("CWE-NONE", "UNKNOWN", "ERROR"))
    fn = sum(1 for r in results if r["true_cwe"] != "CWE-NONE" and r.get("predicted_cwe") in ("CWE-NONE", "UNKNOWN", "ERROR"))
    tn = sum(1 for r in results if r["true_cwe"] == "CWE-NONE" and r.get("predicted_cwe") == "CWE-NONE")
    fp = sum(1 for r in results if r["true_cwe"] == "CWE-NONE" and r.get("predicted_cwe") != "CWE-NONE")

    binary_precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    binary_recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    binary_f1 = (
        (2 * binary_precision * binary_recall / (binary_precision + binary_recall))
        if (binary_precision + binary_recall) > 0
        else 0.0
    )

    lang_stats = defaultdict(lambda: {"total": 0, "correct": 0})
    for r in results:
        l = r["language"]
        lang_stats[l]["total"] += 1
        if r.get("is_correct"):
            lang_stats[l]["correct"] += 1

    summary = {
        "model": model_name,
        "prompt_mode": prompt_mode,
        "checkpoint_tag": checkpoint_tag or "default",
        "total_samples": len(samples),
        "correct_predictions": correct_count,
        "overall_accuracy": round(accuracy, 4),
        "overall_accuracy_percent": f"{accuracy * 100:.2f}%",
        "binary_precision_percent": f"{binary_precision * 100:.2f}%",
        "binary_recall_percent": f"{binary_recall * 100:.2f}%",
        "binary_f1_percent": f"{binary_f1 * 100:.2f}%",
        "avg_latency_sec": round(avg_latency, 2),
        "total_elapsed_sec": round(elapsed_time, 2),
        "tokens_per_sec": round(tokens_per_sec, 2),
        "python_accuracy": f"{(lang_stats['python']['correct'] / lang_stats['python']['total'] * 100):.2f}%"
        if lang_stats["python"]["total"]
        else "0%",
        "javascript_accuracy": f"{(lang_stats['javascript']['correct'] / lang_stats['javascript']['total'] * 100):.2f}%"
        if lang_stats["javascript"]["total"]
        else "0%",
        "typescript_accuracy": f"{(lang_stats['typescript']['correct'] / lang_stats['typescript']['total'] * 100):.2f}%"
        if lang_stats["typescript"]["total"]
        else "0%",
        "results": results,
    }

    summary["confusion_matrix"] = build_confusion_matrix(results)

    clean_name = clean_path_component(model_name)
    run_dir = get_run_dir(checkpoint_tag)
    results_dir = run_dir / "results" / clean_name
    results_dir.mkdir(parents=True, exist_ok=True)
    final_model_path = results_dir / f"full_eval_{clean_name}.json"
    with open(final_model_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    confusion_json_path, confusion_csv_path, confusion_image_path = export_confusion_matrix(
        summary, results_dir
    )

    print(f"\\n🎯 Model {model_name} ({prompt_mode}) Completed!")
    print(
        f"Exact CWE Accuracy: {summary['overall_accuracy_percent']} ({correct_count}/{len(samples)}) | Binary F1: {summary['binary_f1_percent']} | Avg Latency: {avg_latency:.2f}s"
    )
    print(f"Results saved to: {final_model_path}")
    return summary


def export_reports(all_summaries, checkpoint_tag=None):
    """Export comparative CSV and Markdown reports for advisor / thesis."""
    timestamp = int(time.time())
    reports_dir = get_run_dir(checkpoint_tag) / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    prompt_mode = all_summaries[0].get("prompt_mode", "few-shot")

    md_path = reports_dir / f"master_benchmark_report_{timestamp}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# CodeDEE: Full-Scale Vulnerability Detection Benchmark\\n\\n")
        f.write(
            f"- **Dataset Scale:** Cleaned & Normalized Dataset ({all_summaries[0]['total_samples']} Samples)\\n"
        )
        f.write(
            f"- **Prompting Paradigm:** `{prompt_mode.upper()}`\\n"
        )
        f.write(
            f"- **Hardware Environment:** Intel Core Ultra 9 275HX, NVIDIA RTX 5080 Laptop GPU (16 GB VRAM)\\n"
        )
        f.write(f"- **Inference Platform:** Ollama (Windows 11 Enterprise x64, num_ctx=8192)\\n\\n")

        f.write("## 🏆 Overall Performance Leaderboard\\n\\n")
        f.write(
            "| Model Name | Prompt Mode | Exact CWE Acc | Binary F1 | Python Acc | JS Acc | TS Acc | Avg Latency (s) | Speed (tok/s) |\\n"
        )
        f.write(
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\\n"
        )
        for s in sorted(
            all_summaries, key=lambda x: x["overall_accuracy"], reverse=True
        ):
            f.write(
                f"| **{s['model']}** | `{s.get('prompt_mode', 'few-shot')}` | **{s['overall_accuracy_percent']}** | {s.get('binary_f1_percent', 'N/A')} | {s['python_accuracy']} | {s['javascript_accuracy']} | {s['typescript_accuracy']} | {s['avg_latency_sec']}s | {s['tokens_per_sec']} |\\n"
            )

        f.write("\\n## Confusion Matrices and Findings\\n\\n")
        for summary in sorted(all_summaries, key=lambda x: x["overall_accuracy"], reverse=True):
            model_name = clean_path_component(summary["model"])
            image_path = pathlib.Path("..") / "results" / model_name / f"confusion_matrix_{model_name}.png"
            f.write(f"### {summary['model']} ({summary.get('prompt_mode', 'few-shot')})\\n\\n")
            f.write(f"![{summary['model']} confusion matrix]({image_path.as_posix()})\\n\\n")
            f.write("\\n".join(build_report_findings(summary)) + "\\n\\n")

    csv_path = reports_dir / f"master_benchmark_report_{timestamp}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Model",
                "Prompt Mode",
                "Total Samples",
                "Correct",
                "Overall Accuracy",
                "Binary Precision",
                "Binary Recall",
                "Binary F1",
                "Python Accuracy",
                "JavaScript Accuracy",
                "TypeScript Accuracy",
                "Avg Latency (s)",
                "Tokens Per Sec",
            ]
        )
        for s in sorted(
            all_summaries, key=lambda x: x["overall_accuracy"], reverse=True
        ):
            writer.writerow(
                [
                    s["model"],
                    s.get("prompt_mode", "few-shot"),
                    s["total_samples"],
                    s["correct_predictions"],
                    s["overall_accuracy_percent"],
                    s.get("binary_precision_percent", "N/A"),
                    s.get("binary_recall_percent", "N/A"),
                    s.get("binary_f1_percent", "N/A"),
                    s["python_accuracy"],
                    s["javascript_accuracy"],
                    s["typescript_accuracy"],
                    s["avg_latency_sec"],
                    s["tokens_per_sec"],
                ]
            )

    print(f"\\nMaster Markdown Report: {md_path}")
    print(f"Master CSV Report: {csv_path}")


def main():
    parser = argparse.ArgumentParser(
        description="CodeDEE Full-Scale Master Evaluation Benchmark (Supports Zero-Shot, One-Shot, Few-Shot, and Chain-of-Thought)"
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
        type=str,
        choices=PROMPT_MODES,
        default="few-shot",
        help="Prompting paradigm: 'zero-shot' (no RAG, no examples), 'zero-shot-rag' (RAG rules only, 0 examples), 'one-shot' (RAG + 1 example pair), 'few-shot' (RAG + 3 example pairs, default), 'cot' (4-step Chain-of-Thought + Few-Shot RAG)",
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
        help="Explicitly resume from existing checkpoint file without asking",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Force a brand new run, ignoring any existing checkpoint files",
    )
    parser.add_argument(
        "--checkpoint-tag",
        type=str,
        default=None,
        help="Named tag/prefix for checkpoint and output files (e.g. --checkpoint-tag run_cot_v4)",
    )
    parser.add_argument(
        "--force-cwe",
        action="store_true",
        help="Experimental only: forbid CWE-NONE/UNKNOWN and force a concrete CWE prediction",
    )
    parser.add_argument(
        "--top-k", type=int, default=3, help="Top-K rules retrieved from ChromaDB"
    )
    parser.add_argument(
        "--no-few-shot",
        action="store_true",
        help="Legacy flag: equivalent to --prompt-mode zero-shot-rag",
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=25,
        help="Save checkpoint every N samples",
    )

    args = parser.parse_args()

    # Handle legacy --no-few-shot flag gracefully
    active_prompt_mode = args.prompt_mode
    if args.no_few_shot and active_prompt_mode == "few-shot":
        active_prompt_mode = "zero-shot-rag"

    # Auto-assign a descriptive checkpoint tag if none given so different prompt modes don't collide
    active_tag = args.checkpoint_tag or f"{args.dataset}_{active_prompt_mode.replace('-', '_')}"

    print("==================================================")
    print("CodeDEE: Full-Scale Master Evaluation Engine")
    print(f"Target Models ({len(args.models)}): {args.models}")
    print(f"Prompting Paradigm: {active_prompt_mode.upper()}")
    print(f"Active Checkpoint Tag: {active_tag}")
    print("==================================================")

    collection = get_chroma_collection() if active_prompt_mode != "zero-shot" else None
    samples, dataset_path = load_dataset(args.dataset)
    print(f"Active Dataset ({args.dataset}): {dataset_path.name}")

    if args.limit and args.limit < len(samples):
        samples = samples[: args.limit]
        print(f"⚠️ Limit applied: Running first {len(samples)} samples.")
    else:
        print(f"Loaded master evaluation dataset: {len(samples)} samples.")

    all_summaries = []
    for model_name in args.models:
        try:
            summary = evaluate_model_full_scale(
                model_name=model_name,
                samples=samples,
                collection=collection,
                prompt_mode=active_prompt_mode,
                top_k=args.top_k,
                save_interval=args.checkpoint_interval,
                resume=args.resume,
                fresh=args.fresh,
                checkpoint_tag=active_tag,
                force_cwe=args.force_cwe,
            )
            all_summaries.append(summary)
        except KeyboardInterrupt:
            print(
                f"\\n⚠️ Process interrupted by user while testing {model_name}. Checkpoints are safely saved!"
            )
            break
        except Exception as e:
            print(f"\\n❌ Error during model {model_name}: {e}")

    if all_summaries:
        export_reports(all_summaries, checkpoint_tag=active_tag)


if __name__ == "__main__":
    main()
'''

with open(script_path, "w", encoding="utf-8") as f:
    f.write(new_script)

print(f"Updated {script_path} successfully.")
