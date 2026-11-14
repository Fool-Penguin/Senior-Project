"""
CodeDEE - Multi-Model Vulnerability Evaluation Harness using ChromaDB RAG
Evaluates Ollama models on detecting code vulnerabilities using the cleaned dataset.

========================================================================================
HOW TO RUN THE SCRIPT (CLI USAGE EXAMPLES):
========================================================================================

1. Run all models on all samples:
   python scripts/evaluate_all_models_chromadb.py --full

2. Run all models on specific number of samples (e.g. 30 samples):
   python scripts/evaluate_all_models_chromadb.py --limit 30

3. Run a single specific model on all samples:
   python scripts/evaluate_all_models_chromadb.py --models qwen2.5-coder:7b --full

4. Run a single specific model on specific number of samples (e.g. 15 samples):
   python scripts/evaluate_all_models_chromadb.py --models qwen2.5-coder:7b --limit 15

(Stratified Mode by default):
   python scripts/evaluate_all_models_chromadb.py --samples-per-lang 8
========================================================================================

Uses ChromaDB vector search (language-filtered, top-k=3) with few-shot code pairs.
Outputs accuracy, latency, and comprehensive JSON benchmark logs.
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

# Ensure UTF-8 console output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import chromadb
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

ROOT = pathlib.Path(__file__).parent.parent
DATASET_PATH = ROOT / "datasets" / "combined" / "dataset.jsonl"
CHROMA_DIR = ROOT / "data" / "chromadb_kb"
BENCHMARK_DIR = ROOT / "benchmarks_llm_eval"
BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

TARGET_MODELS = [
    "qwen2.5:1.5b",
    "qwen2.5-coder:1.5b",
    "qwen2.5-coder:7b",
    "deepseek-coder:6.7b",
    "codellama:7b",
    "llama3.1:8b",
    "qwen2.5-coder:14b",
    "gpt-oss:20b",
    "qwen2.5-coder:32b",
]

SYSTEM_PROMPT = """You are an expert Static Application Security Testing (SAST) and Program Analysis Engine (CodeDEE Neural Oracle).
Your role is to analyze a given code snippet, trace tainted data flows from untrusted inputs (Sources) to sensitive operations (Sinks), and determine if a security vulnerability is present.

### Analysis Guidelines:
1. Treat all function parameters, method arguments, and external data as UNTRUSTED caller-controlled inputs (potential taint sources) unless they are strictly hardcoded constants.
2. Trace dataflow from these parameters to sensitive execution sinks (e.g. SQL execution, shell command execution, HTML rendering/interpolation, file path access, regex compilation, code evaluation).
3. Check if adequate sanitization, escaping, or defensive validation is applied to neutralize the sink.
4. Vulnerability Classification:
   - If an unmitigated vulnerability exists: Set "vulnerability_detected": true, identify the exact catalogued "cwe_id" (e.g. CWE-89, CWE-79, CWE-78, CWE-22, etc.), and calibrate "confidence_score" and "risk_level".
   - If code is safe, properly sanitized, or benign: Set "vulnerability_detected": false, "cwe_id": "CWE-NONE", "risk_level": "None".
5. Technical Reason: In "reason", provide a concise technical explanation tracing [Source Parameter] -> [Propagation] -> [Sink], explaining why defense is missing or flawed. Use single quotes for code names inside JSON (e.g. item['field']).
6. Strict Constraint: Do NOT generate code patches or code blocks. Your role is strictly detection and technical analysis.

You MUST respond strictly with a valid JSON object matching the following schema without any conversational text or markdown code fences outside the JSON:

