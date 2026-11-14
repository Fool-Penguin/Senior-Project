"""
CodeDEE - Dataset Version Builder
Generates the 4 official benchmark dataset versions in datasets/combined/
with self-documenting filenames and a companion DATASETS_VERSIONS_README.md.

Versions:
- Version 1: dataset_v1_raw_unfiltered_1208.jsonl
  (Original 1,208 samples before cleaning)
- Version 2: dataset_v2_filtered_30to4000_vuln_only_928.jsonl
  (928 samples: 30 <= len(code) <= 4,000 chars, 28 Taxonomy CWEs, 100% vulnerable)
- Version 3: dataset_v3_multifunc_30to20000_vuln_only_967.jsonl
  (967 samples: 30 <= len(code) <= 20,000 chars / up to ~320 lines to preserve multi-function code, 28 Taxonomy CWEs, 100% vulnerable)
- Version 4: dataset_v4_multifunc_with_safe_patches_1911.jsonl
  (1,911 samples: All 967 vulnerable samples from Version 3 + 944 distinct developer-patched safe code negative controls labeled as CWE-NONE / is_vulnerable=false)
"""

import json
import pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).parent.parent
COMBINED_DIR = ROOT / "datasets" / "combined"


def main():
    bak_path = COMBINED_DIR / "dataset.jsonl.bak"
    kb_path = COMBINED_DIR / "knowledge_base.jsonl"

    with open(bak_path, "r", encoding="utf-8") as f:
        v1_rows = [json.loads(line) for line in f if line.strip()]

    with open(kb_path, "r", encoding="utf-8") as f:
        kb_rows = [json.loads(line) for line in f if line.strip()]

    tax_cwes = {r["cwe_id"] for r in kb_rows}

    # 1. Version 1: Full raw 1,208 samples before cleaning
    v1_path = COMBINED_DIR / f"dataset_v1_raw_unfiltered_{len(v1_rows)}.jsonl"
    with open(v1_path, "w", encoding="utf-8") as f:
        for r in v1_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 2. Version 2: Filtered 30 <= len <= 4000, 28 Taxonomy CWEs, vulnerable only (928 samples)
    v2_rows = [
        r
        for r in v1_rows
        if r.get("cwe_id") in tax_cwes
        and 30 <= len(r.get("original_code", "")) <= 4000
    ]
    v2_path = COMBINED_DIR / f"dataset_v2_filtered_30to4000_vuln_only_{len(v2_rows)}.jsonl"
    with open(v2_path, "w", encoding="utf-8") as f:
        for r in v2_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 3. Version 3: Multi-function 30 <= len <= 20000 (~320 lines), 28 Taxonomy CWEs, vulnerable only (967 samples)
    v3_rows = [
        r
        for r in v1_rows
        if r.get("cwe_id") in tax_cwes
        and 30 <= len(r.get("original_code", "")) <= 20000
    ]
    v3_path = COMBINED_DIR / f"dataset_v3_multifunc_30to20000_vuln_only_{len(v3_rows)}.jsonl"
    with open(v3_path, "w", encoding="utf-8") as f:
        for r in v3_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 4. Version 4: Version 3 + Safe Patched Negative Controls (967 vulnerable + 944 safe = 1,911 samples)
    v4_rows = []
    safe_count = 0
    for r in v3_rows:
        v4_rows.append(r)
        fixed = r.get("fixed_code", "")
        orig = r.get("original_code", "")
        if fixed and 30 <= len(fixed.strip()) <= 20000 and fixed.strip() != orig.strip():
            safe_entry = dict(r)
            safe_entry["sample_id"] = f"{r['sample_id']}_SAFE_PATCHED"
            safe_entry["is_vulnerable"] = False
            safe_entry["ground_truth_fixed_cwe"] = r["cwe_id"]
            safe_entry["cwe_id"] = "CWE-NONE"
            safe_entry["cwe_name"] = "Safe / Patched Code (Negative Control)"
            safe_entry["cwe_description"] = (
                f"Developer-patched safe version of {r['sample_id']} (mitigated {r['cwe_id']})"
            )
            safe_entry["original_code"] = fixed
            v4_rows.append(safe_entry)
            safe_count += 1

    v4_path = COMBINED_DIR / f"dataset_v4_multifunc_with_safe_patches_{len(v4_rows)}.jsonl"
    with open(v4_path, "w", encoding="utf-8") as f:
        for r in v4_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 5. External Dataset: Meta PurpleLlama CyberSecEval (filtered to Python/JS/TS & our 28 Taxonomy CWEs)
    import urllib.request
    url = "https://raw.githubusercontent.com/meta-llama/PurpleLlama/main/CybersecurityBenchmarks/datasets/instruct/instruct.json"
    print("Downloading Meta PurpleLlama CyberSecEval dataset...")
    data = json.loads(urllib.request.urlopen(url, timeout=30).read().decode("utf-8"))
    kb_map = {r["cwe_id"]: r for r in kb_rows}

    cyber_rows = []
    for item in data:
        lang = str(item.get("language", "")).lower()
        cwe = str(item.get("cwe_identifier", "")).upper()
        code = str(item.get("origin_code", "")).strip()
        if lang in ("python", "javascript", "typescript") and cwe in kb_map and 30 <= len(code) <= 20000:
            kb_ref = kb_map[cwe]
            cyber_rows.append(
                {
                    "sample_id": f"CYBERSECEVAL_{item.get('prompt_id')}_{item.get('pattern_id')}",
                    "language": lang,
                    "is_vulnerable": True,
                    "cwe_id": cwe,
                    "cwe_name": kb_ref.get("cwe_name", ""),
                    "cwe_description": item.get("pattern_desc", kb_ref.get("cwe_description", "")),
                    "owasp_category": kb_ref.get("owasp_category", ""),
                    "original_sources": [
                        f"cyberseceval:{item.get('repo', '')}:{item.get('file_path', '')}:{item.get('line_number', '')}"
                    ],
                    "source_pattern": item.get("file_path", ""),
                    "sink_pattern": item.get("line_text", "").strip(),
                    "sanitizer_pattern": kb_ref.get("sanitizer_pattern", ""),
                    "original_code": code,
                    "fixed_code": "",
                    "catalogue_id": kb_ref.get("catalogue_id", ""),
                    "split": "cyberseceval",
                    "split_reason": "meta_purplellama_cyberseceval",
                }
            )

    cyber_path = COMBINED_DIR / f"dataset_cyberseceval_external_{len(cyber_rows)}.jsonl"
    with open(cyber_path, "w", encoding="utf-8") as f:
        for r in cyber_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Write README explaining the dataset versions clearly
    readme_path = COMBINED_DIR / "DATASETS_VERSIONS_README.md"
    readme_content = f"""# CodeDEE Evaluation Dataset Versions (`datasets/combined/`)

This directory contains **4 explicit versions** of the CodeDEE security evaluation dataset plus **Meta's PurpleLlama CyberSecEval external benchmark**, so you can run benchmarks on any specific version via `--dataset v1|v2|v3|v4|cyberseceval` (or pass a custom path).

| Version | Filename | Total Samples | Vulnerable (`is_vulnerable=true`) | Safe Controls (`CWE-NONE`) | Code Length Filter | CWE Scope | Purpose |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| **V1** | `{v1_path.name}` | **{len(v1_rows)}** | {len(v1_rows)} | 0 | Unfiltered (8 chars to 17.3M chars) | All raw CWEs (including out-of-scope) | Raw baseline before any cleaning |
| **V2** | `{v2_path.name}` | **{len(v2_rows)}** | {len(v2_rows)} | 0 | `30 <= len <= 4,000` chars (~1–80 lines) | Official 28 Taxonomy CWEs (27 unique IDs) | Single-function clean benchmark (also saved as `dataset.jsonl`) |
| **V3** | `{v3_path.name}` | **{len(v3_rows)}** | {len(v3_rows)} | 0 | `30 <= len <= 20,000` chars (up to ~320 lines) | Official 28 Taxonomy CWEs (27 unique IDs) | **Multi-function benchmark** (retains 39 real-world multi-function files up to ~320 lines while removing >20k char repo dumps) |
| **V4** | `{v4_path.name}` | **{len(v4_rows)}** | {len(v3_rows)} | **{safe_count}** | `30 <= len <= 20,000` chars (up to ~320 lines) | Official 28 Taxonomy CWEs + `CWE-NONE` | **Paired Vulnerable + Safe Patch Benchmark** (evaluates True Positives, False Positives, True Negatives, and False Negatives) |
| **CyberSecEval** | `{cyber_path.name}` | **{len(cyber_rows)}** | {len(cyber_rows)} | 0 | `30 <= len <= 20,000` chars | Official 28 Taxonomy CWEs (Python & JS) | **External Validation Benchmark** extracted from Meta's PurpleLlama CyberSecEval real-world repository corpus |

## How to Run Each Version with `scripts/run_full_scale_benchmark.py`

```powershell
# Run Version 1 (Raw 1,208 samples)
python scripts/run_full_scale_benchmark.py --dataset v1 --checkpoint-tag run_v1

# Run Version 2 (Filtered 30..4000 chars, 928 vulnerable samples)
python scripts/run_full_scale_benchmark.py --dataset v2 --checkpoint-tag run_v2

# Run Version 3 (Multi-function 30..20000 chars, 967 vulnerable samples)
python scripts/run_full_scale_benchmark.py --dataset v3 --checkpoint-tag run_v3

# Run Version 4 (Multi-function + Safe Patched Controls, 1,911 total samples)
python scripts/run_full_scale_benchmark.py --dataset v4 --checkpoint-tag run_v4

# Run External Meta PurpleLlama CyberSecEval Benchmark ({len(cyber_rows)} Python/JS samples)
python scripts/run_full_scale_benchmark.py --dataset cyberseceval --checkpoint-tag run_cyberseceval
```
"""
    readme_path.write_text(readme_content, encoding="utf-8")
    print(f"Successfully generated all dataset versions and {readme_path.name}:")
    print(f"  V1: {v1_path.name} ({len(v1_rows)} samples)")
    print(f"  V2: {v2_path.name} ({len(v2_rows)} samples)")
    print(f"  V3: {v3_path.name} ({len(v3_rows)} samples)")
    print(f"  V4: {v4_path.name} ({len(v4_rows)} samples: {len(v3_rows)} vuln + {safe_count} safe)")
    print(f"  CyberSecEval: {cyber_path.name} ({len(cyber_rows)} samples)")


if __name__ == "__main__":
    main()
