"""
CodeDEE Master Benchmark Runner (Standard Academic Instruct Protocol)
======================================================================
Evaluates local Ollama models sequentially across 5 major code benchmarks:
  1. Official OpenAI HumanEval (Python, 164 tasks) - 100% full dataset
  2. MultiPL-E Multilingual (JavaScript 161 tasks, TypeScript 159 tasks) - 100% full dataset
  3. BigCodeBench (Python with 139 engineering libraries, 250 tasks)
  4. SantaCoder FIM (Bidirectional code infilling in Python & JS, 250 tasks)
  5. CRUXEval (Code execution reasoning & state simulation, 250 tasks)

Total evaluated tasks per model: 1,234 tasks (or configurable via CLI).

Protocol Alignment (Academic Standard):
  - Instruct / Chat Template for generation tasks (HumanEval, MultiPL-E, BigCodeBench)
  - Multi-language regex code extraction (eliminates markdown syntax crashes)
  - 512 token generation budget (eliminates premature expression cutoffs)
  - Natural end-of-turn termination (eliminates premature '\n#' stop token truncation)
  - Model-specific FIM infilling tokens for SantaCoder FIM
  - Live hardware monitoring: Speed (t/s), Latency (s), RAM (GB), GPU VRAM (GB)
  - Windows-safe process tree termination (taskkill /F /T /PID)
  - Atomic incremental disk caching (safe to Ctrl+C and resume anytime)

Usage:
  python run_all_benchmarks.py
  python run_all_benchmarks.py --limit 10       (Quick validation)
  python run_all_benchmarks.py --skip-phase2    (Run Phase 1 only)
"""

import argparse
import ast
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
import pandas as pd
import psutil

try:
    import pynvml
    pynvml.nvmlInit()
    HAS_NVML = True
except Exception:
    HAS_NVML = False

ROOT = pathlib.Path(__file__).parent
BENCH_DATA_DIR = ROOT / "benchmarks_multilingual" / "datasets"
RESULTS_DIR = ROOT / "benchmarks_multilingual" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA_API = "http://127.0.0.1:11434/api/generate"

# Phase 1: 6 Candidate Architectures
PHASE_1_MODELS = [
    "qwen2.5-coder:7b",
    "deepseek-coder:6.7b",
    "qwen2.5-coder:1.5b",
    "llama3.1:8b",
    "codellama:7b",
    "gpt-oss:20b"
]

# Phase 2: Family Scaling Ladder
SCALING_LADDER_QWEN = [
    "qwen2.5-coder:1.5b",
    "qwen2.5-coder:7b",
    "qwen2.5-coder:14b",
    "qwen2.5-coder:32b"
]

# Standard Sample Quotas
QUOTA_HUMANEVAL = 164     # 100% of dataset
QUOTA_MULTIP_JS = 161     # 100% of dataset
QUOTA_MULTIP_TS = 159     # 100% of dataset
DEFAULT_QUOTA_BCB = 250   # 250 tasks from 1,140
DEFAULT_QUOTA_FIM = 250   # 250 tasks from 4,792
DEFAULT_QUOTA_CRUX = 250  # 250 tasks from 800

# ─── Live Memory Monitoring ──────────────────────────────────────────────────

def get_memory_stats() -> dict:
    ram = psutil.virtual_memory()
    ram_used_gb = round(ram.used / (1024 ** 3), 1)
    ram_total_gb = round(ram.total / (1024 ** 3), 1)
    ram_pct = ram.percent

    vram_used_gb = 0.0
    vram_total_gb = 0.0
    vram_pct = 0.0

    if HAS_NVML:
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            vram_used_gb = round(info.used / (1024 ** 3), 1)
            vram_total_gb = round(info.total / (1024 ** 3), 1)
            vram_pct = round(info.used / info.total * 100, 1)
        except Exception:
            pass

    return {
        "ram_used_gb": ram_used_gb,
        "ram_total_gb": ram_total_gb,
        "ram_pct": ram_pct,
        "vram_used_gb": vram_used_gb,
        "vram_total_gb": vram_total_gb,
        "vram_pct": vram_pct,
        "tag": f"[RAM: {ram_used_gb}/{ram_total_gb}GB ({ram_pct}%) | VRAM: {vram_used_gb}/{vram_total_gb}GB ({vram_pct}%)]"
    }

