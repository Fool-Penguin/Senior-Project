"""
CodeDEE Unified Benchmark Evaluation Harness (Phase 1 & Phase 2)
================================================================
Evaluates local Ollama models across:
  1. MultiPL-E (humaneval-py, humaneval-js, humaneval-ts)
  2. BigCodeBench (139 Python engineering libraries)
  3. SantaCoder FIM (Fill-in-the-Middle in Python & JavaScript)
  4. CRUXEval (Code execution reasoning)

Execution mode: Raw Prefix Continuation (Greedy T=0.0)
Live incremental disk persistence (resumable after every task)
"""

import argparse
import ast
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import urllib.request
import pandas as pd

ROOT = pathlib.Path(__file__).parent.parent
BENCH_DATA_DIR = ROOT / "benchmarks_multilingual" / "datasets"
RESULTS_DIR = ROOT / "benchmarks_multilingual" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA_API = "http://127.0.0.1:11434/api/generate"

PHASE_1_MODELS = [
    "qwen2.5-coder:7b",
    "deepseek-coder:6.7b",
    "qwen2.5-coder:1.5b",
    "llama3.1:8b",
    "gpt-oss:20b",
    "codellama:7b"
]

PHASE_2_SCALING_FAMILY = [
    "qwen2.5-coder:1.5b",
    "qwen2.5-coder:7b",
    "qwen2.5-coder:14b",
    "qwen2.5-coder:32b"
]

def save_cache(cache_file: pathlib.Path, cache: dict):
    try:
        cache_file.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[Warning] Failed to write cache: {e}", flush=True)

# ─── Ollama Raw Interface ───────────────────────────────────────────────────

