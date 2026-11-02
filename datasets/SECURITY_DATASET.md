# CodeDEE security dataset and knowledge base

**What this is:** Task 2 work for comparing local LLMs (Qwen, Gemma, and others) on vulnerability detection.  
**Languages in scope:** Python, JavaScript, TypeScript.  
**Catalogue:** 28 types in `data/security_vulnerability_catalogue.yaml` (27 unique CWEs; CWE-200 is shared by LLM02 and LLM07).

This folder is **not** the older 170-repo docs/SBOM study. That pipeline lives on this branch under `security_analysis/` and is described in `security_analysis/README.md`. This file is only the **vuln/fixed-code dataset** used to test models.

---

## What was done

1. **Catalogue.** Friend’s YAML of 28 in-scope types (CWE + OWASP Web 2025 + OWASP LLM 2025 where it applies). Mapping is from this YAML, not from Hugging Face “LLM02” tags.
2. **Mine 170 sample repos.** GitHub Security Advisories (official GHSA, not Issues). 683 catalogue-scoped advisories in the status table; **74** parent/fix code pairs could be extracted.
3. **Download public pairs** that already have both vulnerable and fixed code:
   - Gift catalogue-scope dump: **879** with `fixed_code` (the 1891 file also has vuln-only rows; those were **not** used).
   - AppSecBench Py/JS/TS: **324**
   - SecureCodePairs Py/JS/TS: **107**
4. **Combine** into one schema: **1384** pairs in `datasets/combined/codedee_combined_pairs.jsonl`.
5. **Split for model eval (no overlap):**
   - **Knowledge base (cheat sheet):** `knowledge_base.jsonl` — **83** cards copied from the YAML (28 types × 3 languages, minus prototype-pollution Python). Paste into the prompt only in the “with KB” run. Never score these rows.
   - **Dataset (exam):** `dataset.jsonl` — **1208** pairs = the 1384 pool minus 67 KB examples minus 102 exact duplicate snippets. Score every model on these.

A snippet is never in both files. Overlap of dataset vs KB examples is **0**.

---

## How to test a model (Qwen, Gemma, …)

Use the **same** 1208 dataset rows for every model.

**Do not paste `security_vulnerability_catalogue.yaml` into the model.** That file is the human/script source (971 lines, including exclusions and academic justifications). We already extracted the in-scope types into `knowledge_base.jsonl`.

| Run | What you give the model | What you measure |
|---|---|---|
| **1. Pure model** | Only the snippet from `dataset.jsonl` + a short question: vulnerable or SAFE, and which CWE | What the model knows cold |
| **2. Prompt + KB** | Same snippet + **every** row in `knowledge_base.jsonl` whose `language` matches (27 or 28 cards). Not the `.yaml` file. Not only the gold CWE. | Whether catalogue context helps |

Score `original_code` as the vulnerable case. Optionally also score `fixed_code` and expect SAFE. Do not put dataset rows in the prompt.

---

## Why the exam is 1208, not 1384

`codedee_combined_pairs.jsonl` is the **pool** (1384). The exam is every remaining pair after the knowledge base takes its examples:

| Slice in `dataset.jsonl` | Count |
|---|---|
| GHSA | 74 |
| AppSecBench (test + validation + train) | 221 |
| SecureCodePairs (test + val + train + benchmark) | 80 |
| Gift | 833 |
| **Total exam** | **1208** |

67 short pairs are KB examples only (excluded from the exam). 102 other rows were dropped because they are exact duplicates of a snippet already in the exam or in the KB. “Train” in `split_reason` is only the original Hugging Face split name. We did **not** fine-tune Qwen on them. Columns are the same as every other exam row.

---

## CWE-200 (do not dump into both LLM02 and LLM07)

There are **61** CWE-200 pairs in the 1384:

| Kind | Count | How we tell them apart |
|---|---|---|
| LLM02 (sensitive data into context) | 11 | `catalogue_id = VULN-LLM-002` |
| LLM07 (system prompt leak) | 11 | `catalogue_id = VULN-LLM-007` |
| Generic web disclosure (neither) | 39 | `catalogue_id` empty |

Use `catalogue_id` / `owasp_llm`, not `cwe_id` alone.

---

## Still missing (not synthesized)

No vuln/fixed pair exists yet for:

- **CWE-328** (weak hash) — empty in Python, JS, and TS
- CWE-338 Python and TypeScript
- CWE-327 TypeScript
- CWE-611 XXE JavaScript
- CWE-209 JavaScript

KB still has a **definition** card for CWE-328. You cannot **score** 328 until a pair is written or mined. Existing synthetics (`SYN_LLM*`, `SYNTH-*`) only cover LLM02/LLM07.

---

## Start here (the two files you actually use)

