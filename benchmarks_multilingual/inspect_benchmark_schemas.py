import pandas as pd
import json
import pathlib

BENCH_DIR = pathlib.Path(__file__).parent / "datasets"

print("--- MultiPL-E JS Sample ---")
df_js = pd.read_parquet(BENCH_DIR / "humaneval-js.parquet")
row_js = df_js.iloc[0]
print("Name:", row_js['name'])
print("Stop tokens:", row_js['stop_tokens'])
print("Prompt:\n", row_js['prompt'][:200])
print("Tests:\n", row_js['tests'][:200])

print("\n--- MultiPL-E TS Sample ---")
df_ts = pd.read_parquet(BENCH_DIR / "humaneval-ts.parquet")
row_ts = df_ts.iloc[0]
print("Name:", row_ts['name'])
print("Stop tokens:", row_ts['stop_tokens'])
print("Prompt:\n", row_ts['prompt'][:200])
print("Tests:\n", row_ts['tests'][:200])

print("\n--- BigCodeBench Sample ---")
df_bcb = pd.read_parquet(BENCH_DIR / "bigcodebench.parquet")
row_bcb = df_bcb.iloc[0]
print("Task ID:", row_bcb['task_id'])
print("Complete Prompt:\n", row_bcb['complete_prompt'][:200])
print("Canonical Solution:\n", row_bcb['canonical_solution'][:150])
print("Test:\n", row_bcb.get('test', '')[:150])

print("\n--- SantaCoder FIM Sample ---")
df_fim = pd.read_parquet(BENCH_DIR / "santacoder_fim.parquet")
print("FIM languages:", df_fim['language'].value_counts().to_dict())
row_fim = df_fim.iloc[0]
print("FIM Lang:", row_fim['language'])
print("Prefix:\n", row_fim['prompt'][:100])
print("Suffix:\n", row_fim['suffix'][:100])
print("Canonical:\n", row_fim['canonical_solution'][:100])

print("\n--- CRUXEval Sample ---")
with open(BENCH_DIR / "cruxeval.jsonl", "r", encoding="utf-8") as f:
    crux0 = json.loads(f.readline())
print("ID:", crux0['id'])
print("Code:\n", crux0['code'][:100])
print("Input:", crux0['input'])
print("Output:", crux0['output'])