{
  "cwe_id": "<Predicted CWE ID, e.g. CWE-89, CWE-79, or CWE-NONE if benign>",
  "vulnerability_detected": <true | false>,
  "confidence_score": <Float between 0.0 and 1.0 indicating your detection confidence>,
  "risk_level": "<Critical | High | Medium | Low | None>",
  "reason": "<Detailed technical explanation: identify source parameter, propagation, sink, and why sanitization is missing or flawed>"
}
"""


def get_chroma_collection():
    """Load or initialize ChromaDB collection."""
    if not CHROMA_DIR.exists():
        print("ChromaDB not found. Building now...")
        import build_chromadb_kb
        build_chromadb_kb.build_knowledge_base_vector_store()

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    embedding_fn = ONNXMiniLM_L6_V2()
    collection = client.get_collection(
        name="codedee_knowledge_base", embedding_function=embedding_fn
    )
    return collection


def retrieve_rag_context(
    collection, code, language, top_k=3, include_few_shot=True
):
    """Filtered Similarity Search."""
    lang = language.lower()
    lines = code.splitlines()
    meaningful_lines = [l for l in lines if not l.strip().startswith(('import ', 'from ', '#', '//', '/*'))]
    query_text = "\n".join(meaningful_lines)[:2000] if meaningful_lines else code[:2000]

    try:
        results = collection.query(
            query_texts=[query_text],
            where={"language": lang},
            n_results=top_k,
            include=["metadatas", "documents", "distances"],
        )
    except Exception as e:
        results = collection.query(
            query_texts=[query_text],
            n_results=top_k,
            include=["metadatas", "documents", "distances"],
        )

    context_lines = [f"### Relevant Security Catalogue & Rules ({lang}):"]
    metadatas = results["metadatas"][0] if results.get("metadatas") else []
    for m in metadatas:
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

        if include_few_shot and m.get("has_example"):
            orig_ex = m.get("example_original_code", "").strip()[:250]
            fixed_ex = m.get("example_fixed_code", "").strip()[:250]
            if orig_ex:
                rule_block += f"\n  * Flawed Code Example:\n```\n{orig_ex}\n```"
            if fixed_ex:
                rule_block += f"\n  * Safe/Fixed Example:\n```\n{fixed_ex}\n```"

        context_lines.append(rule_block)

    return "\n\n".join(context_lines)


def build_prompt(
    sample, collection, top_k=3, use_rag=True, include_few_shot=True
):
    """Assemble final prompt for the LLM."""
    lang = sample.get("language", "python")
    code = sample.get("original_code", "")

    rag_block = ""
    if use_rag and collection:
        rag_block = retrieve_rag_context(
            collection=collection,
            code=code,
            language=lang,
            top_k=top_k,
            include_few_shot=include_few_shot,
        )

    prompt = f"""{rag_block}

### Code to Inspect ({lang}):
```{lang}
{code}
```

