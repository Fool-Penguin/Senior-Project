# -*- coding: utf-8 -*-
"""
CodeDEE: Public Benchmark Evaluator for Local LLMs
Uses the Official OpenAI HumanEval Dataset (164 standardized coding tasks).
100% Public Data, Zero Synthetic / Generated Code.
"""

import os
import sys

# Force UTF-8 encoding on Windows terminal
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except:
        pass

import json
import time
import gzip
import urllib.request
import re
import subprocess
import tempfile
from pathlib import Path

OLLAMA_API_URL = "http://localhost:11434/api/generate"
HUMANEVAL_URL = "https://github.com/openai/human-eval/raw/master/data/HumanEval.jsonl.gz"
CACHE_DIR = Path("datasets/original")
CACHE_FILE = CACHE_DIR / "HumanEval.jsonl"


def ensure_humaneval_dataset():
    """Downloads official OpenAI HumanEval dataset if not already cached."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    
    print(f"[*] Downloading official OpenAI HumanEval dataset from {HUMANEVAL_URL}...", flush=True)
    req = urllib.request.Request(HUMANEVAL_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        decompressed = gzip.decompress(resp.read()).decode("utf-8")
    
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        f.write(decompressed)
    
    tasks = [json.loads(line) for line in decompressed.strip().split("\n") if line.strip()]
    print(f"[+] Download complete: {len(tasks)} official coding tasks cached at {CACHE_FILE}", flush=True)
    return tasks


def query_ollama(model_name: str, prompt: str, timeout: int = 45):
    """Sends prompt to local Ollama instance and returns generated code + speed metrics."""
    req_body = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,  # Greedy decoding for deterministic benchmark evaluation
            "num_predict": 512,
        }
    }
    req = urllib.request.Request(
        OLLAMA_API_URL,
        data=json.dumps(req_body).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            elapsed = time.perf_counter() - t0
            raw_response = data.get("response", "")
            eval_count = data.get("eval_count", 0)
            eval_duration_ns = data.get("eval_duration", 1)
            tokens_per_sec = (eval_count / (eval_duration_ns / 1e9)) if eval_duration_ns > 0 else 0.0
            return {
                "success": True,
                "response": raw_response,
                "elapsed_sec": round(elapsed, 3),
                "eval_count": eval_count,
                "tokens_per_sec": round(tokens_per_sec, 1)
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "elapsed_sec": round(time.perf_counter() - t0, 3),
            "eval_count": 0,
            "tokens_per_sec": 0.0
        }


def extract_code(raw_response: str, prompt: str) -> str:
    """Extracts clean python function body from LLM output."""
    match = re.search(r"```(?:python)?\s*(.*?)\s*```", raw_response, re.DOTALL)
    if match:
        code = match.group(1).strip()
    else:
        code = raw_response.strip()
    
    if prompt.strip() in code:
        return code
    return prompt + "\n" + code


def run_unit_test(full_code: str, test_code: str, entry_point: str, timeout_sec: int = 5):
    """Executes generated code against official OpenAI test assertions in an isolated subprocess."""
    combined_script = f"""{full_code}

{test_code}

check({entry_point})
"""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
        tmp.write(combined_script)
        tmp_path = tmp.name
    
    try:
        proc = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout_sec
        )
        if proc.returncode == 0:
            return {"passed": True, "error": None}
        else:
            err = proc.stderr.strip().split("\n")[-1] if proc.stderr else "Runtime assertion failed"
            return {"passed": False, "error": err}
    except subprocess.TimeoutExpired:
        return {"passed": False, "error": "Execution timed out (Infinite Loop)"}
    except Exception as e:
        return {"passed": False, "error": str(e)}
    finally:
        try:
            os.remove(tmp_path)
        except:
            pass


def evaluate_model(model_name: str, tasks: list, limit: int = 10):
    """Evaluates a model across a slice of official tasks."""
    print(f"\n=======================================================", flush=True)
    print(f" BENCHMARKING: {model_name} on OpenAI HumanEval", flush=True)
    print(f" Official Public Tasks: {limit} problems (Greedy decoding T=0.0)", flush=True)
    print(f"=======================================================", flush=True)
    
    passed_count = 0
    total_speed = 0.0
    results = []
    
    for i, task in enumerate(tasks[:limit]):
        task_id = task["task_id"]
        prompt = task["prompt"]
        test = task["test"]
        entry_point = task["entry_point"]
        
        instruct_prompt = f"""Complete the following Python function. Return ONLY the completed Python function inside a ```python ... ``` block.