# ─── Cache Helper ────────────────────────────────────────────────────────────

def save_cache(cache_file: pathlib.Path, cache: dict):
    try:
        cache_file.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[Warning] Failed to write cache: {e}", flush=True)

# ─── Ollama Interface ────────────────────────────────────────────────────────

def query_ollama(model: str, prompt: str, raw: bool = False, stop_tokens: list[str] = None, num_predict: int = 512, timeout: int = 60) -> dict:
    options = {
        "temperature": 0.0,
        "num_predict": num_predict
    }
    if stop_tokens:
        options["stop"] = stop_tokens

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "raw": raw,
        "options": options
    }
    t0 = time.time()
    req = urllib.request.Request(
        OLLAMA_API,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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
            if tok_per_sec > 450:
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

# ─── Standard Code Block Extractor ───────────────────────────────────────────

def extract_code(raw_response: str, prompt: str, lang: str = "python") -> str:
    """
    Extracts clean code from LLM output across Python, JavaScript, and TypeScript.
    Handles markdown fenced blocks, stripped signatures, and raw code outputs.
    """
    lang_clean = lang.lower()
    patterns = [
        rf"```(?:{lang_clean}|{lang_clean[:2]}|py|js|ts)?\s*(.*?)\s*```",
        r"```\s*(.*?)\s*```"
    ]
    extracted = ""
    for pat in patterns:
        m = re.search(pat, raw_response, re.DOTALL | re.IGNORECASE)
        if m:
            extracted = m.group(1).strip()
            break
    if not extracted:
        extracted = raw_response.strip()

    # Clean residual markdown backticks
    extracted = re.sub(r"^```\w*\s*", "", extracted).strip()
    extracted = re.sub(r"\s*```$", "", extracted).strip()

    # Detect if extracted code already contains the function definition
    # If prompt signature is missing, prepend prompt header
    prompt_stripped = prompt.strip()
    first_line_prompt = prompt_stripped.split("\n")[0].strip() if prompt_stripped else ""

    if first_line_prompt and first_line_prompt in extracted:
        return extracted

    # Check if a function def exists with the same entry name
    if lang_clean == "python":
        if "\ndef " in "\n" + extracted or "\nclass " in "\n" + extracted:
            return extracted
        return prompt + "\n" + extracted
    else:
        # JS / TS
        if any(kw in extracted for kw in ["function ", "const ", "let ", "var ", "=>"]):
            return extracted
        return prompt + "\n" + extracted

# ─── Process Tree Execution with Windows Safe Termination ───────────────────

def run_command_safe(cmd: list[str], timeout: int = 10) -> tuple[bool, str]:
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            return (proc.returncode == 0, stderr if proc.returncode != 0 else "OK")
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
            except Exception:
                pass
            return (False, f"TimeoutExpired (>{timeout}s)")
    except Exception as e:
        return (False, str(e))

def run_python_test(code: str, test_code: str, timeout: int = 10) -> tuple[bool, str]:
    full_script = f"{code}\n\n{test_code}\n"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(full_script)
        temp_path = f.name
    try:
        return run_command_safe([sys.executable, temp_path], timeout=timeout)
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
        return run_command_safe(["node", temp_path], timeout=timeout)
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
        return run_command_safe(["node", "--experimental-strip-types", temp_path], timeout=timeout)
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass

# ─── Benchmark 1: Official OpenAI HumanEval (Python 164 Tasks) ──────────────

def eval_openai_humaneval(model: str, limit: int = None, cache: dict = None, cache_file: pathlib.Path = None) -> dict:
    if cache is None:
        cache = {}

    pq_path = BENCH_DATA_DIR / "openai_humaneval.parquet"
    if pq_path.exists():
        df = pd.read_parquet(pq_path)
        tasks = []
        for _, row in df.iterrows():
            tasks.append({
                "id": row["task_id"],
                "prompt": row["prompt"],
                "test": row["test"] + f"\ncheck({row['entry_point']})"
            })
    else:
        tasks = []
        with open(BENCH_DATA_DIR / "humaneval-py.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    tasks.append({
                        "id": item["task_id"],
                        "prompt": item["prompt"],
                        "test": item["test"] + f"\ncheck({item['entry_point']})"
                    })

    if limit and limit > 0:
        tasks = tasks[:limit]

    results = []
    passed = 0
    total_speed = 0.0
    total_latency = 0.0

    print(f"\n--- Running Official OpenAI HumanEval [Python] for {model} ({len(tasks)} tasks) ---", flush=True)
    for idx, t in enumerate(tasks, 1):
        task_key = f"humaneval_{t['id']}"

        if task_key in cache:
            entry = cache[task_key]
            results.append(entry)
            if entry["passed"]:
                passed += 1
            total_speed += entry.get("tok_per_sec", 0.0)
            total_latency += entry.get("latency_sec", 0.0)
            status_str = "PASS (Cached)" if entry["passed"] else "FAIL (Cached)"
            print(f"[{idx}/{len(tasks)}] [HumanEval] {t['id']}: {status_str} ({entry.get('latency_sec', 0)}s, {entry.get('tok_per_sec', 0)} t/s)", flush=True)
            continue

        instruct_prompt = f"""Complete the following Python function. Return ONLY the completed Python function inside a ```python ... ``` block.

{t['prompt']}
"""
        q = query_ollama(model, instruct_prompt, raw=False, num_predict=512)
        code = extract_code(q["response"], t["prompt"], lang="python")
        ok, msg = run_python_test(code, t["test"])

        if ok:
            passed += 1
        total_speed += q["tok_per_sec"]
        total_latency += q["latency_sec"]

        entry = {
            "task_id": t["id"],
            "benchmark": "OpenAI-HumanEval",
            "passed": ok,
            "tok_per_sec": q["tok_per_sec"],
            "latency_sec": q["latency_sec"],
            "error_msg": msg[:150] if not ok else ""
        }
        cache[task_key] = entry
        results.append(entry)
        if cache_file:
            save_cache(cache_file, cache)

        mem = get_memory_stats()
        status_str = "PASS" if ok else "FAIL"
        print(f"[{idx}/{len(tasks)}] [HumanEval] {t['id']}: {status_str} ({q['latency_sec']}s, {q['tok_per_sec']} t/s) {mem['tag']}", flush=True)

    n = len(tasks)
    pass_rate = round(passed / n * 100, 2) if n > 0 else 0.0
    avg_speed = round(total_speed / n, 2) if n > 0 else 0.0
    avg_latency = round(total_latency / n, 2) if n > 0 else 0.0

    return {
        "benchmark": "OpenAI-HumanEval",
        "total": n,
        "passed": passed,
        "pass_rate": pass_rate,
        "avg_speed_tps": avg_speed,
        "avg_latency_sec": avg_latency,
        "tasks": results
    }

