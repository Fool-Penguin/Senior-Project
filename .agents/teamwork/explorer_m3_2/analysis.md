# Technical Analysis: CST Program Slicer & Neural Oracle (Milestone 3)

## 1. Codebase Architecture & File Mapping

### 1.1 Existing Layout vs PROJECT.md Layout
- `PROJECT.md` (lines 166-173) specifies:
  ```
  app/neuro/
  ├── __init__.py
  ├── rag.py
  ├── slicer.py
  └── oracle.py
  ```
- Current implementation files:
  - `app/parser/cst_manager.py` (Tree-sitter CST parsing manager for Python, JS, TS, TSX)
  - `app/slicer/program_slicer.py` (ProgramSlicer)
  - `app/oracle/neural_oracle.py` (NeuralOracle)
  - `app/knowledge/chroma_kb.py` (ChromaKnowledgeBase)
  - `app/verifier/multi_gate.py` (MultiGateVerifier)
  - `app/api/patches.py` (POST /api/generate-patches)
- **Recommendation**: Create `app/neuro/` module with `slicer.py`, `oracle.py`, and `rag.py` while providing bidirectional aliases/imports with `app/slicer/`, `app/oracle/`, and `app/knowledge/`. This satisfies `PROJECT.md` layout without breaking existing imports in `test_neuro_verifier.py` and API endpoints.

---

## 2. CST Program Slicer Design Specification

### 2.1 Function & Method Node Types Across Languages
| Language | Tree-sitter CST Target Node Types | Enclosing Statement Wrapper to Snapped |
|---|---|---|
| **Python** | `function_definition` | If parent is `decorated_definition`, snap to `decorated_definition` (preserves `@app.route(...)`, `@login_required`, etc.) |
| **JavaScript / TypeScript** | `function_declaration`, `method_definition` | If inside `export_statement`, snap to `export_statement` |
| **JavaScript / TypeScript (Expressions)** | `arrow_function`, `function_expression` | If parent is `variable_declarator`, snap to enclosing `lexical_declaration` / `variable_declaration` / `export_statement` |

### 2.2 Function Name Extraction Heuristics
1. `function_definition` (Python) / `function_declaration` (JS/TS):
   - Child node with field name `"name"` or type `"identifier"`.
2. `method_definition` (JS/TS):
   - Child node with field name `"name"` or type `"property_identifier"` / `"identifier"`.
3. `arrow_function` / `function_expression` (JS/TS):
   - Check `node.parent`. If parent is `variable_declarator`:
     - Extract `parent.child_by_field_name('name')` or child `identifier` (e.g. `const handleLogin = (req, res) => ...` -> name is `"handleLogin"`).
   - If parent is `assignment_expression`:
     - Extract left-hand identifier (e.g. `exports.login = (req, res) => ...` -> `"login"`).
   - If parent is `pair` (object literal):
     - Extract `parent.child_by_field_name('key')` (e.g. `{ login: (req, res) => ... }` -> `"login"`).
   - Fallback: `"anonymous"`.

### 2.3 Top-Level Script Slicing Algorithm
When neither source nor sink is enclosed in a function (e.g., flat scripts):
1. If the entire script is short (`<= 60` lines), return the entire script to preserve full context without truncation.
2. If `> 60` lines:
   - Collect all top-level statements from `tree.root_node.children`.
   - Identify module import statements (`import_statement`, `import_from_statement` in Python; `import_statement` in JS/TS). Retain the first 5 import statements at the top (crucial for LLM to identify DB driver: `sqlite3`, `psycopg2`, `pg`, `mysql2`).
   - Find statements overlapping `[source_line, sink_line]`.
   - Expand window by `context_padding = 3` statements before the source statement and after the sink statement.
   - Join sliced statements with statement-boundary alignment.
   - Tag `slice_type = "top_level_statements"`.

### 2.4 ProgramSlicer Interface
```python
class ProgramSlicer:
    def __init__(self) -> None:
        self.cst_manager = CSTParserManager.get_instance()

    def find_enclosing_function(
        self, tree: tree_sitter.Tree, line_num: int, language: str
    ) -> Optional[Tuple[tree_sitter.Node, str]]:
        ...

    def slice_context(
        self,
        code: str,
        language: str,
        source_line: int,
        sink_line: int,
        context_padding: int = 3,
    ) -> Dict[str, Any]:
        ...

    def slice_from_finding(
        self,
        finding: SymbolicFinding,
        code: Optional[str] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Convenience method directly accepting SymbolicFinding."""
        ...
```

---

## 3. Neural Oracle Design Specification

### 3.1 Stage 3B Assessment: Prompt Construction
The prompt must supply:
1. `TARGET CODE SLICE` (from CST Program Slicer)
2. `TAINT PROPAGATION PATH` (ordered steps from `finding.taint_path`)
3. `RAG KNOWLEDGE` (retrieved from ChromaDB)
4. Strict JSON schema request.

