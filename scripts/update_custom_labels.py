import json
import csv
from pathlib import Path

path_json = Path("datasets/custom/custom_security_benchmark.json")
path_csv = Path("datasets/custom/custom_security_benchmark.csv")

with open(path_json, "r", encoding="utf-8") as f:
    records = json.load(f)

def resolve(entry):
    raw_src = entry.get("source_dataset") or entry.get("source_benchmark") or ""
    sid = entry.get("sample_id") or entry.get("id") or ""
    if "Meta-CyberSecEval-Instruct" in raw_src or sid.startswith("META_CYBERSEC"):
        return "meta_cyberseceval_instruct.json (Bhatt et al., 2024)"
    elif "CodeLens" in raw_src or sid.startswith(("SEC_PY_CWE", "SEC_JS_CWE", "SEC_TS_CWE", "SEC_PY_LLM", "SEC_JS_LLM")):
        return "benchmark_security_cwe_owasp.json (CodeLens Team Curated)"
    elif "Semgrep" in raw_src or sid.startswith("SEMGREP_"):
        return "opensource_benchmark_security.json (Semgrep Rule Test Suite)"
    elif "CVEfixes" in raw_src or sid.startswith(("CVEFIXES_", "SEC_PY_CVE_")):
        return "hitoshura25_cvefixes_all.parquet (Bhandari et al., MSR 2021)"
    elif "PyGoat" in raw_src or "PYGOAT" in sid:
        return "pygoat_mitre.py (OWASP PyGoat Project)"
    elif "Juice Shop" in raw_src or "JUICE" in sid:
        return "juice_shop_b2bOrder.ts (OWASP Juice Shop Project)"
    elif "BIPIA" in raw_src or "BIPIA" in sid:
        return "opensource_benchmark_security.json (Alibaba BIPIA Benchmark)"
    elif "CyberSecEval" in raw_src or "CYBERSEC" in sid:
        return "meta_cyberseceval_autocomplete.json (Bhatt et al., 2024)"
    else:
        return f"custom_security_benchmark.json ({raw_src or 'Curated'})"

for r in records:
    r["source_dataset"] = resolve(r)

with open(path_json, "w", encoding="utf-8") as f:
    json.dump(records, f, indent=2, ensure_ascii=False)

if path_csv.exists() and len(records) > 0:
    fieldnames = list(records[0].keys())
    with open(path_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(r)

print(f"Updated {len(records)} records in custom_security_benchmark.json and csv successfully!")
