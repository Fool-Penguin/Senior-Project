"""
CodeDEE - Local LLM Vulnerability Evaluation Module
Stage 3B: Guided Neuro-Symbolic Neural Oracle Benchmark

Evaluates Local LLM (via Ollama) on detecting CWE flaws in code:
- Input: Vulnerable source code + RAG Knowledge Base context
- Target Output Schema:
  {
    "cwe_id": "CWE-...",
    "reason": "Detailed chain-of-thought explanation of tainted dataflow",
    "confidence_score": 0.0 to 1.0,
    "risk_level": "Critical" | "High" | "Medium" | "Low"
  }
"""

import argparse
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).parent.parent
DATASET_PATH = ROOT / "datasets" / "combined" / "dataset.jsonl"
KB_PATH = ROOT / "datasets" / "combined" / "knowledge_base.jsonl"
BENCHMARK_OUT_DIR = ROOT / "benchmarks_llm_eval"
BENCHMARK_OUT_DIR.mkdir(parents=True, exist_ok=True)


SYSTEM_PROMPT = """You are an expert Static Application Security Testing (SAST) and Program Analysis Engine (CodeDEE Neural Oracle).
Your role is to analyze a given code snippet, trace tainted data flows from untrusted inputs (Sources) to sensitive operations (Sinks), and identify security vulnerabilities.

You MUST respond strictly with a valid JSON object matching the following schema without any conversational text or markdown code fences outside the JSON:

{
  "cwe_id": "<Predicted CWE ID, e.g. CWE-89, CWE-79, or CWE-NONE if benign>",
  "reason": "<Detailed technical explanation of the flaw: identify source, propagation, sink, and why sanitization is missing or flawed>",
  "confidence_score": <Float between 0.0 and 1.0 indicating your detection confidence>,
  "risk_level": "<Critical | High | Medium | Low | None>"
}
"""


def load_knowledge_base():
    """Load and index Knowledge Base by language."""
    kb_by_lang = defaultdict(list)
    with open(KB_PATH, "r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            kb_by_lang[entry["language"]].append(entry)
    return kb_by_lang


def build_rag_context(kb_entries, max_rules=12, include_few_shot=False):
    """
    Format RAG knowledge base catalogue into a concise context prompt.
    Includes vulnerability definition, known sources, sinks, and sanitizers.
    """
    context_lines = [
        "### Known Security Catalogue & Rules for this Language:"
    ]
    for k in kb_entries[:max_rules]:
        cid = k.get("catalogue_id", "")
        cwe = k.get("cwe_id", "")
        name = k.get("cwe_name", "")
        sources = k.get("source_pattern", "N/A")
        sinks = k.get("sink_pattern", "N/A")
        sanitizers = k.get("sanitizer_pattern", "N/A")

        rule_text = (
            f"- [{cid}] {cwe} ({name}):\n"
            f"  * Sources: {sources[:120]}\n"
            f"  * Sinks: {sinks[:120]}\n"
            f"  * Valid Sanitizers: {sanitizers[:120]}"
        )
        if include_few_shot and k.get("example_original_code"):
            ex_code = k.get("example_original_code")[:200]
            rule_text += f"\n  * Example Flaw: {ex_code}"
        context_lines.append(rule_text)

    return "\n".join(context_lines)


def build_evaluation_prompt(
    sample, kb_by_lang, use_rag=True, include_few_shot=False
):
    """Construct complete prompt for Ollama."""
    lang = sample.get("language", "python")
    code = sample.get("original_code", "")

    rag_block = ""
    if use_rag and lang in kb_by_lang:
        rag_block = build_rag_context(
            kb_by_lang[lang], max_rules=15, include_few_shot=include_few_shot
        )

    prompt = f"""{rag_block}

### Code to Inspect ({lang}):
```
{code}
```

Instructions:
1. Trace user-controlled inputs to sensitive execution sinks.
2. Determine if proper sanitization, parameterized queries, or encoding is present.
3. Return the JSON object with cwe_id, reason, confidence_score, and risk_level.
"""
    return prompt


def call_ollama(
    prompt,
    model="qwen2.5-coder:7b",
    system=SYSTEM_PROMPT,
    base_url="http://localhost:11434",
    timeout=60,
):
    """Call Ollama /api/generate endpoint."""
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1, "top_p": 0.9, "num_predict": 512},
    }
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
        return None, latency, str(e)