| File | What it is |
|---|---|
| [`combined/dataset.jsonl`](combined/dataset.jsonl) | **Exam.** 1208 pairs. Score models on `original_code`. |
| [`combined/knowledge_base.jsonl`](combined/knowledge_base.jsonl) | **Extracted YAML.** 83 cards. This is what run 2 reads. |
| [`../data/security_vulnerability_catalogue.yaml`](../data/security_vulnerability_catalogue.yaml) | **Source catalogue.** Do not send this file to the model. |

`split_dataset_kb.py` reads the YAML and writes `knowledge_base.jsonl` (one card per type × language: CWE, OWASP, CVSS, source/sink/sanitizer, optional short example). Rebuild after changing the pool:

```bash
python3 datasets/combined/build_combined_pairs.py
python3 datasets/combined/split_dataset_kb.py
```

---

## File-by-file

### Catalogue (definitions)

| File | What it does |
|---|---|
| [`data/security_vulnerability_catalogue.yaml`](../data/security_vulnerability_catalogue.yaml) | Source of the 28 in-scope types (CWE, OWASP Web, OWASP LLM, CVSS, per-language patterns). **Not** the file you prompt with. |
| [`data/Taxonomy_table.csv`](../data/Taxonomy_table.csv) | Spreadsheet view of the same taxonomy. |
| [`data/Uncovered_Taxonomy_table.csv`](../data/Uncovered_Taxonomy_table.csv) | Types **out** of static-analysis scope (not in the 28). |

### Combined pool and split (this week)

| File | What it does |
|---|---|
| [`combined/build_combined_pairs.py`](combined/build_combined_pairs.py) | Merges Gift 879 + AppSec Py/JS/TS + SCP Py/JS/TS + GHSA 74 into one schema. Splits CWE-200 by `catalogue_id`. |
| [`combined/codedee_combined_pairs.jsonl`](combined/codedee_combined_pairs.jsonl) | The 1384-row pool. One object per vuln/fixed pair. ~117MB. |
| [`combined/codedee_combined_pairs.csv`](combined/codedee_combined_pairs.csv) | Same 1384 rows as CSV (Excel). Duplicate of the jsonl; you can skip this on GitHub if size is a problem. |
| [`combined/codedee_combined_summary.json`](combined/codedee_combined_summary.json) | Counts: sources, languages, CWE-200 split, in vs out of catalogue. |
| [`combined/split_dataset_kb.py`](combined/split_dataset_kb.py) | Builds the YAML knowledge base first, then puts every leftover pair into the exam. Strips `VULNERABLE`/`SECURE` comment leaks. Drops exact duplicate snippets. |
| [`combined/dataset.jsonl`](combined/dataset.jsonl) | 1208 exam pairs + `split` / `split_reason`. |
| [`combined/knowledge_base.jsonl`](combined/knowledge_base.jsonl) | Extracted KB: 83 cards from the YAML + optional short example from train/Gift, never from the exam. Give this to the model in run 2. |
| [`combined/split_summary.json`](combined/split_summary.json) | Split counts, overlap check (should be 0), empty CWE×language cells. |

**Schema of a pool/exam row:** `sample_id`, `language`, `is_vulnerable`, `cwe_id`, `cwe_name`, `cwe_description`, `owasp_category`, `cvss_v31_vector`, `original_sources`, `source_pattern`, `sink_pattern`, `sanitizer_pattern`, `original_code`, `fixed_code`, `catalogue_id`, `owasp_llm`.

**Schema of a KB card:** `kb_id` (`VULN-…:python`), definition fields above, plus `example_sample_id` / `example_original_code` / `example_fixed_code` (empty when no unused short example exists).

### Coverage tables

| File | What it does |
|---|---|
| [`benchmark/catalogue_coverage.csv`](benchmark/catalogue_coverage.csv) | Per catalogue type: how many pairs from Gift / AppSec / SCP / GHSA, and Py/JS/TS. `MISSING` = CWE-328. |
| [`benchmark/llm_coverage.csv`](benchmark/llm_coverage.csv) | OWASP LLM 2025 pair counts. Only LLM01, LLM02, LLM05, LLM07 are in the YAML; the other LLM types are excluded on purpose. |
| [`benchmark/coverage.json`](benchmark/coverage.json) | Machine-readable coverage. |
| [`benchmark/label_audit.csv`](benchmark/label_audit.csv) | Spot-check of source labels vs YAML mapping. |
| [`benchmark/cases.jsonl`](benchmark/cases.jsonl) | Small case list used while building coverage. |

### Gift (unified dump)

| File | What it does |
|---|---|
| [`build_unified_dataset.py`](build_unified_dataset.py) | Older builder for the Gift catalogue-scope JSON. |
| [`unified/codedee_security_dataset_catalogue_scope.json`](unified/codedee_security_dataset_catalogue_scope.json) | Gift dump: 1891 rows, of which **879 have `fixed_code`**. Only those 879 entered the 1384 pool. ~117MB. |
| [`unified/coverage_report.json`](unified/coverage_report.json) | Gift coverage vs catalogue. |
| [`unified/cat_stats.json`](unified/cat_stats.json) | Gift CWE counts. |

