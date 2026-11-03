# Handoff Report: CST Program Slicer & Neural Oracle (Milestone 3)

## 1. Observation

1. **Tree-sitter CST Architecture**:
   - Location: `codedee/codedee_server/app/parser/cst_manager.py` (referenced as `app/graphs/cst.py` in dispatch prompt).
   - Singleton `CSTParserManager.get_instance()` provides grammars for `python`, `javascript`, `typescript`, and `tsx`.
   - Node extraction in `cst_manager.py` lines 240-252:
     ```python
     def get_functions(self, tree: tree_sitter.Tree, language: str) -> List[tree_sitter.Node]:
         norm = self.normalize_language(language)
         if norm == LanguageType.PYTHON.value:
             fn_types = {"function_definition"}
         else:
             fn_types = {
                 "function_declaration",
                 "function_expression",
                 "arrow_function",
                 "method_definition",
             }
         return self.find_all_by_type(tree.root_node, fn_types)
     ```
   - CST Structure Inspection via tree-sitter:
     - Python decorated functions: `@app.route('/login')\ndef login(): pass` produces root node `decorated_definition` wrapping `function_definition`. If row 0 is inspected, matching only `function_definition` can miss the route decorator.
     - JS/TS arrow functions: `const search = (req, res) => { ... }` produces `lexical_declaration` -> `variable_declarator` -> `arrow_function`. Slicing only `arrow_function` strips `const search =`, and its child identifier is empty while `variable_declarator.child_by_field_name('name')` holds the identifier `search`.
     - JS/TS exports: `export const handler = ...` wraps the declaration in `export_statement`.

2. **Existing Models & Contracts**:
   - Location: `codedee/codedee_server/app/models/contracts.py`.
   - `SymbolicFinding` (lines 94-124): Contains `cwe_id`, `source_node: Dict[str, Any]`, `sink_node: Dict[str, Any]`, `taint_path: List[Dict[str, Any]]`, `sanitized: bool`, `code_slice: Optional[str]`.
   - `NeuroAssessment` (lines 126-138): Contains `confidence_score: float` (0.0–1.0), `risk_level: str` (CRITICAL, HIGH, MEDIUM, LOW, SAFE), `sanitizer_detected: bool`, `sanitizer_details: Optional[str]`, `is_false_positive: bool`, `reasoning: str`, `flagged_for_review: bool`, `suggested_remediation: Optional[str]`.
   - `SecurityNodeOutput` (lines 168-182): Enforces complete Stage 3B payload (`issue_id`, `target_file`, `symbolic_finding`, `neuro_assessment`, `pipeline_metadata`).

3. **Current Program Slicer**:
   - Location: `codedee/codedee_server/app/slicer/program_slicer.py`.
   - Lines 92-126 correctly slice single function or inter-procedural functions when both source and sink lines fall inside functions.
   - Lines 142-150: Flat script fallback simply returns the entire file `slice_code = code`, which for scripts with hundreds of lines bloats the prompt unnecessarily.

4. **Current Neural Oracle**:
   - Location: `codedee/codedee_server/app/oracle/neural_oracle.py`.
   - Local Ollama verification: `GET http://127.0.0.1:11434/api/tags` returned 200 with models `['qwen2.5:1.5b', 'qwen2.5-coder:32b', 'qwen2.5-coder:14b', 'gpt-oss:20b', 'llama3.1:8b', 'deepseek-coder:6.7b', 'codellama:7b', 'qwen2.5-coder:7b', 'qwen2.5-coder:1.5b']`.
   - Prompt in lines 91-112: Takes `code_slice` and `rag_context`, but omits `finding.taint_path` steps even though `finding` is passed into `_query_ollama_assessment`.
   - JSON parsing in lines 128-132: Uses `re.search(r"\{.*\}", raw_response, re.DOTALL)` which can fail on nested code fences or trailing commas.
   - Patch generation: Not present in `neural_oracle.py`; currently implemented inside `app/api/patches.py` (lines 253-383).

5. **Test Suite Status**:
   - Running `pytest` in `codedee_server/` executed 110 tests: 109 passed, 1 failed (`test_cross_file_taint_path` due to relative working directory `Security_CWE/cross_file_demo/`, unrelated to Stage 3B/4).
   - `tests/test_neuro_verifier.py` (7 tests) and `tests/test_api.py` (17 tests) all passed 100%.

---

## 2. Logic Chain

1. **CST Program Slicing Enhancements**:
   - *From Observation 1*: In Python, functions often have route or auth decorators (e.g., `@app.route(...)`). Snapping `matched_node` to its parent when `matched_node.parent.type == "decorated_definition"` ensures the HTTP route context is included in the slice for the LLM.
   - *From Observation 1*: In JS/TS, arrow functions and function expressions assigned to variables (`const foo = () => ...`) have parent `variable_declarator` in `lexical_declaration` or `export_statement`. Slicing at the `lexical_declaration`/`export_statement` level preserves the complete variable binding and exports, preventing truncated syntax.
   - *From Observation 1*: Arrow function names can be extracted via `parent.child_by_field_name('name')` or finding identifier in `parent.children`, eliminating false `"anonymous"` function labels.
   - *From Observation 3*: For top-level scripts, rather than dumping the whole file, the slicer should locate top-level statement nodes overlapping `[source_line, sink_line]`, expand by 3 statements before/after, and prepend initial module imports (e.g. `sqlite3`, `pg`). If the script is <= 60 lines, returning the entire script is preferred for complete context.