{prompt}
"""
        res = query_ollama(model_name, instruct_prompt)
        if not res["success"]:
            print(f"  [{i+1}/{limit}] {task_id:15} | [ERROR] OLLAMA: {res.get('error')}", flush=True)
            continue
        
        code = extract_code(res["response"], prompt)
        test_res = run_unit_test(code, test, entry_point)
        
        if test_res["passed"]:
            passed_count += 1
            status_str = "[PASS]"
        else:
            status_str = f"[FAIL] ({test_res['error'][:30]})"
            
        speed = res["tokens_per_sec"]
        total_speed += speed
        print(f"  [{i+1}/{limit}] {task_id:15} | {status_str:35} | {speed:6.1f} t/s | {res['elapsed_sec']:4.2f}s", flush=True)
        
        results.append({
            "task_id": task_id,
            "passed": test_res["passed"],
            "error": test_res["error"],
            "tokens_per_sec": speed,
            "elapsed_sec": res["elapsed_sec"]
        })
    
    pass_rate = (passed_count / limit) * 100.0 if limit > 0 else 0.0
    avg_speed = total_speed / limit if limit > 0 else 0.0
    avg_latency = sum(r["elapsed_sec"] for r in results) / limit if limit > 0 else 0.0
    print(f"-------------------------------------------------------", flush=True)
    print(f" SUMMARY for {model_name}:", flush=True)
    print(f"   Pass@1 Score: {pass_rate:.1f}% ({passed_count}/{limit})", flush=True)
    print(f"   Avg Speed:    {avg_speed:.1f} tokens/second", flush=True)
    print(f"   Avg Latency:  {avg_latency:.2f} seconds/task", flush=True)
    print(f"=======================================================\n", flush=True)
    return {
        "model": model_name,
        "pass_rate": pass_rate,
        "passed_count": passed_count,
        "total_evaluated": limit,
        "avg_speed": avg_speed,
        "avg_latency": avg_latency,
        "details": results
    }


def main():
    tasks = ensure_humaneval_dataset()
    
    all_known_models = [
        "qwen2.5-coder:7b",
        "qwen2.5-coder:1.5b",
        "deepseek-coder:6.7b",
        "codellama:7b",
        "llama3.1:8b",
        "gpt-oss:20b"
    ]
    
    target_models = list(all_known_models)
    is_single_model = False
    
    if len(sys.argv) > 1 and sys.argv[1] != "all":
        target_models = [sys.argv[1]]
        is_single_model = True
    
    num_tasks = 10
    if len(sys.argv) > 2:
        try:
            num_tasks = int(sys.argv[2])
        except:
            pass
            
    summary_table = []
    for model in target_models:
        res = evaluate_model(model, tasks, limit=num_tasks)
        summary_table.append(res)
        
    # Model hardware metadata
    param_map = {
        "qwen2.5-coder:7b": "7.6B",
        "qwen2.5-coder:1.5b": "1.5B",
        "deepseek-coder:6.7b": "6.7B",
        "codellama:7b": "7.0B",
        "llama3.1:8b": "8.0B",
        "gpt-oss:20b": "20.0B"
    }

    results_dir = Path("benchmarks_llm_patch/results")
    results_dir.mkdir(parents=True, exist_ok=True)
    md_file = results_dir / "public_benchmark_ranked_results.md"
    json_file = results_dir / "public_benchmark_ranked_results.json"

    # Merge with previous leaderboard if running an individual model with matching task count
    if is_single_model and json_file.exists():
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                prev_data = json.load(f)
            if prev_data.get("tasks_evaluated_count") == num_tasks:
                existing_map = {row["model"]: row for row in prev_data.get("ranked_leaderboard", [])}
                # Update or add current tested model
                for res in summary_table:
                    existing_map[res["model"]] = res
                summary_table = list(existing_map.values())
                print(f"[i] Merged single model run with existing {len(summary_table)} benchmarked models.", flush=True)
        except Exception as e:
            print(f"[!] Note: Could not merge with existing results ({e}). Using current run only.", flush=True)

    # RANKING LOGIC: Sort primarily by Pass@1 descending, secondarily by Speed descending
    summary_table.sort(key=lambda x: (x["pass_rate"], x["avg_speed"]), reverse=True)
    
    print("\n" + "="*88, flush=True)
    print(" OFFICIAL OPENAI HUMANEVAL: RANKED LOCAL MODEL LEADERBOARD", flush=True)
    print(f" Dataset: Official OpenAI HumanEval ({num_tasks} Tasks) | Temperature: 0.0 (Deterministic)", flush=True)
    print("="*88, flush=True)
    print(f"{'Rank':<10} | {'Model Name':<21} | {'Params':<7} | {'Pass@1 (%)':<11} | {'Score':<8} | {'Speed (t/s)':<12} | {'Avg Time':<10}", flush=True)
    print("-" * 88, flush=True)
    
    for i, row in enumerate(summary_table, 1):
        score_str = f"{row['passed_count']}/{row['total_evaluated']}"
        params = param_map.get(row['model'], "N/A")
        rank_str = f"#{i}"
        if i == 1:
            rank_str = "#1 WINNER"
        elif i == 2:
            rank_str = "#2 RUNNER"
            
        print(f"{rank_str:<10} | {row['model']:<21} | {params:<7} | {row['pass_rate']:<9.1f}% | {score_str:<8} | {row['avg_speed']:<12.1f} | {row['avg_latency']:<8.2f}s", flush=True)
    print("="*88, flush=True)
    
    md_content = f"""# Official OpenAI HumanEval Benchmark: Ranked Local Model Leaderboard