### GitHub mining (170 repos)

| File | What it does |
|---|---|
| [`mining/probe_ghsa_170.py`](mining/probe_ghsa_170.py) | Queries GitHub official advisory DB for the 170 sample repos (not Issues). |
| [`mining/ghsa_probe_170.json`](mining/ghsa_probe_170.json) | Raw probe output. |
| [`mining/ghsa_fix_status_170.csv`](mining/ghsa_fix_status_170.csv) | **683** catalogue-scoped advisories: whether a fix commit and code were found. This is why the CSV looks like “600+” not 74. |
| [`mining/ghsa_repo_cwe_fix_counts.csv`](mining/ghsa_repo_cwe_fix_counts.csv) | Per-repo CWE counts, with vs without extractable code. |
| [`mining/extract_ghsa_pairs.py`](../eval_qwen/extract_ghsa_pairs.py) | Turns status rows into parent/fix snippets. |
| [`mining/ghsa_eval_pairs.json`](mining/ghsa_eval_pairs.json) | **74** pairs (JSON). |
| [`mining/ghsa_eval_pairs.csv`](mining/ghsa_eval_pairs.csv) | Same 74 pairs (CSV). |

### Hugging Face downloads (Py/JS/TS only used in the pool)

| File | What it does |
|---|---|
| `appsecbench/{train,validation,test}.jsonl` | AppSecBench official splits. Only Python/JS/TS went into the 1384. |
| `securecodepairs/{train,validation,test,benchmark}.jsonl` | SecureCodePairs. Official splits; leftover rows after KB examples are in the 1208 exam. |
| `securecode/*.parquet` | SecureCode **conversations** (scthornton/securecode). **Not** in the 1384. License CC BY-NC-SA 4.0. Optional later as extra KB text only. |
| [`original/HumanEval.jsonl`](original/HumanEval.jsonl) | HumanEval (functional coding). Not part of the security exam. |

### Qwen eval already run (not the 1208 exam)

These tested **Qwen2.5-coder:7b via Ollama** on earlier slices (GHSA 74, AppSec, SCP). They are old results. Re-run on `dataset.jsonl` when comparing several models.

| File | What it does |
|---|---|
| [`eval_qwen/run_ghsa_eval.py`](../eval_qwen/run_ghsa_eval.py) | Asks Qwen: is the **parent** snippet vulnerable, which CWE. |
| [`eval_qwen/run_appsecbench.py`](../eval_qwen/run_appsecbench.py) | AppSecBench eval (detect + CWE). |
| [`eval_qwen/run_securecodepairs.py`](../eval_qwen/run_securecodepairs.py) | SecureCodePairs test split eval. |
| [`eval_qwen/run_benchmark.py`](../eval_qwen/run_benchmark.py) | Hand-built sparse-CWE + mixed benchmark. |
| [`eval_qwen/build_benchmark.py`](../eval_qwen/build_benchmark.py) | Builds that mixed benchmark file. |
| [`eval_qwen/handwritten_pairs.py`](../eval_qwen/handwritten_pairs.py) | Hand-written pairs for sparse CWEs (not CWE-328). |
| [`eval_qwen/results/qwen_final_parent_only.csv`](../eval_qwen/results/qwen_final_parent_only.csv) | Final GHSA-74 parent-only predictions. |
| [`eval_qwen/results/qwen_final_parent_only_summary.csv`](../eval_qwen/results/qwen_final_parent_only_summary.csv) | Headline: 74 snippets, flag-parent 39%, CWE-correct 15%, plus latency/RAM. |
| `eval_qwen/results/benchmark/` | AppSec / mixed / SCP run CSVs and JSON summaries. |

### CodeDEE engine (Tasks 5–6, not the LLM exam)

| File | What it does |
|---|---|
| `codedee/` | Metrics + Python graphs (CG/CFG/DFG) CLI. |
| `code_dee_eval/run_task5.py` | Task 5: CodeDEE vs Pylint/ESLint on real commits. |
| `code_dee_eval/run_task6.py` | Task 6: AST-only vs CG+CFG+DFG. |
| `code_dee_eval/CodeDEE_Tasks_5_6_7_Evaluation_Guide.md` | Task guide. Task 7 was skipped. |
| `code_dee_eval/CODEDEE_RECENT_WORK.md` | What was actually run for 5/6. |

Do **not** push `code_dee_eval/node_modules/`.

---

## What is huge / Git LFS

- `combined/knowledge_base.jsonl` is small (~95KB). Prompt with this, not the YAML.
- `combined/dataset.jsonl` is ~116MB (Gift dumps in the exam) — Git LFS.
- `combined/codedee_combined_pairs.jsonl` is ~117MB — Git LFS. The CSV duplicate is not needed on GitHub.
- Do **not** add `code_dee_eval/node_modules/`.
