# CodeDEE Evaluation Dataset Versions (`datasets/combined/`)

This directory contains **4 explicit versions** of the CodeDEE security evaluation dataset plus **Meta's PurpleLlama CyberSecEval external benchmark**, so you can run benchmarks on any specific version via `--dataset v1|v2|v3|v4|cyberseceval` (or pass a custom path).

| Version | Filename | Total Samples | Vulnerable (`is_vulnerable=true`) | Safe Controls (`CWE-NONE`) | Code Length Filter | CWE Scope | Purpose |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| **V1** | `dataset_v1_raw_unfiltered_1208.jsonl` | **1208** | 1208 | 0 | Unfiltered (8 chars to 17.3M chars) | All raw CWEs (including out-of-scope) | Raw baseline before any cleaning |
| **V2** | `dataset_v2_filtered_30to4000_vuln_only_928.jsonl` | **928** | 928 | 0 | `30 <= len <= 4,000` chars (~1–80 lines) | Official 28 Taxonomy CWEs (27 unique IDs) | Single-function clean benchmark (also saved as `dataset.jsonl`) |
| **V3** | `dataset_v3_multifunc_30to20000_vuln_only_967.jsonl` | **967** | 967 | 0 | `30 <= len <= 20,000` chars (up to ~320 lines) | Official 28 Taxonomy CWEs (27 unique IDs) | **Multi-function benchmark** (retains 39 real-world multi-function files up to ~320 lines while removing >20k char repo dumps) |
| **V4** | `dataset_v4_multifunc_with_safe_patches_1911.jsonl` | **1911** | 967 | **944** | `30 <= len <= 20,000` chars (up to ~320 lines) | Official 28 Taxonomy CWEs + `CWE-NONE` | **Paired Vulnerable + Safe Patch Benchmark** (evaluates True Positives, False Positives, True Negatives, and False Negatives) |
| **CyberSecEval** | `dataset_cyberseceval_external_507.jsonl` | **507** | 507 | 0 | `30 <= len <= 20,000` chars | Official 28 Taxonomy CWEs (Python & JS) | **External Validation Benchmark** extracted from Meta's PurpleLlama CyberSecEval real-world repository corpus |

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

# Run External Meta PurpleLlama CyberSecEval Benchmark (507 Python/JS samples)
python scripts/run_full_scale_benchmark.py --dataset cyberseceval --checkpoint-tag run_cyberseceval
```
