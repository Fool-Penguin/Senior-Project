"""
Benchmark Dataset Downloader for MultiPL-E, BigCodeBench, FIM, and CRUXEval
"""

import os
import pathlib
import urllib.request
import json
import pandas as pd

ROOT = pathlib.Path(__file__).parent.parent
BENCH_DIR = ROOT / "benchmarks_multilingual" / "datasets"
BENCH_DIR.mkdir(parents=True, exist_ok=True)

URLS = {
    "humaneval-js.parquet": "https://huggingface.co/datasets/nuprl/MultiPL-E/resolve/refs%2Fconvert%2Fparquet/humaneval-js/test/0000.parquet",
    "humaneval-ts.parquet": "https://huggingface.co/datasets/nuprl/MultiPL-E/resolve/refs%2Fconvert%2Fparquet/humaneval-ts/test/0000.parquet",
    "bigcodebench.parquet": "https://huggingface.co/datasets/bigcode/bigcodebench/resolve/main/data/train-00000-of-00001.parquet",
    "santacoder_fim.parquet": "https://huggingface.co/datasets/bigcode/santacoder-fim-task/resolve/main/data/train-00000-of-00001-b6ec1fdd66018baa.parquet",
    "cruxeval.jsonl": "https://huggingface.co/datasets/cruxeval-org/cruxeval/raw/main/test.jsonl"
}

def download_file(url: str, dest: pathlib.Path):
    if dest.exists() and dest.stat().st_size > 1000:
        print(f"[Exists] {dest.name} ({dest.stat().st_size:,} bytes)")
        return
    print(f"[Downloading] {dest.name} from {url}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp, open(dest, "wb") as out:
        out.write(resp.read())
    print(f"[Done] Saved {dest.name} ({dest.stat().st_size:,} bytes)")

def main():
    print("=" * 60)
    print("Ingesting Official Benchmark Datasets")
    print("=" * 60)

    # 1. Download Remote Datasets
    for filename, url in URLS.items():
        dest = BENCH_DIR / filename
        download_file(url, dest)

    # 2. Link or Copy Local HumanEval.jsonl
    he_orig = ROOT / "datasets" / "original" / "HumanEval.jsonl"
    he_dest = BENCH_DIR / "humaneval-py.jsonl"
    if he_orig.exists():
        if not he_dest.exists() or he_dest.stat().st_size != he_orig.stat().st_size:
            he_dest.write_bytes(he_orig.read_bytes())
            print(f"[Copied] Local HumanEval.jsonl -> {he_dest.name} ({he_dest.stat().st_size:,} bytes)")
        else:
            print(f"[Exists] {he_dest.name} ({he_dest.stat().st_size:,} bytes)")
    else:
        print("[Warning] datasets/original/HumanEval.jsonl not found!")

    # 3. Inspect and verify each dataset
    print("\n--- Benchmark Dataset Verification ---")
    
    # Python HumanEval
    with open(he_dest, "r", encoding="utf-8") as f:
        py_tasks = [json.loads(l) for l in f if l.strip()]
    print(f"1. MultiPL-E Python (HumanEval): {len(py_tasks)} tasks")

    # JS MultiPL-E
    df_js = pd.read_parquet(BENCH_DIR / "humaneval-js.parquet")
    print(f"2. MultiPL-E JavaScript:        {len(df_js)} tasks (columns: {list(df_js.columns)})")

    # TS MultiPL-E
    df_ts = pd.read_parquet(BENCH_DIR / "humaneval-ts.parquet")
    print(f"3. MultiPL-E TypeScript:        {len(df_ts)} tasks (columns: {list(df_ts.columns)})")

    # BigCodeBench
    df_bcb = pd.read_parquet(BENCH_DIR / "bigcodebench.parquet")
    print(f"4. BigCodeBench:                {len(df_bcb)} tasks (columns: {list(df_bcb.columns)[:5]})")

    # SantaCoder FIM
    df_fim = pd.read_parquet(BENCH_DIR / "santacoder_fim.parquet")
    print(f"5. SantaCoder FIM:              {len(df_fim)} tasks (columns: {list(df_fim.columns)})")

    # CRUXEval
    with open(BENCH_DIR / "cruxeval.jsonl", "r", encoding="utf-8") as f:
        crux_tasks = [json.loads(l) for l in f if l.strip()]
    print(f"6. CRUXEval:                    {len(crux_tasks)} tasks (keys: {list(crux_tasks[0].keys())})")

    print("\nAll benchmark datasets successfully ingested and verified!")

if __name__ == "__main__":
    main()