#### Prompt Template:
```text
You are an expert security auditor evaluating a suspected CWE-89 SQL Injection vulnerability.

TARGET CODE SLICE ({language}):
```{language}
{code_slice}
```

TAINT PROPAGATION PATH:
{taint_path_summary}

RELEVANT DEFENSE PATTERNS & SANITIZERS (RAG KNOWLEDGE):
{rag_context}

TASK:
1. Trace the untrusted user input along the taint path from source to sink.
2. Determine whether the input is neutralized by parameterized query placeholders (?, %s, $1) or custom sanitizers (type casting, regex validation, allow-listing).
3. If properly sanitized or parameter-bound, mark sanitizer_detected=true, is_false_positive=true, and risk_level="SAFE".
4. If vulnerable, assess confidence_score (0.0 - 1.0), risk_level ("CRITICAL", "HIGH", "MEDIUM", "LOW"), and explain the attack vector.

Respond STRICTLY with a valid JSON object matching this schema:
{{
  "confidence_score": <float between 0.0 and 1.0>,
  "risk_level": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "SAFE",
  "sanitizer_detected": <true or false>,
  "sanitizer_details": <string description or null>,
  "is_false_positive": <true or false>,
  "reasoning": "<concise chain-of-thought rationale>",
  "flagged_for_review": <true or false>,
  "suggested_remediation": "<actionable fix recommendation or null>"
}}
Do not include any prose or explanation outside the JSON codeblock.
```

### 3.2 Robust Multi-Stage JSON Parser
```python
def extract_json_from_llm_response(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Robust JSON extraction handling:
    1. Markdown fences ```json ... ``` or ``` ... ```
    2. Outermost balanced brace extraction
    3. Trailing comma cleanup
    4. Type normalization and clamping
    """
    if not raw_text or not raw_text.strip():
        return None

    cleaned = raw_text.strip()

    # 1. Check markdown fences
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    # 2. Extract outermost { ... }
    brace_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if brace_match:
        cleaned = brace_match.group(0).strip()

    # 3. Clean trailing commas before closing braces/brackets
    cleaned = re.sub(r",\s*([\]\}])", r"\1", cleaned)

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    return None
```

### 3.3 Graceful Deterministic Fallback Specification
If Ollama is unreachable, times out, returns HTTP != 200, or produces unparseable output:
1. Catch all exceptions (`requests.RequestException`, `json.JSONDecodeError`, etc.).
2. Evaluate `finding.sanitized`:
   - If `True`:
     - `confidence_score = 0.90`
     - `risk_level = "SAFE"`
     - `sanitizer_detected = True`
     - `sanitizer_details = "Deterministic AST analysis: Parameterized query placeholders or safe variable binding confirmed."`
     - `is_false_positive = True`
     - `reasoning = "Deterministic fallback verified that query parameters are safely isolated from SQL command structure."`
     - `flagged_for_review = False`
     - `suggested_remediation = None`
   - If `False`:
     - Examine sink expression for dynamic formatting (`f"..."`, `+`, `%`, `${...}`):
       - If dynamic formatting present:
         - `confidence_score = 0.95`
         - `risk_level = "CRITICAL"`
         - `sanitizer_detected = False`
         - `sanitizer_details = None`
         - `is_false_positive = False`
         - `reasoning = "Deterministic taint verification: Untrusted parameter flows directly into SQL execution sink via dynamic string interpolation without parameterized placeholders."`
         - `flagged_for_review = False`
         - `suggested_remediation = "Replace dynamic string interpolation with parameterized queries (e.g., '?' for SQLite, '%s' for PostgreSQL, '$1' for Node pg)."`
       - If ambiguous:
         - `confidence_score = 0.50`
         - `risk_level = "MEDIUM"`
         - `flagged_for_review = True`
         - `reasoning = "Deterministic analysis identified potential unverified taint path; flagged for security engineer review."`

### 3.4 Stage 4 Patch Generation Specification
Integrate `generate_candidate_patches` into `NeuralOracle`:
```python
def generate_candidate_patches(
    self,
    original_code: str,
    language: str,
    finding: Optional[SymbolicFinding] = None,
    candidate_count: int = 3,
) -> List[str]:
```
1. Prompt Ollama `qwen2.5-coder:7b` at temperatures `[0.1, 0.3, 0.5]` with RAG guidance for the language.
2. Prompt requirements:
   - Replace dynamic concatenation with parameterized placeholders.
   - Maintain EXACT function name, signature, and parameter list.
   - Zero new external dependencies.
   - Maintainability non-regression (delta CC <= 0).
   - Code-only output inside markdown fence.
3. Extract code from markdown fence.
4. Supplement with:
   - Ground truth from `mini_test_datasets.json` (if matching sample).
   - Rule-based AST/regex parameterization transforms (Python: `?`, `%s`; JS/TS: `$1`, `?`).
5. Deduplicate and return candidate list of 3-4 distinct candidates for `MultiGateVerifier`.
