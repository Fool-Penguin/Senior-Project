# Dispatch for Explorer Survey 1
Investigate R1 (Monorepo Scaffolding & Backend Architecture, Dataset extraction, Ollama environment).
See prompt for full details.

## 2026-11-01T08:52:23Z
You are survey_explorer_1, an exploration agent for CodeDEE.
Your working directory is: d:\4th-year\Senior-Project\.agents\teamwork\explorer_survey_1
You MUST read the original request file first: d:\4th-year\Senior-Project\.agents\teamwork\ORIGINAL_REQUEST.md

Your mission is Phase 0 Survey for R1 (Monorepo Scaffolding & Backend Architecture) and Environment:
1. Examine `D:\4th-year\Senior-Project\datasets\unified\codedee_security_dataset_catalogue_scope.json`:
   - Inspect its structure, JSON format, schema, and size.
   - Determine how to filter records for `cwe_id == 'CWE-89'`.
   - How many CWE-89 samples exist, and across which languages (Python, JS, TS)?
   - Verify the exact 14 columns: `sample_id`, `language`, `Is_vulnerable`, `cwe_id`, `cwe_name`, `cwe_description`, `owasp_category`, `cvss_v31_vector`, `sources`, `source_pattern`, `sink_pattern`, `sanitizer_pattern`, `original_code`, `fixed_code`.
   - Provide concrete code snippet/logic for extracting `codedee_server/data/mini_test_datasets.json`.
2. Inspect environment capabilities & dependencies:
   - Check local Python version and whether `fastapi`, `uvicorn`, `pydantic`, `tree-sitter`, `tree-sitter-languages`, `networkx`, `chromadb`, `requests`, `pytest` are installed or can be installed.
   - Check Node.js and npm version in the environment.
   - Check Ollama reachability at `http://127.0.0.1:11434` / `http://localhost:11434`, list installed models, check if `qwen2.5-coder:7b` is present and functional.
3. Architecture & API specification for `codedee_server/`:
   - Design folder layout under `d:\4th-year\Senior-Project\codedee\codedee_server\`.
   - Define exact Pydantic schemas for the Stage 3B Security Node Output Contract (`issue_id`, `target_file`, `symbolic_finding`, `neuro_assessment`, `pipeline_metadata`).
   - Define REST API endpoint specifications: `GET /health`, `POST /api/scan`, `POST /api/generate-patches`, `POST /api/apply-patch`.
4. Document all findings, command outputs, schemas, and recommendations in:
   `d:\4th-year\Senior-Project\.agents\teamwork\explorer_survey_1\survey_r1.md` and `d:\4th-year\Senior-Project\.agents\teamwork\explorer_survey_1\handoff.md`.
5. Send a completion message to your parent orchestrator with a summary of findings.
