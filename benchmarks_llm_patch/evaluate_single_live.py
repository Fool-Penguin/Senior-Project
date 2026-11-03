"""
Live Interactive Benchmark Evaluator for Ollama Models (Component C7 & C8)
Queries a local Ollama model in real-time, displays:
  1. Starter Code (Before Fix)
  2. Full Prompt Sent
  3. Live Model Generated Output
  4. Ground Truth Reference Fix
  5. 4-Gate Verification Stack (CST Syntax, Interface, Taint Broken, Delta CC, Unit Test, CodeBLEU)

Usage:
  python benchmarks_llm_patch/evaluate_single_live.py [model_name] [cwe_id]
Example:
  python benchmarks_llm_patch/evaluate_single_live.py qwen2.5-coder:7b CWE-078
  python benchmarks_llm_patch/evaluate_single_live.py qwen2.5-coder:1.5b all
"""

import sys
import json
import time
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from benchmarks_llm_patch.test_cases.cwe_test_cases import TEST_CASES
from benchmarks_llm_patch.prompt_templates import SYSTEM_PROMPT, build_patch_prompt
from benchmarks_llm_patch.run_full_evaluation import evaluate_single_patch, extract_code_from_markdown


def query_ollama(model_name: str, prompt: str) -> dict:
    url = "http://localhost:11434/api/generate"
    payload = json.dumps({
        "model": model_name,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.95
        }
    }).encode("utf-8")

    start_time = time.time()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            elapsed = time.time() - start_time
            eval_count = data.get("eval_count", 0)
            eval_duration_ns = data.get("eval_duration", 0)
            tps = (eval_count / (eval_duration_ns / 1e9)) if eval_duration_ns > 0 else (eval_count / elapsed if elapsed > 0 else 0)
            return {
                "success": True,
                "text": data.get("response", ""),
                "latency_sec": round(elapsed, 2),
                "tokens_per_sec": round(tps, 1),
                "eval_tokens": eval_count
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "text": "",
            "latency_sec": 0,
            "tokens_per_sec": 0
        }


def run_case(model_name: str, cwe_id: str):
    if cwe_id not in TEST_CASES:
        print(f"[Error] Unknown test case: {cwe_id}. Available: {list(TEST_CASES.keys())}")
        return

    tc = TEST_CASES[cwe_id]
    prompt = build_patch_prompt(tc, fix_style="minimal")

    print("\n" + "=" * 80)
    print(f"EVALUATING TEST CASE: {cwe_id} ({tc['cwe_name']})")
    print(f"Target Model: {model_name} (Local Ollama)")
    print("=" * 80)

    # 1. Starter Code (Before Fix)
    print("\n" + "-" * 80)
    print("[1] STARTER CODE (VULNERABLE CODE BEFORE FIX):")
    print("-" * 80)
    for idx, line in enumerate(tc["code"].splitlines(), 1):
        print(f"  {idx:>2} | {line}")
    print(f"  Taint Source : {tc['taint_source']}")
    print(f"  Vulnerable Sink: {tc['taint_sink']}")

    # 2. Prompt Sent
    print("\n" + "-" * 80)
    print("[2] PROMPT SENT TO MODEL:")
    print("-" * 80)
    print(prompt)

    # 3. Live Model Query
    print("\n" + "-" * 80)
    print(f"[3] QUERYING {model_name} VIA OLLAMA...")
    print("-" * 80)
    res = query_ollama(model_name, prompt)
    if not res["success"]:
        print(f"  [Query Failed] Error: {res.get('error')}")
        return

    raw_output = res["text"]
    clean_patch = extract_code_from_markdown(raw_output)
    print(f"  Inference Latency: {res['latency_sec']}s | Speed: {res['tokens_per_sec']} tokens/s | Generated Tokens: {res['eval_tokens']}")
    print("\n  --- Raw Model Output ---")
    print(raw_output)

    # 4. Ground Truth Reference Fix
    print("\n" + "-" * 80)
    print("[4] GROUND TRUTH REFERENCE FIX (ORACLE FIX):")
    print("-" * 80)
    for idx, line in enumerate(tc["reference_fix"].splitlines(), 1):
        print(f"  {idx:>2} | {line}")

    # 5. Multi-Gate Verification
    print("\n" + "-" * 80)
    print("[5] MULTI-GATE VERIFICATION RESULTS (C8 ORACLE STACK):")
    print("-" * 80)
    eval_res = evaluate_single_patch(cwe_id, tc, clean_patch, model_name)

    print(f"  Gate 1 - Tree-sitter Syntax Validity : {'PASSED [OK]' if eval_res['syntax_valid'] else 'FAILED [X]'} ({eval_res['syntax_detail']})")
    print(f"  Gate 2 - Interface Signature Integrity : {'PASSED [OK]' if eval_res['interface_preserved'] else 'FAILED [X]'} ({eval_res['interface_detail']})")
    print(f"  Gate 3 - Taint Path Broken (Security) : {'PASSED [OK]' if eval_res['vulnerability_resolved'] else 'FAILED [X]'} ({eval_res['vulnerability_detail']})")
    print(f"  Gate 4 - Maintainability Delta (CC)   : {'PASSED [OK]' if eval_res['delta_cc'] <= 0 else 'WARNING'} (Delta CC: {eval_res['delta_cc']}, Before: {eval_res['cc_before']} -> After: {eval_res['cc_after']})")
    print(f"  Oracle - Pass@1 Unit Test Execution   : {'PASSED [OK]' if eval_res['unit_test_passed'] else 'FAILED [X]'} ({eval_res['unit_test_detail']})")
    print(f"  Oracle - Zero New Flaws (Bandit/SAST) : {'PASSED [OK]' if eval_res['zero_new_vulnerabilities'] else 'FAILED [X]'}")
    print(f"  Oracle - CodeBLEU vs Ground Truth     : {eval_res['codebleu']['codebleu']}%")

    overall = eval_res["overall_case_success"]
    print(f"\n  >> OVERALL CASE VERDICT: {'COMPOSITE SUCCESS [PASSED]' if overall else 'VERIFICATION FAILED [REJECTED]'}")


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5-coder:7b"
    target_cwe = sys.argv[2] if len(sys.argv) > 2 else "CWE-078"

    if target_cwe.lower() == "all":
        for cid in ["CWE-078", "CWE-089", "CWE-079", "CWE-022", "CWE-502"]:
            run_case(model, cid)
    else:
        run_case(model, target_cwe)


if __name__ == "__main__":
    main()