def extract_and_parse_json(raw_text):
    """Safely parse JSON response from LLM."""
    if not raw_text:
        return None
    raw_text = raw_text.strip()
    # Remove markdown code fences if present
    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```[a-zA-Z]*\n?", "", raw_text)
        raw_text = re.sub(r"\n?```$", "", raw_text)

    try:
        data = json.loads(raw_text)
        return {
            "cwe_id": str(data.get("cwe_id", "Unknown")).upper().strip(),
            "reason": str(data.get("reason", "")),
            "confidence_score": float(data.get("confidence_score", 0.0)),
            "risk_level": str(data.get("risk_level", "Unknown")).capitalize(),
        }
    except Exception:
        # Fallback regex extraction
        cwe_match = re.search(r"CWE-\d+", raw_text, re.IGNORECASE)
        cwe = cwe_match.group(0).upper() if cwe_match else "UNKNOWN"
        return {
            "cwe_id": cwe,
            "reason": raw_text[:300],
            "confidence_score": 0.5 if cwe != "UNKNOWN" else 0.0,
            "risk_level": "Unknown",
        }


def run_evaluation(
    model="qwen2.5-coder:7b",
    limit=5,
    lang_filter=None,
    use_rag=True,
    include_few_shot=False,
):
    """Run evaluation benchmark on sample dataset."""
    print(f"==================================================")
    print(f"CodeDEE LLM Vulnerability Evaluation Harness")
    print(f"Model: {model} | Use RAG: {use_rag} | Few-Shot: {include_few_shot}")
    print(f"==================================================")

    kb_by_lang = load_knowledge_base()

    # Load test dataset
    samples = []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        for line in f:
            s = json.loads(line)
            if lang_filter and s.get("language") != lang_filter:
                continue
            samples.append(s)

    if limit and limit < len(samples):
        samples = samples[:limit]

    print(f"Total test samples to evaluate: {len(samples)}")

    results = []
    correct_cwe = 0

    for idx, s in enumerate(samples, 1):
        sid = s.get("sample_id")
        lang = s.get("language")
        true_cwe = s.get("cwe_id")

        print(
            f"[{idx}/{len(samples)}] Evaluating {sid} ({lang}) - Ground Truth: {true_cwe}..."
        )
        prompt = build_evaluation_prompt(
            s, kb_by_lang, use_rag=use_rag, include_few_shot=include_few_shot
        )

        resp, latency, err = call_ollama(prompt, model=model)
        if err:
            print(f"  ❌ Ollama Error: {err}")
            results.append(
                {
                    "sample_id": sid,
                    "language": lang,
                    "ground_truth_cwe": true_cwe,
                    "error": err,
                    "latency": latency,
                }
            )
            continue

        raw_output = resp.get("response", "")
        parsed = extract_and_parse_json(raw_output)

        is_match = parsed["cwe_id"] == true_cwe
        if is_match:
            correct_cwe += 1
            print(
                f"  ✅ MATCH: {parsed['cwe_id']} | Conf: {parsed['confidence_score']:.2f} | Risk: {parsed['risk_level']} | Latency: {latency:.2f}s"
            )
        else:
            print(
                f"  ⚠️ MISMATCH: Pred {parsed['cwe_id']} vs True {true_cwe} | Conf: {parsed['confidence_score']:.2f} | Risk: {parsed['risk_level']} | Latency: {latency:.2f}s"
            )

        results.append(
            {
                "sample_id": sid,
                "language": lang,
                "ground_truth_cwe": true_cwe,
                "predicted_cwe": parsed["cwe_id"],
                "reason": parsed["reason"],
                "confidence_score": parsed["confidence_score"],
                "risk_level": parsed["risk_level"],
                "is_correct": is_match,
                "latency_sec": latency,
                "tokens_eval": resp.get("eval_count", 0),
            }
        )

    # Save results
    timestamp = int(time.time())
    out_file = (
        BENCHMARK_OUT_DIR
        / f"eval_results_{model.replace(':', '_')}_{timestamp}.json"
    )
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "model": model,
                "use_rag": use_rag,
                "include_few_shot": include_few_shot,
                "total_evaluated": len(samples),
                "accuracy": (correct_cwe / len(samples)) if samples else 0.0,
                "results": results,
            },
            f,
            indent=2,
        )

    print(f"\nBenchmark finished! Accuracy: {correct_cwe}/{len(samples)}")
    print(f"Results saved to: {out_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="CodeDEE Local LLM Evaluation Harness"
    )
    parser.add_argument(
        "--model", default="qwen2.5-coder:7b", help="Ollama model name"
    )
    parser.add_argument(
        "--limit", type=int, default=10, help="Number of samples to evaluate"
    )
    parser.add_argument(
        "--lang", default=None, help="Filter language: python, javascript, etc."
    )
    parser.add_argument(
        "--no-rag",
        action="store_true",
        help="Disable RAG knowledge base injection",
    )
    parser.add_argument(
        "--few-shot",
        action="store_true",
        help="Include few-shot code pairs from KB",
    )
    args = parser.parse_args()

    run_evaluation(
        model=args.model,
        limit=args.limit,
        lang_filter=args.lang,
        use_rag=not args.no_rag,
        include_few_shot=args.few_shot,
    )