> **Benchmark Dataset:** Official OpenAI HumanEval (`HumanEval.jsonl`, 100% Public Data)  
> **Evaluation Mode:** Greedy Decoding ($T = 0.0$, Deterministic)  
> **Evaluated Tasks:** {num_tasks} Standard Python Coding Problems  
> **Test Harness:** Subprocess execution with official `check()` assertions  
> **Date:** October 2026  

---

### Ranked Leaderboard Table

| Rank | Model Name | Parameter Size | Pass@1 Success Rate | Correct / Total | Generation Speed | Avg Latency | Recommendation Tier |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
"""
    for i, row in enumerate(summary_table, 1):
        score_str = f"{row['passed_count']}/{row['total_evaluated']}"
        params = param_map.get(row['model'], "N/A")
        tier_rec = "Alternative Baseline"
        if row['model'] == "qwen2.5-coder:7b":
            tier_rec = "**Default Local (Standard GPU >= 6GB)**"
        elif row['model'] == "qwen2.5-coder:1.5b":
            tier_rec = "**Default Local (Low-Spec CPU / <= 8GB RAM)**"
        elif row['model'] == "gpt-oss:20b":
            tier_rec = "**High-Capacity Local (High-End GPU >= 16GB / 32GB RAM)**"
            
        md_content += f"| **#{i}** | **`{row['model']}`** | {params} | **{row['pass_rate']:.1f}%** | {score_str} | {row['avg_speed']:.1f} t/s | {row['avg_latency']:.2f}s | {tier_rec} |\n"
        
    md_content += """
---

### Key Takeaways
1. **Pass@1 Functional Correctness:** Models are ranked by their ability to write syntactically valid code that satisfies 100% of OpenAI's rigorous test assertions.
2. **Speed & Efficiency:** Throughput (tokens/second) reflects live inference speed on local hardware.
3. **Reproducibility:** Anyone can re-run this exact test with:
   ```powershell
   # Test all models:
   python benchmarks_llm_patch/run_public_benchmark_test.py all 10

   # Or test a specific model (e.g. gpt-oss:20b) and auto-merge into leaderboard:
   python benchmarks_llm_patch/run_public_benchmark_test.py gpt-oss:20b 10
   ```
"""
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(md_content)
        
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump({
            "benchmark_dataset": "OpenAI HumanEval (Official)",
            "tasks_evaluated_count": num_tasks,
            "ranked_leaderboard": summary_table
        }, f, indent=2)
        
    print(f"\n[+] Ranked Markdown Leaderboard saved to: {md_file}", flush=True)
    print(f"[+] Structured JSON Results saved to:      {json_file}", flush=True)


if __name__ == "__main__":
    main()