Instructions:
1. Treat function arguments and parameters as untrusted caller inputs (potential taint sources).
2. Trace if any untrusted arguments reach sensitive execution sinks without proper validation or sanitization.
3. If an unmitigated vulnerability exists, specify the exact CWE ID (e.g. CWE-79, CWE-89, CWE-78) and set vulnerability_detected to true.
4. If the code is properly sanitized, safe, or benign, set cwe_id to "CWE-NONE", vulnerability_detected to false, and risk_level to "None".
5. Do NOT generate code patches or fix implementations.
6. Return strictly the JSON object specifying cwe_id, vulnerability_detected, confidence_score, risk_level, and reason.
"""
    return prompt


def call_ollama(
    prompt,
    model,
    system=SYSTEM_PROMPT,
    base_url="http://localhost:11434",
    timeout=180,
):
    """Call Ollama API with 1024 token budget."""
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1, "top_p": 0.9, "num_predict": 1024},
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


def parse_llm_json(raw_text):
    """Parse output into required schema."""
    default_res = {
        "cwe_id": "UNKNOWN",
        "vulnerability_detected": False,
        "confidence_score": 0.0,
        "risk_level": "Unknown",
        "reason": "",
    }
    if not raw_text:
        return default_res

    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

    # First attempt: direct json load
    try:
        data = json.loads(text)
        cwe_raw = str(data.get("cwe_id") or data.get("confirmed_cwe") or "UNKNOWN").upper().strip()
        vuln_detected = bool(data.get("vulnerability_detected", cwe_raw not in ["CWE-NONE", "NONE", "UNKNOWN"]))
        return {
            "cwe_id": cwe_raw,
            "vulnerability_detected": vuln_detected,
            "confidence_score": float(data.get("confidence_score", 0.0)),
            "risk_level": str(data.get("risk_level", "Unknown")).capitalize(),
            "reason": str(data.get("reason", "")),
        }
    except Exception:
        pass

    # Second attempt: outermost json block
    json_block = re.search(r"\{[\s\S]*\}", text)
    if json_block:
        try:
            data = json.loads(json_block.group(0))
            cwe_raw = str(data.get("cwe_id") or data.get("confirmed_cwe") or "UNKNOWN").upper().strip()
            vuln_detected = bool(data.get("vulnerability_detected", cwe_raw not in ["CWE-NONE", "NONE", "UNKNOWN"]))
            return {
                "cwe_id": cwe_raw,
                "vulnerability_detected": vuln_detected,
                "confidence_score": float(data.get("confidence_score", 0.0)),
                "risk_level": str(data.get("risk_level", "Unknown")).capitalize(),
                "reason": str(data.get("reason", "")),
            }
        except Exception:
            pass

    # Fallback regex
    cwe_match = re.search(r"CWE-\d+", text, re.IGNORECASE)
    cwe = cwe_match.group(0).upper() if cwe_match else "UNKNOWN"
    return {
        "cwe_id": cwe,
        "vulnerability_detected": cwe not in ["UNKNOWN", "CWE-NONE", "NONE"],
        "confidence_score": 0.5 if cwe != "UNKNOWN" else 0.0,
        "risk_level": "Unknown",
        "reason": text[:250],
    }


def load_dataset_samples(limit=None, full=False, samples_per_lang=8):
    """Load evaluation samples from dataset.jsonl with flexible scoping."""
    all_samples = []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                all_samples.append(json.loads(line))

    if limit is not None and limit > 0:
        return all_samples[:limit], all_samples

    if full:
        return all_samples, all_samples

    # Stratified mode
    stratified = defaultdict(lambda: defaultdict(list))
    for s in all_samples:
        stratified[s["language"]][s["cwe_id"]].append(s)

    selected = []
    for lang in ["python", "javascript", "typescript"]:
        cwes = list(stratified[lang].keys())
        count = 0
        for cwe in cwes:
            selected.append(stratified[lang][cwe][0])
            count += 1
            if count >= samples_per_lang:
                break

    return selected, all_samples


def evaluate_model(
    model_name,
    samples,
    collection,
    use_rag=True,
    include_few_shot=True,
    top_k=3,
):
    """Evaluate a single model on the given dataset samples."""
    print(f"\n==================================================")
    print(f"🚀 Benchmarking Model: {model_name}")
    print(
        f"Samples: {len(samples)} | ChromaDB RAG: {use_rag} | Few-Shot: {include_few_shot}"
    )
    print(f"==================================================")

    results = []
    correct_count = 0
    total_latency = 0.0
    total_tokens = 0

    for i, s in enumerate(samples, 1):
        sid = s.get("sample_id")
        lang = s.get("language")
        true_cwe = s.get("cwe_id")

        prompt = build_prompt(
            sample=s,
            collection=collection,
            top_k=top_k,
            use_rag=use_rag,
            include_few_shot=include_few_shot,
        )

        resp, latency, err = call_ollama(prompt, model=model_name)
        total_latency += latency

        if err:
            print(
                f"  [{i}/{len(samples)}] {sid} ({lang}) -> ❌ Error: {err} ({latency:.2f}s)"
            )
            results.append(
                {
                    "sample_id": sid,
                    "language": lang,
                    "true_cwe": true_cwe,
                    "error": err,
                    "latency": latency,
                }
            )
            continue

        raw_resp = resp.get("response", "")
        parsed = parse_llm_json(raw_resp)
        tokens = resp.get("eval_count", 0)
        total_tokens += tokens

        is_match = parsed["cwe_id"] == true_cwe
        if is_match:
            correct_count += 1
            status = "✅ MATCH"
        else:
            status = f"⚠️ MISMATCH (Pred: {parsed['cwe_id']})"

        print(
            f"  [{i}/{len(samples)}] {sid} ({lang} | True: {true_cwe}) -> {status} | Conf: {parsed['confidence_score']:.2f} | Risk: {parsed['risk_level']} | Latency: {latency:.2f}s"
        )

        results.append(
            {
                "sample_id": sid,
                "language": lang,
                "true_cwe": true_cwe,
                "predicted_cwe": parsed["cwe_id"],
                "is_correct": is_match,
                "vulnerability_detected": parsed["vulnerability_detected"],
                "confidence_score": parsed["confidence_score"],
                "risk_level": parsed["risk_level"],
                "reason": parsed["reason"],
                "latency_sec": latency,
                "tokens_generated": tokens,
            }
        )

    accuracy = (correct_count / len(samples)) if samples else 0.0
    avg_latency = (total_latency / len(samples)) if samples else 0.0
    tok_per_sec = (total_tokens / total_latency) if total_latency > 0 else 0.0

    summary = {
        "model": model_name,
        "total_samples": len(samples),
        "correct_predictions": correct_count,
        "accuracy": round(accuracy, 4),
        "accuracy_percent": f"{accuracy * 100:.1f}%",
        "avg_latency_sec": round(avg_latency, 2),
        "tokens_per_sec": round(tok_per_sec, 2),
        "use_rag": use_rag,
        "include_few_shot": include_few_shot,
        "timestamp": int(time.time()),
        "results": results,
    }
    return summary


def main():
    parser = argparse.ArgumentParser(
        description="CodeDEE Multi-Model Vulnerability Evaluation Harness with ChromaDB"
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=None,
        help="Specify models to benchmark. Default: all 9 target models",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run on all samples in cleaned dataset (928 samples)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Run on exact first N samples (e.g. --limit 50)",
    )
    parser.add_argument(
        "--samples-per-lang",
        type=int,
        default=8,
        help="Samples per language in stratified mode (default 8 -> 24 total)",
    )
    parser.add_argument(
        "--no-rag",
        action="store_true",
        help="Disable ChromaDB RAG context retrieval",
    )
    parser.add_argument(
        "--no-few-shot",
        action="store_true",
        help="Exclude few-shot code pairs from RAG context",
    )
    parser.add_argument(
        "--top-k", type=int, default=3, help="Top-K rules to retrieve from RAG"
    )

    args = parser.parse_args()

    # Load ChromaDB Collection
    collection = None
    if not args.no_rag:
        print("Connecting to ChromaDB knowledge base...")
        collection = get_chroma_collection()

    eval_samples, all_samples = load_dataset_samples(
        limit=args.limit,
        full=args.full,
        samples_per_lang=args.samples_per_lang,
    )
    print(
        f"Benchmark dataset loaded: {len(eval_samples)} samples (Total available: {len(all_samples)})"
    )

    models_to_test = args.models if args.models else TARGET_MODELS
    print(f"Target Models to Evaluate ({len(models_to_test)}): {models_to_test}")

    all_model_summaries = []

    for model in models_to_test:
        summary = evaluate_model(
            model_name=model,
            samples=eval_samples,
            collection=collection,
            use_rag=not args.no_rag,
            include_few_shot=not args.no_few_shot,
            top_k=args.top_k,
        )
        all_model_summaries.append(summary)

        # Save individual model result
        sanitized_name = model.replace(":", "_").replace(".", "_")
        out_path = (
            BENCHMARK_DIR
            / f"benchmark_{sanitized_name}_{int(time.time())}.json"
        )
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

    # Save comparative master report
    master_report = {
        "benchmark_timestamp": int(time.time()),
        "total_models": len(models_to_test),
        "sample_count": len(eval_samples),
        "is_full_dataset": args.full or (args.limit and args.limit >= len(all_samples)),
        "leaderboard": [
            {
                "model": s["model"],
                "accuracy": s["accuracy_percent"],
                "correct": f"{s['correct_predictions']}/{s['total_samples']}",
                "avg_latency": f"{s['avg_latency_sec']}s",
                "tok_per_sec": s["tokens_per_sec"],
            }
            for s in sorted(
                all_model_summaries, key=lambda x: x["accuracy"], reverse=True
            )
        ],
        "detailed_summaries": all_model_summaries,
    }

    master_path = (
        BENCHMARK_DIR
        / f"master_benchmark_comparison_{int(time.time())}.json"
    )
    with open(master_path, "w", encoding="utf-8") as f:
        json.dump(master_report, f, indent=2)

    # Print Final Leaderboard
    print("\n" + "=" * 65)
    print("🏆 FINAL BENCHMARK LEADERBOARD (CWE Detection Performance)")
    print("=" * 65)
    print(
        f"{'Model Name':<25} | {'Accuracy':<10} | {'Score':<8} | {'Avg Latency':<12} | {'Speed'}"
    )
    print("-" * 65)
    for row in master_report["leaderboard"]:
        print(
            f"{row['model']:<25} | {row['accuracy']:<10} | {row['correct']:<8} | {row['avg_latency']:<12} | {row['tok_per_sec']} t/s"
        )
    print("=" * 65)
    print(f"Master comparative report saved to: {master_path}")


if __name__ == "__main__":
    main()