2. **Neural Oracle Stage 3B Assessment**:
   - *From Observation 4*: The existing prompt omits `finding.taint_path`. Including a structured `TAINT PROPAGATION PATH` section in the prompt allows `qwen2.5-coder:7b` to trace intermediate variable transformations and verify whether any step neutralized the taint (e.g., regex check, int cast, or allowlist).
   - *From Observation 4*: Implementing a multi-stage JSON extractor (`extract_json_from_llm_response`):
     - Strip markdown fences (```` ```json ... ``` ````).
     - Extract outermost `{ ... }`.
     - Clean trailing commas before closing braces/brackets.
     - Validate fields and clamp `confidence_score` into `[0.0, 1.0]`.
     - Auto-flag for review if `confidence_score < 0.60`.

3. **Deterministic Fallback Architecture**:
   - *From Observation 4*: When Ollama is offline or times out, wrapping `_query_ollama_assessment` with a deterministic rule-based fallback guarantees API and test stability.
   - If `finding.sanitized` is True, returns `risk_level="SAFE"`, `confidence_score=0.90`, `sanitizer_detected=True`, `is_false_positive=True`.
   - If `finding.sanitized` is False, inspects sink expression for dynamic formatting (`f"..."`, `+`, `%`, `${...}`) -> `risk_level="CRITICAL"`, `confidence_score=0.95`. Ambiguous flows return `confidence_score=0.50`, `flagged_for_review=True`.

4. **Stage 4 Patch Generation via Neural Oracle**:
   - *From Observation 4*: Unifying patch generation by adding `generate_candidate_patches` to `NeuralOracle`:
     - Queries `qwen2.5-coder:7b` with temperatures `0.1, 0.3, 0.5` requesting parameterization without interface modification.
     - Injects language-specific RAG knowledge from ChromaDB (`?`, `%s`, `$1`).
     - Backed by ground-truth matching from `mini_test_datasets.json` and AST/regex rule-based transforms.
     - Delivers 3-4 distinct candidate fixes ready for in-memory Multi-Gate verification.

5. **Code Layout Alignment**:
   - To satisfy `PROJECT.md` line 166-173, create `app/neuro/` with `__init__.py`, `slicer.py`, `oracle.py`, and `rag.py`. Provide re-exports between `app.neuro` and `app.slicer`/`app.oracle`/`app.knowledge` to maintain backwards compatibility.

---

## 3. Caveats

1. **Ollama Execution Latency**: Live Ollama `qwen2.5-coder:7b` requests take approximately 3–4 seconds per query on local hardware. Generating 3 candidates sequentially can take ~10–12 seconds. Keep temperature passes bounded to 3 iterations and use a 15–20s timeout per call.
2. **Top-Level Variable Scopes**: In flat scripts without functions, global variables may be reassigned multiple times. Slicing with module imports + statement window provides optimal context for LLMs without token exhaustion.
3. **Existing Test Failure**: `tests/test_taint_walker.py::test_cross_file_taint_path` failed because `Security_CWE/cross_file_demo/` was referenced as a relative path from the server directory. This is unrelated to Stage 3B/4 components and will be resolved in M5 integration.

---

## 4. Conclusion

1. The CST Program Slicer architecture should be enhanced to handle:
   - Python `decorated_definition` (preserving `@app.route` context).
   - JS/TS arrow functions/expressions (snapping to `lexical_declaration`/`export_statement` to retain `const` variable bindings and names).
   - Statement-level snapping for top-level scripts with module imports preserved.
2. The Neural Oracle architecture should be upgraded to:
   - Supply the full `taint_path` steps to the Stage 3B prompt alongside RAG knowledge.
   - Employ a robust multi-stage JSON parser handling code fences and trailing commas.
   - Provide an air-tight deterministic fallback when Ollama is offline or times out.
   - Incorporate Stage 4 Patch Generation (`generate_candidate_patches`) with multi-temperature sampling (0.1, 0.3, 0.5) and rule-based transforms.
3. Re-exporting modules through `app/neuro/` ensures full compliance with `PROJECT.md` while preserving complete compatibility with all existing test suites.

---

## 5. Verification Method

1. **Verify CST Program Slicing**:
   ```powershell
   cd d:\4th-year\Senior-Project\codedee\codedee_server
   pytest tests/test_neuro_verifier.py -k test_program_slicer -v
   ```
   Inspect slice output to verify function names, enclosing decorators, and statement bounds.

2. **Verify Neural Oracle Live & Fallback**:
   ```powershell
   pytest tests/test_neuro_verifier.py -k test_neural_oracle_assessment -v
   ```
   Asserts `confidence_score` between 0.0 and 1.0, valid `risk_level`, and non-empty `reasoning`.

3. **Verify Full Test Suite**:
   ```powershell
   pytest tests/test_neuro_verifier.py tests/test_api.py -v
   ```
   All 24 tests must pass with zero errors.

4. **Invalidation Conditions**:
   - If an arrow function slice omits the variable identifier or declaration keyword.
   - If `_query_ollama_assessment` crashes on markdown code fences or malformed JSON instead of falling back cleanly.
   - If `generate-patches` fails to produce candidate fixes when Ollama is offline.