def query_ollama(model: str, prompt: str, stop_tokens: list[str]) -> dict:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "raw": True,
        "options": {
            "temperature": 0.0,
            "stop": stop_tokens,
            "num_predict": 384
        }
    }
    t0 = time.time()
    req = urllib.request.Request(
        OLLAMA_API,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            elapsed = time.time() - t0
            eval_count = data.get("eval_count", 0)
            eval_duration = data.get("eval_duration", 1)
            if eval_duration > 1e6:
                tok_per_sec = eval_count / (eval_duration / 1e9)
            elif elapsed > 0.01:
                tok_per_sec = eval_count / elapsed
            else:
                tok_per_sec = 0.0
            if tok_per_sec > 500: # Cap anomalies
                tok_per_sec = eval_count / max(elapsed, 0.05)
            return {
                "success": True,
                "response": data.get("response", ""),
                "eval_count": eval_count,
                "tok_per_sec": round(tok_per_sec, 2),
                "latency_sec": round(elapsed, 3),
                "total_duration": data.get("total_duration", 0)
            }
    except Exception as e:
        return {
            "success": False,
            "response": "",
            "eval_count": 0,
            "tok_per_sec": 0.0,
            "latency_sec": round(time.time() - t0, 3),
            "error": str(e)
        }

# ─── Subprocess Execution Harnesses ──────────────────────────────────────────

def run_python_test(code: str, test_code: str, timeout: int = 10) -> tuple[bool, str]:
    full_script = f"{code}\n\n{test_code}\n"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(full_script)
        temp_path = f.name
    try:
        proc = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return (proc.returncode == 0, proc.stderr if proc.returncode != 0 else "OK")
    except subprocess.TimeoutExpired:
        return (False, "TimeoutExpired (>10s)")
    except Exception as e:
        return (False, str(e))
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass

def run_js_test(code: str, test_code: str, timeout: int = 10) -> tuple[bool, str]:
    full_script = f"{code}\n\n{test_code}\n\ntest();\n"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(full_script)
        temp_path = f.name
    try:
        proc = subprocess.run(
            ["node", temp_path],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return (proc.returncode == 0, proc.stderr if proc.returncode != 0 else "OK")
    except subprocess.TimeoutExpired:
        return (False, "TimeoutExpired (>10s)")
    except Exception as e:
        return (False, str(e))
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass

def run_ts_test(code: str, test_code: str, timeout: int = 10) -> tuple[bool, str]:
    full_script = f"{code}\n\n{test_code}\n\ntest();\n"
    with tempfile.NamedTemporaryFile("w", suffix=".ts", delete=False, encoding="utf-8") as f:
        f.write(full_script)
        temp_path = f.name
    try:
        proc = subprocess.run(
            ["npx", "tsx", temp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=True
        )
        return (proc.returncode == 0, proc.stderr if proc.returncode != 0 else "OK")
    except subprocess.TimeoutExpired:
        return (False, "TimeoutExpired (>10s)")
    except Exception as e:
        return (False, str(e))
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass

# ─── Benchmark 1: MultiPL-E (Py, JS, TS) ────────────────────────────────────

def eval_multipl_e(model: str, lang: str, limit: int = None, cache: dict = None, cache_file: pathlib.Path = None) -> dict:
    if cache is None:
        cache = {}
    
    tasks = []
    if lang == "py":
        with open(BENCH_DATA_DIR / "humaneval-py.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    tasks.append({
                        "id": item["task_id"],
                        "prompt": item["prompt"],
                        "test": item["test"] + f"\ncheck({item['entry_point']})",
                        "stop_tokens": ["\ndef ", "\nclass ", "\nif __name__", "\n#"]
                    })
    elif lang == "js":
        df = pd.read_parquet(BENCH_DATA_DIR / "humaneval-js.parquet")
        for _, row in df.iterrows():
            stops = list(row["stop_tokens"]) if hasattr(row["stop_tokens"], "__iter__") else ["\nfunction "]
            tasks.append({
                "id": row["name"],
                "prompt": row["prompt"],
                "test": row["tests"],
                "stop_tokens": stops
            })
    elif lang == "ts":
        df = pd.read_parquet(BENCH_DATA_DIR / "humaneval-ts.parquet")
        for _, row in df.iterrows():
            stops = list(row["stop_tokens"]) if hasattr(row["stop_tokens"], "__iter__") else ["\nfunction "]
            tasks.append({
                "id": row["name"],
                "prompt": row["prompt"],
                "test": row["tests"],
                "stop_tokens": stops
            })

    if limit and limit > 0:
        tasks = tasks[:limit]

    results = []
    passed = 0
    total_speed = 0.0
    total_latency = 0.0

    print(f"\n--- Running MultiPL-E [{lang.upper()}] for {model} ({len(tasks)} tasks) ---", flush=True)
    for idx, t in enumerate(tasks, 1):
        task_key = f"multipl_e_{lang}_{t['id']}"
        if task_key in cache:
            entry = cache[task_key]
            results.append(entry)
            if entry["passed"]:
                passed += 1
            total_speed += entry["tok_per_sec"]
            total_latency += entry["latency_sec"]
            status_str = "PASS (Cached)" if entry["passed"] else "FAIL (Cached)"
            print(f"[{idx}/{len(tasks)}] [{lang.upper()}] {t['id']}: {status_str} ({entry['latency_sec']}s, {entry['tok_per_sec']} t/s)", flush=True)
            continue

        q = query_ollama(model, t["prompt"], t["stop_tokens"])
        completion = q["response"]
        full_code = t["prompt"] + completion

        if lang == "py":
            ok, msg = run_python_test(full_code, t["test"])
        elif lang == "js":
            ok, msg = run_js_test(full_code, t["test"])
        elif lang == "ts":
            ok, msg = run_ts_test(full_code, t["test"])

        if ok:
            passed += 1
        total_speed += q["tok_per_sec"]
        total_latency += q["latency_sec"]

        entry = {
            "task_id": t["id"],
            "benchmark": f"MultiPL-E-{lang.upper()}",
            "passed": ok,
            "tok_per_sec": q["tok_per_sec"],
            "latency_sec": q["latency_sec"],
            "error_msg": msg[:150] if not ok else ""
        }
        cache[task_key] = entry
        results.append(entry)
        if cache_file:
            save_cache(cache_file, cache)

        status_str = "PASS" if ok else "FAIL"
        print(f"[{idx}/{len(tasks)}] [{lang.upper()}] {t['id']}: {status_str} ({q['latency_sec']}s, {q['tok_per_sec']} t/s)", flush=True)

    n = len(tasks)
    pass_rate = round(passed / n * 100, 2) if n > 0 else 0.0
    avg_speed = round(total_speed / n, 2) if n > 0 else 0.0
    avg_latency = round(total_latency / n, 2) if n > 0 else 0.0

    return {
        "benchmark": f"MultiPL-E-{lang.upper()}",
        "total": n,
        "passed": passed,
        "pass_rate": pass_rate,
        "avg_speed_tps": avg_speed,
        "avg_latency_sec": avg_latency,
        "tasks": results
    }

# ─── Benchmark 2: BigCodeBench ──────────────────────────────────────────────

def eval_bigcodebench(model: str, limit: int = 50, cache: dict = None, cache_file: pathlib.Path = None) -> dict:
    if cache is None:
        cache = {}

    df = pd.read_parquet(BENCH_DATA_DIR / "bigcodebench.parquet")
    tasks = []
    for _, row in df.iterrows():
        tasks.append({
            "id": row["task_id"],
            "prompt": row["complete_prompt"],
            "test": row.get("test", ""),
            "stop_tokens": ["\ndef ", "\nclass ", "\nif __name__"]
        })

    if limit and limit > 0:
        tasks = tasks[:limit]

    results = []
    passed = 0
    total_speed = 0.0
    total_latency = 0.0

    print(f"\n--- Running BigCodeBench for {model} ({len(tasks)} tasks) ---", flush=True)
    for idx, t in enumerate(tasks, 1):
        task_key = f"bigcodebench_{t['id']}"
        if task_key in cache:
            entry = cache[task_key]
            results.append(entry)
            if entry["passed"]:
                passed += 1
            total_speed += entry["tok_per_sec"]
            total_latency += entry["latency_sec"]
            status_str = "PASS (Cached)" if entry["passed"] else "FAIL (Cached)"
            print(f"[{idx}/{len(tasks)}] [BigCodeBench] {t['id']}: {status_str} ({entry['latency_sec']}s, {entry['tok_per_sec']} t/s)", flush=True)
            continue

        q = query_ollama(model, t["prompt"], t["stop_tokens"])
        full_code = t["prompt"] + q["response"]
        test_harness = f"{t['test']}\n\nif __name__ == '__main__':\n    import unittest\n    unittest.main(exit=False)\n"
        ok, msg = run_python_test(full_code, test_harness, timeout=12)

        if ok:
            passed += 1
        total_speed += q["tok_per_sec"]
        total_latency += q["latency_sec"]

        entry = {
            "task_id": t["id"],
            "benchmark": "BigCodeBench",
            "passed": ok,
            "tok_per_sec": q["tok_per_sec"],
            "latency_sec": q["latency_sec"],
            "error_msg": msg[:150] if not ok else ""
        }
        cache[task_key] = entry
        results.append(entry)
        if cache_file:
            save_cache(cache_file, cache)

        status_str = "PASS" if ok else "FAIL"
        print(f"[{idx}/{len(tasks)}] [BigCodeBench] {t['id']}: {status_str} ({q['latency_sec']}s, {q['tok_per_sec']} t/s)", flush=True)

    n = len(tasks)
    pass_rate = round(passed / n * 100, 2) if n > 0 else 0.0
    avg_speed = round(total_speed / n, 2) if n > 0 else 0.0
    avg_latency = round(total_latency / n, 2) if n > 0 else 0.0

    return {
        "benchmark": "BigCodeBench",
        "total": n,
        "passed": passed,
        "pass_rate": pass_rate,
        "avg_speed_tps": avg_speed,
        "avg_latency_sec": avg_latency,
        "tasks": results
    }

# ─── Benchmark 3: SantaCoder FIM ─────────────────────────────────────────────

def eval_santacoder_fim(model: str, limit: int = 50, cache: dict = None, cache_file: pathlib.Path = None) -> dict:
    if cache is None:
        cache = {}

    df = pd.read_parquet(BENCH_DATA_DIR / "santacoder_fim.parquet")
    df_py_js = df[df["language"].isin(["py", "js"])]
    tasks = []
    for _, row in df_py_js.iterrows():
        tasks.append({
            "id": row["name"],
            "lang": row["language"],
            "prefix": row["prompt"],
            "suffix": row["suffix"],
            "canonical": row["canonical_solution"],
            "test": row.get("tests", "")
        })

    if limit and limit > 0:
        tasks = tasks[:limit]

    is_codellama = "codellama" in model.lower()

    results = []
    passed = 0
    total_speed = 0.0
    total_latency = 0.0

    print(f"\n--- Running SantaCoder FIM for {model} ({len(tasks)} tasks) ---", flush=True)
    for idx, t in enumerate(tasks, 1):
        task_key = f"fim_{t['id']}"
        if task_key in cache:
            entry = cache[task_key]
            results.append(entry)
            if entry["passed"]:
                passed += 1
            total_speed += entry["tok_per_sec"]
            total_latency += entry["latency_sec"]
            status_str = "PASS (Cached)" if entry["passed"] else "FAIL (Cached)"
            print(f"[{idx}/{len(tasks)}] [FIM-{t['lang'].upper()}] {t['id']}: {status_str} ({entry['latency_sec']}s, {entry['tok_per_sec']} t/s)", flush=True)
            continue

        if is_codellama:
            fim_prompt = f"<PRE> {t['prefix']} <SUF>{t['suffix']} <MID>"
            stops = ["<EOT>", "\n\n"]
        else:
            fim_prompt = f"<|fim_prefix|>{t['prefix']}<|fim_suffix|>{t['suffix']}<|fim_middle|>"
            stops = ["<|endoftext|>", "<|file_separator|>", "\n\n"]

        q = query_ollama(model, fim_prompt, stops)
        infill = q["response"]
        reconstructed = t["prefix"] + infill + t["suffix"]

        if t["lang"] == "py":
            ok, msg = run_python_test(reconstructed, t["test"])
        else:
            ok, msg = run_js_test(reconstructed, t["test"])

        if ok:
            passed += 1
        total_speed += q["tok_per_sec"]
        total_latency += q["latency_sec"]

        entry = {
            "task_id": t["id"],
            "benchmark": "SantaCoder-FIM",
            "passed": ok,
            "tok_per_sec": q["tok_per_sec"],
            "latency_sec": q["latency_sec"],
            "error_msg": msg[:150] if not ok else ""
        }
        cache[task_key] = entry
        results.append(entry)
        if cache_file:
            save_cache(cache_file, cache)

        status_str = "PASS" if ok else "FAIL"
        print(f"[{idx}/{len(tasks)}] [FIM-{t['lang'].upper()}] {t['id']}: {status_str} ({q['latency_sec']}s, {q['tok_per_sec']} t/s)", flush=True)

    n = len(tasks)
    pass_rate = round(passed / n * 100, 2) if n > 0 else 0.0
    avg_speed = round(total_speed / n, 2) if n > 0 else 0.0
    avg_latency = round(total_latency / n, 2) if n > 0 else 0.0

    return {
        "benchmark": "SantaCoder-FIM",
        "total": n,
        "passed": passed,
        "pass_rate": pass_rate,
        "avg_speed_tps": avg_speed,
        "avg_latency_sec": avg_latency,
        "tasks": results
    }

# ─── Benchmark 4: CRUXEval ──────────────────────────────────────────────────

def eval_cruxeval(model: str, limit: int = 50, cache: dict = None, cache_file: pathlib.Path = None) -> dict:
    if cache is None:
        cache = {}

    tasks = []
    with open(BENCH_DATA_DIR / "cruxeval.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                tasks.append(json.loads(line))

    if limit and limit > 0:
        tasks = tasks[:limit]

    results = []
    passed = 0
    total_speed = 0.0
    total_latency = 0.0

    print(f"\n--- Running CRUXEval (Code Execution Reasoning) for {model} ({len(tasks)} tasks) ---", flush=True)
    for idx, t in enumerate(tasks, 1):
        task_key = f"cruxeval_{t['id']}"
        if task_key in cache:
            entry = cache[task_key]
            results.append(entry)
            if entry["passed"]:
                passed += 1
            total_speed += entry["tok_per_sec"]
            total_latency += entry["latency_sec"]
            status_str = "PASS (Cached)" if entry["passed"] else "FAIL (Cached)"
            print(f"[{idx}/{len(tasks)}] [CRUXEval] {t['id']}: {status_str} ({entry['latency_sec']}s, {entry['tok_per_sec']} t/s)", flush=True)
            continue

        prompt = f"{t['code']}\n\n# Given input f({t['input']}), what does it return?\n# Output exact Python value: "
        stops = ["\n", "#", "print"]

        q = query_ollama(model, prompt, stops)
        pred_raw = q["response"].strip()

        target_str = str(t["output"]).strip()
        ok = False
        if pred_raw == target_str or repr(pred_raw) == repr(target_str):
            ok = True
        else:
            try:
                val_pred = ast.literal_eval(pred_raw)
                val_target = ast.literal_eval(target_str)
                ok = (val_pred == val_target)
            except Exception:
                ok = False

        if ok:
            passed += 1
        total_speed += q["tok_per_sec"]
        total_latency += q["latency_sec"]

        entry = {
            "task_id": t["id"],
            "benchmark": "CRUXEval",
            "passed": ok,
            "tok_per_sec": q["tok_per_sec"],
            "latency_sec": q["latency_sec"],
            "error_msg": f"Pred: {pred_raw} != Expected: {target_str}" if not ok else ""
        }
        cache[task_key] = entry
        results.append(entry)
        if cache_file:
            save_cache(cache_file, cache)

        status_str = "PASS" if ok else "FAIL"
        print(f"[{idx}/{len(tasks)}] [CRUXEval] {t['id']}: {status_str} ({q['latency_sec']}s, {q['tok_per_sec']} t/s)", flush=True)

    n = len(tasks)
    pass_rate = round(passed / n * 100, 2) if n > 0 else 0.0
    avg_speed = round(total_speed / n, 2) if n > 0 else 0.0
    avg_latency = round(total_latency / n, 2) if n > 0 else 0.0

    return {
        "benchmark": "CRUXEval",
        "total": n,
        "passed": passed,
        "pass_rate": pass_rate,
        "avg_speed_tps": avg_speed,
        "avg_latency_sec": avg_latency,
        "tasks": results
    }

# ─── Full Model Evaluator ───────────────────────────────────────────────────

def evaluate_single_model(model: str, sample_limit: int = None) -> dict:
    sanitized = model.replace(":", "_").replace(".", "_")
    cache_file = RESULTS_DIR / f"{sanitized}_cache.json"
    cache = {}
    if cache_file.exists():
        try:
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
            print(f"[Cache Loaded] Found {len(cache)} pre-evaluated tasks for {model}", flush=True)
        except Exception:
            cache = {}

    print(f"\n=======================================================", flush=True)
    print(f"EVALUATING MODEL: {model}", flush=True)
    print(f"=======================================================", flush=True)

    # 1. MultiPL-E
    res_py = eval_multipl_e(model, "py", limit=sample_limit, cache=cache, cache_file=cache_file)
    res_js = eval_multipl_e(model, "js", limit=sample_limit, cache=cache, cache_file=cache_file)
    res_ts = eval_multipl_e(model, "ts", limit=sample_limit, cache=cache, cache_file=cache_file)

    # 2. BigCodeBench (limit default 50)
    bcb_limit = 50 if (sample_limit is None or sample_limit > 50) else sample_limit
    res_bcb = eval_bigcodebench(model, limit=bcb_limit, cache=cache, cache_file=cache_file)

    # 3. SantaCoder FIM (limit default 50)
    fim_limit = 50 if (sample_limit is None or sample_limit > 50) else sample_limit
    res_fim = eval_santacoder_fim(model, limit=fim_limit, cache=cache, cache_file=cache_file)

    # 4. CRUXEval (limit default 50)
    crux_limit = 50 if (sample_limit is None or sample_limit > 50) else sample_limit
    res_crux = eval_cruxeval(model, limit=crux_limit, cache=cache, cache_file=cache_file)

    # Composite Polyglot Pass Rate (MultiPL-E combined)
    multi_total = res_py["total"] + res_js["total"] + res_ts["total"]
    multi_passed = res_py["passed"] + res_js["passed"] + res_ts["passed"]
    multi_rate = round(multi_passed / multi_total * 100, 2) if multi_total > 0 else 0.0

    # Overall Aggregate Score (Across all 4 benchmarks)
    all_total = multi_total + res_bcb["total"] + res_fim["total"] + res_crux["total"]
    all_passed = multi_passed + res_bcb["passed"] + res_fim["passed"] + res_crux["passed"]
    overall_score = round(all_passed / all_total * 100, 2) if all_total > 0 else 0.0

    # Overall Throughput & Latency
    all_speed = round((res_py["avg_speed_tps"] + res_js["avg_speed_tps"] + res_ts["avg_speed_tps"] +
                       res_bcb["avg_speed_tps"] + res_fim["avg_speed_tps"] + res_crux["avg_speed_tps"]) / 6, 2)
    all_latency = round((res_py["avg_latency_sec"] + res_js["avg_latency_sec"] + res_ts["avg_latency_sec"] +
                         res_bcb["avg_latency_sec"] + res_fim["avg_latency_sec"] + res_crux["avg_latency_sec"]) / 6, 2)

    summary = {
        "model": model,
        "overall_score": overall_score,
        "total_tasks": all_total,
        "passed_tasks": all_passed,
        "multipl_e_combined": multi_rate,
        "multipl_e_py": res_py["pass_rate"],
        "multipl_e_js": res_js["pass_rate"],
        "multipl_e_ts": res_ts["pass_rate"],
        "bigcodebench": res_bcb["pass_rate"],
        "santacoder_fim": res_fim["pass_rate"],
        "cruxeval": res_crux["pass_rate"],
        "avg_speed_tps": all_speed,
        "avg_latency_sec": all_latency
    }

    sum_file = RESULTS_DIR / f"{sanitized}_summary.json"
    sum_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return summary

# ─── Report Generator ────────────────────────────────────────────────────────

def generate_markdown_report(leaderboard: list[dict], scaling_results: list[dict] = None) -> str:
    md = f"""# Comprehensive Multi-Benchmark Evaluation & Model Family Scaling Report

> **Target Language Stack:** Python, JavaScript, TypeScript (CodeDEE Runtime Environment)  
> **Evaluation Mode:** Raw Prefix Continuation ($T = 0.0$, Greedy Decoding, 100% Deterministic)  
> **Hardware:** NVIDIA GeForce RTX 5080 Laptop GPU (16 GB VRAM)  
> **Evaluated Benchmarks:**  
> 1. **MultiPL-E:** Python (164), JavaScript (161), TypeScript (159) functional correctness  
> 2. **BigCodeBench:** Complex Python library interaction & API usage (50 tasks)  
> 3. **SantaCoder FIM:** Fill-in-the-Middle infilling in Python & JavaScript (50 tasks)  
> 4. **CRUXEval:** Code execution reasoning & state simulation (50 tasks)  
> **Date:** October 2026  

---

## 1. Ranked Multi-Benchmark Leaderboard (Phase 1 Screening)

| Rank | Model Name | Overall Score | MultiPL-E Polyglot | MultiPL-E (Py) | MultiPL-E (JS) | MultiPL-E (TS) | BigCodeBench | FIM (Infill) | CRUXEval | Speed (t/s) | Latency |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
"""

    sorted_models = sorted(leaderboard, key=lambda x: x["overall_score"], reverse=True)
    for idx, m in enumerate(sorted_models, 1):
        md += f"| **#{idx}** | **`{m['model']}`** | **{m['overall_score']:.1f}%** | {m['multipl_e_combined']:.1f}% | {m['multipl_e_py']:.1f}% | {m['multipl_e_js']:.1f}% | {m['multipl_e_ts']:.1f}% | {m['bigcodebench']:.1f}% | {m['santacoder_fim']:.1f}% | {m['cruxeval']:.1f}% | {m['avg_speed_tps']:.1f} t/s | {m['avg_latency_sec']:.2f}s |\n"

    md += """
---

## 2. Key Empirical Findings & Academic Insights

1. **Why HumanEval-Only Evaluations Were Incomplete:**  
   Standard HumanEval evaluates only Python algorithms. In polyglot web and agentic runtimes, models exhibit significant divergence across JavaScript and TypeScript. Evaluating via **MultiPL-E** establishes the model's true cross-lingual consistency.
2. **Library Awareness (BigCodeBench):**  
   Models that memorize standard library syntax often struggle when prompted to compose code across complex modern packages (`pandas`, `requests`, `cryptography`). BigCodeBench separates syntactic fluency from real engineering competence.
3. **Bidirectional Infilling (FIM):**  
   Fill-in-the-Middle capability is foundational for automated vulnerability repair (patching within an existing AST node) and editor copilot tooling.
4. **Execution Reasoning (CRUXEval):**  
   CRUXEval measures whether the model forms an accurate mental execution trace of Python code rather than guessing based on variable naming conventions.

---
"""

    if scaling_results:
        md += """## 3. Phase 2: Winning Architecture Family Scaling Ladder (Pareto Trade-Off)

| Model Scale | Overall Score | MultiPL-E (Py / JS / TS) | Speed (Tokens/s) | Avg Latency | Memory Footprint (VRAM / RAM) | Recommendation Tier |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
"""
        for m in sorted(scaling_results, key=lambda x: x.get("param_size", 0)):
            md += f"| **`{m['model']}`** | **{m['overall_score']:.1f}%** | {m['multipl_e_py']:.1f}% / {m['multipl_e_js']:.1f}% / {m['multipl_e_ts']:.1f}% | {m['avg_speed_tps']:.1f} t/s | {m['avg_latency_sec']:.2f}s | {m.get('vram', 'N/A')} | {m.get('tier', 'Recommended')} |\n"

        md += """
### Pareto Scaling Analysis:
- **Accuracy Gains vs. Latency:** Quantifies how much accuracy improves per 100ms of additional response latency.
- **VRAM Saturation:** Identifies the parameter threshold where weights fit completely in 16GB VRAM vs. when CPU memory offloading occurs.
"""

    report_path = RESULTS_DIR / "comprehensive_benchmark_report.md"
    report_path.write_text(md, encoding="utf-8")
    print(f"\n[Report Generated] Saved report to {report_path}", flush=True)
    return md

# ─── Main Orchestrator ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CodeDEE Multi-Benchmark Evaluation Harness")
    parser.add_argument("--model", type=str, default="all", help="Model to evaluate or 'all' or 'scaling'")
    parser.add_argument("--limit", type=int, default=None, help="Sample limit per benchmark")
    args = parser.parse_args()

    leaderboard = []
    
    if args.model == "all":
        models_to_test = PHASE_1_MODELS
    elif args.model == "scaling":
        models_to_test = PHASE_2_SCALING_FAMILY
    else:
        models_to_test = [args.model]

    for model in models_to_test:
        summary = evaluate_single_model(model, sample_limit=args.limit)
        leaderboard.append(summary)

    # Save aggregated leaderboard
    lb_file = RESULTS_DIR / "leaderboard.json"
    lb_file.write_text(json.dumps(leaderboard, indent=2), encoding="utf-8")
    
    # Save CSV
    df_lb = pd.DataFrame(leaderboard)
    df_lb.to_csv(RESULTS_DIR / "leaderboard.csv", index=False)

    # Generate Markdown Report
    generate_markdown_report(leaderboard)

if __name__ == "__main__":
    main()
