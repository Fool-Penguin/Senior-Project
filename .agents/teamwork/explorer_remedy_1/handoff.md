# Handoff Report: Investigation of Defect 1 (Neural Oracle Fallback NameError)

## 1. Observation
1. **Defect Reported by Victory Auditor**:
   - In `victory_auditor_1/handoff.md` (lines 44–52):
     ```
     Root Cause: In `codedee/codedee_server/app/neuro/oracle.py:222`, when Ollama queries fail, time out, or throw an exception, `_query_ollama_assessment` executes:
       `return self._deterministic_fallback_assessment(finding, file_content, language)`
     However, `file_content` is NOT in the function's scope (`code_slice` is the parameter name), triggering an unhandled `NameError: name 'file_content' is not defined` and causing HTTP 500 during `/api/scan`.
     Raw Output:
       File "D:\4th-year\Senior-Project\codedee\codedee_server\app\neuro\oracle.py", line 222, in _query_ollama_assessment
         return self._deterministic_fallback_assessment(finding, file_content, language)
                                                                 ^^^^^^^^^^^^
       NameError: name 'file_content' is not defined
     ```
2. **Function Signature and Scopes in `codedee/codedee_server/app/neuro/oracle.py`**:
   - `assess_finding` (lines 87–93, 108–114, 140–146):
     ```python
     def assess_finding(
         self,
         finding: SymbolicFinding,
         file_content: str,
         language: str = "python",
     ) -> NeuroAssessment:
         ...
         slice_info = self.slicer.slice_context(
             code=file_content,
             language=language,
             source_line=source_line,
             sink_line=sink_line,
         )
         code_slice = slice_info.get("slice_code", file_content)
         ...
         assessment = self._query_ollama_assessment(
             code_slice=code_slice,
             language=language,
             rag_context=rag_context,
             taint_path_str=taint_path_str,
             finding=finding,
         )
         return assessment
     ```
   - `_query_ollama_assessment` (lines 150–157, 219–222):
     ```python
     def _query_ollama_assessment(
         self,
         code_slice: str,
         language: str,
         rag_context: str,
         taint_path_str: str,
         finding: SymbolicFinding,
     ) -> NeuroAssessment:
     ...
         except Exception as e:
             logger.warning(f"Ollama Neural Oracle call failed: {e}. Falling back to deterministic review.")

         return self._deterministic_fallback_assessment(finding, code_slice, language)
     ```
   - Notice: Parameters in `_query_ollama_assessment` are `self`, `code_slice`, `language`, `rag_context`, `taint_path_str`, `finding`. `file_content` is NOT in this method's parameter list or local namespace.
3. **Definition and Call Sites of `_deterministic_fallback_assessment`**:
   - Definition (`codedee/codedee_server/app/neuro/oracle.py:224-229`):
     ```python
     def _deterministic_fallback_assessment(
         self,
         finding: SymbolicFinding,
         file_content: str = "",
         language: str = "python",
     ) -> NeuroAssessment:
     ```
   - Call Site 1 (`codedee/codedee_server/app/neuro/oracle.py:222`):
     `return self._deterministic_fallback_assessment(finding, code_slice, language)`
   - Call Site 2 (`codedee/codedee_server/tests/test_neuro_verifier.py:366`):
     `assessment = oracle._deterministic_fallback_assessment(finding, code, "python")`
   - No other call sites exist across the codebase.
4. **Current Status of Line 222 in `oracle.py`**:
   - Inspection of `codedee/codedee_server/app/neuro/oracle.py:222` confirmed that line 222 now reads:
     `return self._deterministic_fallback_assessment(finding, code_slice, language)`
5. **Static Scope and AST Verification**:
   - Ran `python -m py_compile codedee/codedee_server/app/neuro/oracle.py` -> exit code 0.
   - Ran an exhaustive AST `NodeVisitor` scope checker over `oracle.py` matching loaded names against parameters, assignments, comprehension targets, exception handlers, and module-level globals. Result: **0 undefined variable loads**.
6. **Dynamic Offline Fallback Verification**:
   - Executed dynamic invocation of `NeuralOracle` with unreachable Ollama URL `http://127.0.0.1:99999`:
     - `_query_ollama_assessment(...)` logged fallback and returned `NeuroAssessment(risk_level='CRITICAL', confidence_score=1.0)` without raising `NameError`.
     - `assess_finding(..., sanitized=False)` returned `risk_level='CRITICAL'`.
     - `assess_finding(..., sanitized=True)` returned `risk_level='SAFE'`.