# ─── Benchmark 2: MultiPL-E (JavaScript & TypeScript) ───────────────────────

def eval_multipl_e(model: str, lang: str, limit: int = None, cache: dict = None, cache_file: pathlib.Path = None) -> dict:
    if cache is None:
        cache = {}

    tasks = []
    lang_full = "JavaScript" if lang == "js" else "TypeScript"
    file_name = f"humaneval-{lang}.parquet"
    df = pd.read_parquet(BENCH_DATA_DIR / file_name)

    for _, row in df.iterrows():
        tasks.append({
            "id": row["name"],
            "prompt": row["prompt"],
            "test": row["tests"]
        })

    if limit and limit > 0:
        tasks = tasks[:limit]

    results = []
    passed = 0
    total_speed = 0.0
    total_latency = 0.0

    print(f"\n--- Running MultiPL-E [{lang_full}] for {model} ({len(tasks)} tasks) ---", flush=True)
    for idx, t in enumerate(tasks, 1):
        task_key = f"multipl_e_{lang}_{t['id']}"

        if task_key in cache:
            entry = cache[task_key]
            results.append(entry)
            if entry["passed"]:
                passed += 1
            total_speed += entry.get("tok_per_sec", 0.0)
            total_latency += entry.get("latency_sec", 0.0)
            status_str = "PASS (Cached)" if entry["passed"] else "FAIL (Cached)"
            print(f"[{idx}/{len(tasks)}] [{lang.upper()}] {t['id']}: {status_str} ({entry.get('latency_sec', 0)}s, {entry.get('tok_per_sec', 0)} t/s)", flush=True)
            continue

        instruct_prompt = f"""Complete the following {lang_full} function. Return ONLY the completed {lang_full} function inside a ```{lang} ... ``` block.

{t['prompt']}
"""
        q = query_ollama(model, instruct_prompt, raw=False, num_predict=512)
        code = extract_code(q["response"], t["prompt"], lang=lang)

        if lang == "js":
            ok, msg = run_js_test(code, t["test"])
        else:
            ok, msg = run_ts_test(code, t["test"])

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

        mem = get_memory_stats()
        status_str = "PASS" if ok else "FAIL"
        print(f"[{idx}/{len(tasks)}] [{lang.upper()}] {t['id']}: {status_str} ({q['latency_sec']}s, {q['tok_per_sec']} t/s) {mem['tag']}", flush=True)

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

