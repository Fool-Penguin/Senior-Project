## 2026-11-01T08:52:47Z
Sender: cdd4c46b-fa83-40b4-992f-7161af706ca8

You are survey_explorer_3, an exploration agent for CodeDEE.
Your working directory is: d:\4th-year\Senior-Project\.agents\teamwork\explorer_survey_3
You MUST read the original request file first: d:\4th-year\Senior-Project\.agents\teamwork\ORIGINAL_REQUEST.md

Your mission is Phase 0 Survey for R3 (Neuro-Symbolic Audit & In-Memory Multi-Gate Verifier) and R4 (VS Code Extension):
1. ChromaDB Knowledge Base (R3):
   - Check local ChromaDB installation and API compatibility.
   - Design `codedee_server/data/mini_test_knowledges.json` schema and initial seed entries for CWE-89 (descriptions, patterns, parameterized query sanitizers across Python sqlite3/psycopg2, JS pg/mysql2, TS TypeORM/Prisma).
   - Design seeding and vector retrieval logic.
2. Program Slicer & Neural Oracle (R3):
   - Design CST-based Program Slicer extracting full function/method enclosing source and sink.
   - Design Neural Oracle interface with local Ollama (`qwen2.5-coder:7b`): prompt engineering for assessment (confidence_score, risk_level, sanitizer_detected, reasoning) and patch generation (producing 3-4 candidate patches).
3. In-Memory Multi-Gate Verifier (R3):
   - Define exact validation logic for each gate on patch candidates:
     Gate 1: CST syntax validity check (detect tree-sitter ERROR nodes).
     Gate 2: Interface preservation check (function name and parameters unchanged).
     Gate 3: Taint sink neutralization check (string concatenation / raw string formatting eliminated from sink).
     Gate 4: Maintainability non-regression check (delta CC <= 0).
     Gate 6: SAST re-scan check (zero new flaws).
   - Design candidate filtering pipeline returning only 100% verified patches.
4. VS Code Extension Architecture (R4):
   - Design `codedee_extension/` directory structure, `package.json`, `tsconfig.json`.
   - Design configuration (`codedee.serverUrl`, default `http://127.0.0.1:8000`).
   - Design Command `CodeDEE: Scan Current File / Project`.
   - Design interactive Webview Panel (HTML/CSS/JS) showing issues, taint path, reasoning, and `[Request AI Patches]` button.
   - Design Diff Viewer using VS Code API (`vscode.diff`) and `[Apply Patch]` invoking `/api/apply-patch`.
5. Document all findings, schemas, prompt templates, and code designs in:
   `d:\4th-year\Senior-Project\.agents\teamwork\explorer_survey_3\survey_r3_r4.md` and `d:\4th-year\Senior-Project\.agents\teamwork\explorer_survey_3\handoff.md`.
6. Send a completion message to your parent orchestrator with a summary of findings.