7. **Test Suite Verification**:
   - `pytest codedee/codedee_server/tests/test_neuro_verifier.py -v`: **19 passed, 0 failed** in 9.28s.
   - `python -m pytest -p no:anyio codedee/tests_e2e/test_tier1_features.py -v`: **28 passed, 0 failed** in 18.33s (including `test_scan_python_file_on_disk`).
   - `python -m pytest -p no:anyio codedee/tests_e2e/test_tier4_real_world.py -k test_scenario_sec_py_cwe89_001_sqlite_login -v`: **1 passed, 0 failed** in 7.78s.

## 2. Logic Chain
1. In `oracle.py`, `assess_finding` accepts `file_content: str`, performs program slicing to compute `code_slice: str`, and calls `_query_ollama_assessment(code_slice=code_slice, ...)`.
2. `_query_ollama_assessment` defines the code snippet parameter as `code_slice: str`. `file_content` was not included in its signature.
3. During normal operations when local Ollama `qwen2.5-coder:7b` is running and returns HTTP 200 with valid JSON, line 208 returns the `NeuroAssessment` directly, so line 222 was never reached during happy-path tests.
4. When Ollama failed (unreachable, timeout, non-200 status, or non-JSON output), control flowed to line 222 to invoke deterministic fallback.
5. In the original code observed by the Victory Auditor, line 222 attempted `return self._deterministic_fallback_assessment(finding, file_content, language)`. Because `file_content` was not defined in `_query_ollama_assessment`, Python raised `NameError: name 'file_content' is not defined`.
6. Replacing `file_content` with `code_slice` aligns the call argument with the parameter in scope (`code_slice: str`) and satisfies the signature of `_deterministic_fallback_assessment(self, finding, file_content="", language="python")`.
7. Direct AST scope analysis and offline dynamic execution confirm that `oracle.py` now handles Ollama failures gracefully, producing valid `NeuroAssessment` objects with zero `NameError` exceptions.

## 3. Caveats
- No caveats regarding Defect 1. The root cause, variable scoping, and call sites are completely verified.
- Note that Defect 2 (the cross-file taint parameterization heuristic in `walker.py` affecting `test_cross_file_taint_path`) is independent of Defect 1 and is handled separately by `explorer_remedy_2`.

## 4. Conclusion
1. **Defect 1 Root Cause**: `codedee/codedee_server/app/neuro/oracle.py:222` referenced `file_content`, which is outside the lexical scope of `_query_ollama_assessment` (the local parameter name is `code_slice`).
2. **Current File State**: `codedee/codedee_server/app/neuro/oracle.py:222` already has the exact fix in place:
   ```python
   return self._deterministic_fallback_assessment(finding, code_slice, language)
   ```
3. **Validation Status**:
   - Zero syntax errors, zero undefined names in `oracle.py`.
   - Verified offline fallback behavior for both unsanitized (CRITICAL) and sanitized (SAFE) symbolic findings.
   - `test_neuro_verifier.py` (19/19 passed).
   - `test_tier1_features.py` (28/28 passed).
   - `test_scenario_sec_py_cwe89_001_sqlite_login` (PASSED).
4. **Action Required**: Defect 1 is completely resolved and verified. No further edits to `oracle.py` are required.

## 5. Verification Method
To independently verify this resolution:

```powershell
# 1. Verify AST syntax and scope in oracle.py
python -m py_compile codedee/codedee_server/app/neuro/oracle.py

# 2. Run unit tests for neural oracle and multi-gate verifier
pytest codedee/codedee_server/tests/test_neuro_verifier.py -v

# 3. Run E2E Tier 1 tests (covering test_scan_python_file_on_disk)
python -m pytest -p no:anyio codedee/tests_e2e/test_tier1_features.py -k test_scan_python_file_on_disk -v

# 4. Run E2E Tier 4 test (covering test_scenario_sec_py_cwe89_001_sqlite_login)
python -m pytest -p no:anyio codedee/tests_e2e/test_tier4_real_world.py -k test_scenario_sec_py_cwe89_001_sqlite_login -v
```
Invalidation condition: Any occurrence of `NameError: name 'file_content' is not defined` or test failure in the commands above.