# ─── Benchmark 3: BigCodeBench (250 Tasks) ───────────────────────────────────

def eval_bigcodebench(model: str, limit: int = DEFAULT_QUOTA_BCB, cache: dict = None, cache_file: pathlib.Path = None) -> dict:
    if cache is None:
        cache = {}

    df = pd.read_parquet(BENCH_DATA_DIR / "bigcodebench.parquet")
    tasks = []
    for _, row in df.iterrows():
        tasks.append({
            "id": row["task_id"],
            "prompt": row["complete_prompt"],
            "test": row.get("test", "")
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
            total_speed += entry.get("tok_per_sec", 0.0)
            total_latency += entry.get("latency_sec", 0.0)
            status_str = "PASS (Cached)" if entry["passed"] else "FAIL (Cached)"
            print(f"[{idx}/{len(tasks)}] [BigCodeBench] {t['id']}: {status_str} ({entry.get('latency_sec', 0)}s, {entry.get('tok_per_sec', 0)} t/s)", flush=True)
            continue

        instruct_prompt = f"""Complete the following Python function. Return ONLY the completed Python function inside a ```python ... ``` block.

{t['prompt']}
"""
        q = query_ollama(model, instruct_prompt, raw=False, num_predict=512)
        code = extract_code(q["response"], t["prompt"], lang="python")
        test_harness = f"{t['test']}\n\nif __name__ == '__main__':\n    import unittest\n    unittest.main(exit=False)\n"
        ok, msg = run_python_test(code, test_harness, timeout=12)

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

        mem = get_memory_stats()
        status_str = "PASS" if ok else "FAIL"
        print(f"[{idx}/{len(tasks)}] [BigCodeBench] {t['id']}: {status_str} ({q['latency_sec']}s, {q['tok_per_sec']} t/s) {mem['tag']}", flush=True)

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

# ─── Benchmark 4: SantaCoder FIM (250 Tasks) ─────────────────────────────────

def eval_santacoder_fim(model: str, limit: int = DEFAULT_QUOTA_FIM, cache: dict = None, cache_file: pathlib.Path = None) -> dict:
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
            total_speed += entry.get("tok_per_sec", 0.0)
            total_latency += entry.get("latency_sec", 0.0)
            status_str = "PASS (Cached)" if entry["passed"] else "FAIL (Cached)"
            print(f"[{idx}/{len(tasks)}] [FIM-{t['lang'].upper()}] {t['id']}: {status_str} ({entry.get('latency_sec', 0)}s, {entry.get('tok_per_sec', 0)} t/s)", flush=True)
            continue

        if is_codellama:
            fim_prompt = f"<PRE> {t['prefix']} <SUF>{t['suffix']} <MID>"
            stops = ["<EOT>", "\n\n"]
        else:
            fim_prompt = f"<|fim_prefix|>{t['prefix']}<|fim_suffix|>{t['suffix']}<|fim_middle|>"
            stops = ["<|endoftext|>", "<|file_separator|>", "\n\n"]

        q = query_ollama(model, fim_prompt, raw=True, stop_tokens=stops, num_predict=256)
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

        mem = get_memory_stats()
        status_str = "PASS" if ok else "FAIL"
        print(f"[{idx}/{len(tasks)}] [FIM-{t['lang'].upper()}] {t['id']}: {status_str} ({q['latency_sec']}s, {q['tok_per_sec']} t/s) {mem['tag']}", flush=True)

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

# ─── Benchmark 5: CRUXEval (250 Tasks) ───────────────────────────────────────

def eval_cruxeval(model: str, limit: int = DEFAULT_QUOTA_CRUX, cache: dict = None, cache_file: pathlib.Path = None) -> dict:
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
            total_speed += entry.get("tok_per_sec", 0.0)
            total_latency += entry.get("latency_sec", 0.0)
            status_str = "PASS (Cached)" if entry["passed"] else "FAIL (Cached)"
            print(f"[{idx}/{len(tasks)}] [CRUXEval] {t['id']}: {status_str} ({entry.get('latency_sec', 0)}s, {entry.get('tok_per_sec', 0)} t/s)", flush=True)
            continue

        prompt = f"""Given the following Python code and input, what does the function call return? Return ONLY the exact output value (e.g. an integer, string, or list), with no extra text or markdown.

{t['code']}

Output of f({t['input']}):"""

        q = query_ollama(model, prompt, raw=False, num_predict=64)
        pred_raw = q["response"].strip()
        # Clean potential markdown formatting
        pred_clean = re.sub(r"^```\w*\s*", "", pred_raw).strip()
        pred_clean = re.sub(r"\s*```$", "", pred_clean).strip().strip("'\"`")

        target_str = str(t["output"]).strip()
        target_clean = target_str.strip("'\"`")
        ok = False
        if pred_clean == target_clean or repr(pred_clean) == repr(target_clean):
            ok = True
        else:
            try:
                val_pred = ast.literal_eval(pred_clean)
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
            "error_msg": f"Pred: {pred_clean} != Expected: {target_clean}" if not ok else ""
        }
        cache[task_key] = entry
        results.append(entry)
        if cache_file:
            save_cache(cache_file, cache)

        mem = get_memory_stats()
        status_str = "PASS" if ok else "FAIL"
        print(f"[{idx}/{len(tasks)}] [CRUXEval] {t['id']}: {status_str} ({q['latency_sec']}s, {q['tok_per_sec']} t/s) {mem['tag']}", flush=True)

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

# ─── Full Single Model Evaluator ────────────────────────────────────────────

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

    mem_init = get_memory_stats()
    print(f"\n=======================================================", flush=True)
    print(f"EVALUATING MODEL: {model} {mem_init['tag']}", flush=True)
    print(f"=======================================================", flush=True)

    # Quota calculations
    he_lim = sample_limit if sample_limit else QUOTA_HUMANEVAL
    js_lim = sample_limit if sample_limit else QUOTA_MULTIP_JS
    ts_lim = sample_limit if sample_limit else QUOTA_MULTIP_TS
    bcb_lim = sample_limit if sample_limit else DEFAULT_QUOTA_BCB
    fim_lim = sample_limit if sample_limit else DEFAULT_QUOTA_FIM
    crux_lim = sample_limit if sample_limit else DEFAULT_QUOTA_CRUX

    # 1. Official OpenAI HumanEval (164 tasks)
    res_he = eval_openai_humaneval(model, limit=he_lim, cache=cache, cache_file=cache_file)

    # 2. MultiPL-E JavaScript (161 tasks) & TypeScript (159 tasks)
    res_js = eval_multipl_e(model, "js", limit=js_lim, cache=cache, cache_file=cache_file)
    res_ts = eval_multipl_e(model, "ts", limit=ts_lim, cache=cache, cache_file=cache_file)

    # 3. BigCodeBench (250 tasks)
    res_bcb = eval_bigcodebench(model, limit=bcb_lim, cache=cache, cache_file=cache_file)

    # 4. SantaCoder FIM (250 tasks)
    res_fim = eval_santacoder_fim(model, limit=fim_lim, cache=cache, cache_file=cache_file)

    # 5. CRUXEval (250 tasks)
    res_crux = eval_cruxeval(model, limit=crux_lim, cache=cache, cache_file=cache_file)

    # Combined MultiPL-E
    multi_total = res_js["total"] + res_ts["total"]
    multi_passed = res_js["passed"] + res_ts["passed"]
    multi_rate = round(multi_passed / multi_total * 100, 2) if multi_total > 0 else 0.0

    # Grand Total Across All 5 Benchmarks
    all_total = res_he["total"] + multi_total + res_bcb["total"] + res_fim["total"] + res_crux["total"]
    all_passed = res_he["passed"] + multi_passed + res_bcb["passed"] + res_fim["passed"] + res_crux["passed"]
    overall_score = round(all_passed / all_total * 100, 2) if all_total > 0 else 0.0

    # Speed & Latency Averages
    valid_speeds = [v["tok_per_sec"] for v in cache.values() if 0 < v.get("tok_per_sec", 0) < 450]
    valid_lats = [v["latency_sec"] for v in cache.values() if v.get("latency_sec", 0) > 0]
    clean_speed = round(sum(valid_speeds) / len(valid_speeds), 2) if valid_speeds else 0.0
    clean_latency = round(sum(valid_lats) / len(valid_lats), 2) if valid_lats else 0.0

    mem_end = get_memory_stats()

    summary = {
        "model": model,
        "overall_score": overall_score,
        "total_tasks": all_total,
        "passed_tasks": all_passed,
        "humaneval_official": res_he["pass_rate"],
        "multipl_e_js": res_js["pass_rate"],
        "multipl_e_ts": res_ts["pass_rate"],
        "multipl_e_combined": multi_rate,
        "bigcodebench": res_bcb["pass_rate"],
        "santacoder_fim": res_fim["pass_rate"],
        "cruxeval": res_crux["pass_rate"],
        "avg_speed_tps": clean_speed,
        "avg_latency_sec": clean_latency,
        "ram_used_gb": mem_end["ram_used_gb"],
        "vram_used_gb": mem_end["vram_used_gb"]
    }

    sum_file = RESULTS_DIR / f"{sanitized}_summary.json"
    sum_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return summary

# ─── Markdown Report Generator ──────────────────────────────────────────────

def generate_markdown_report(phase1_results: list[dict], scaling_results: list[dict] = None) -> str:
    md = f"""# CodeDEE Comprehensive Multi-Benchmark Evaluation & Scaling Report

> **Evaluation Protocol:** Standard Academic Instruct Protocol (ChatML Template + Robust Code Extractor)  
> **Hardware:** NVIDIA GeForce RTX 5080 Laptop GPU (16 GB VRAM)  
> **Runtime Environment:** Managed Python 3.12, Node.js v24 (Native TypeScript Stripping)  
> **Total Evaluated Tasks per Model:** Up to 1,234 tasks across 5 academic benchmarks:  
> 1. **OpenAI HumanEval (Official):** 164 Python algorithmic tasks  
> 2. **MultiPL-E (JS & TS):** 161 JavaScript & 159 TypeScript tasks  
> 3. **BigCodeBench:** 250 tasks across 139 Python engineering libraries  
> 4. **SantaCoder FIM:** 250 bidirectional infilling tasks across Python & JavaScript  
> 5. **CRUXEval:** 250 code execution reasoning tasks  

---

## 1. Ranked Multi-Benchmark Leaderboard (Phase 1 Screening)

| Rank | Model Name | Overall Score | OpenAI HumanEval | MultiPL-E (JS) | MultiPL-E (TS) | BigCodeBench | FIM (Infill) | CRUXEval | Speed (Tokens/s) | Latency (s) | RAM Used | VRAM Footprint |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
"""

    sorted_models = sorted(phase1_results, key=lambda x: x["overall_score"], reverse=True)
    for idx, m in enumerate(sorted_models, 1):
        ram_str = f"{m.get('ram_used_gb', 0)} GB"
        vram_str = f"{m.get('vram_used_gb', 0)} GB"
        md += f"| **#{idx}** | **`{m['model']}`** | **{m['overall_score']:.1f}%** | **{m['humaneval_official']:.1f}%** | {m['multipl_e_js']:.1f}% | {m['multipl_e_ts']:.1f}% | {m['bigcodebench']:.1f}% | {m['santacoder_fim']:.1f}% | {m['cruxeval']:.1f}% | **{m['avg_speed_tps']:.1f} t/s** | **{m['avg_latency_sec']:.2f}s** | {ram_str} | {vram_str} |\n"

    md += """
---

## 2. Benchmark Breakdown & Empirical Capabilities

1. **OpenAI HumanEval (164 tasks):** Standard Python algorithmic problem-solving under official academic zero-shot Pass@1 conditions.
2. **MultiPL-E JavaScript & TypeScript (320 tasks):** Cross-lingual polyglot performance verifying type safety and ecosystem consistency in modern web runtimes.
3. **BigCodeBench (250 tasks):** Real-world library API orchestration across 139 packages (`pandas`, `requests`, `cryptography`, `numpy`), measuring practical software engineering.
4. **SantaCoder FIM (250 tasks):** Bidirectional infilling evaluating the model's ability to insert patches between existing prefixes and suffixes.
5. **CRUXEval (250 tasks):** Execution simulation testing whether the model accurately models runtime execution state rather than merely pattern-matching tokens.

---
"""

    if scaling_results:
        md += """## 3. Phase 2: Winning Architecture Family Scaling Ladder (Pareto Trade-Off)

| Model Scale | Overall Score | OpenAI HumanEval | MultiPL-E (JS / TS) | Speed (Tokens/s) | Latency (s) | RAM Used | VRAM Footprint | Efficiency Trade-Off |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
"""
        for m in scaling_results:
            ram_str = f"{m.get('ram_used_gb', 0)} GB"
            vram_str = f"{m.get('vram_used_gb', 0)} GB"
            p_scores = f"{m['multipl_e_js']:.1f}% / {m['multipl_e_ts']:.1f}%"
            md += f"| **`{m['model']}`** | **{m['overall_score']:.1f}%** | **{m['humaneval_official']:.1f}%** | {p_scores} | **{m['avg_speed_tps']:.1f} t/s** | **{m['avg_latency_sec']:.2f}s** | {ram_str} | {vram_str} | Evaluated |\n"

        md += """
### Pareto Scaling Analysis:
* **Speed vs. Accuracy:** Quantifies throughput degradation per percentage point of functional accuracy gained.
* **VRAM Saturation:** Identifies the hardware boundary on the RTX 5080 Laptop GPU where parameter weights fit entirely in GPU VRAM vs. requiring system RAM offloading.
"""

    report_path = RESULTS_DIR / "comprehensive_benchmark_report.md"
    report_path.write_text(md, encoding="utf-8")
    print(f"\n[Report Generated] Saved report to {report_path}", flush=True)
    return md

# ─── Master Sequential Pipeline ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CodeDEE Master Benchmark Runner")
    parser.add_argument("--limit", type=int, default=None, help="Optional sample limit per benchmark (e.g. 10)")
    parser.add_argument("--skip-phase2", action="store_true", help="Skip Phase 2 scaling ladder")
    args = parser.parse_args()

    print("=" * 75, flush=True)
    print("CodeDEE Master Benchmark Runner: Standard Academic Instruct Protocol", flush=True)
    print("Evaluating 5 Benchmarks: HumanEval, MultiPL-E (JS/TS), BigCodeBench, FIM, CRUXEval", flush=True)
    print("=" * 75, flush=True)

    # Pre-flight check: Verify Ollama is reachable
    try:
        urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5)
    except Exception:
        print("\n[ERROR] Unable to reach Ollama at http://127.0.0.1:11434.", flush=True)
        print("Please launch the Ollama app or run 'ollama serve' in another terminal, then restart this script.\n", flush=True)
        sys.exit(1)

    # Phase 1: Candidate Architectures Sequentially
    phase1_summaries = []
    for idx, model in enumerate(PHASE_1_MODELS, 1):
        print(f"\n>>> [Phase 1: Model {idx}/{len(PHASE_1_MODELS)}] Evaluating {model}...", flush=True)
        summary = evaluate_single_model(model, sample_limit=args.limit)
        phase1_summaries.append(summary)

        # Update live leaderboard
        lb_file = RESULTS_DIR / "leaderboard.json"
        lb_file.write_text(json.dumps(phase1_summaries, indent=2), encoding="utf-8")
        df_lb = pd.DataFrame(phase1_summaries)
        df_lb.to_csv(RESULTS_DIR / "leaderboard.csv", index=False)
        generate_markdown_report(phase1_summaries)

    # Determine Winner
    sorted_p1 = sorted(phase1_summaries, key=lambda x: x["overall_score"], reverse=True)
    winner = sorted_p1[0]["model"]
    print(f"\n" + "=" * 75, flush=True)
    print(f"PHASE 1 COMPLETE: Top Architecture Winner is '{winner}' ({sorted_p1[0]['overall_score']:.1f}%)", flush=True)
    print("=" * 75, flush=True)

    # Phase 2: Family Scaling Ladder
    scaling_summaries = []
    if not args.skip_phase2:
        if "qwen" in winner.lower():
            family_models = SCALING_LADDER_QWEN
        else:
            family_models = [winner]

        print(f"\n>>> [Phase 2: Family Scaling Ladder] Evaluating family: {family_models}", flush=True)
        for s_model in family_models:
            existing = [s for s in phase1_summaries if s["model"] == s_model]
            if existing:
                print(f"[Phase 2] Using Phase 1 results for {s_model}", flush=True)
                scaling_summaries.append(existing[0])
            else:
                print(f"[Phase 2] Evaluating scaling model: {s_model}...", flush=True)
                s_sum = evaluate_single_model(s_model, sample_limit=args.limit)
                scaling_summaries.append(s_sum)

        generate_markdown_report(phase1_summaries, scaling_summaries)

    print("\n" + "=" * 75, flush=True)
    print("ALL BENCHMARKS & ALL MODELS COMPLETE!", flush=True)
    print(f"Results Report -> {RESULTS_DIR / 'comprehensive_benchmark_report.md'}", flush=True)
    print(f"Leaderboard CSV -> {RESULTS_DIR / 'leaderboard.csv'}", flush=True)
    print("=" * 75, flush=True)

if __name__ == "__main__":
    main()
