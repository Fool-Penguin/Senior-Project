## 2026-11-01T10:05:54Z
You are worker_m2 (Agent 2: Static Analysis & Graph Engineer).
Your working directory is: d:\4th-year\Senior-Project\.agents\teamwork\worker_m2
You MUST read the original request file first: d:\4th-year\Senior-Project\.agents\teamwork\ORIGINAL_REQUEST.md
Also read the project architecture document: d:\4th-year\Senior-Project\.agents\teamwork\orchestrator\PROJECT.md
Also read the technical survey findings from Explorer 2:
- d:\4th-year\Senior-Project\.agents\teamwork\explorer_survey_2\survey_r2.md
- d:\4th-year\Senior-Project\.agents\teamwork\explorer_survey_2\handoff.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Assigned Scope: Milestone 2 (R2 - Static Analysis & Graph Modeling Engine)
Exclusive Write Ownership:
- d:\4th-year\Senior-Project\codedee\codedee_server\app\parser\cst_manager.py
- d:\4th-year\Senior-Project\codedee\codedee_server\app\graphs\call_graph.py
- d:\4th-year\Senior-Project\codedee\codedee_server\app\graphs\cfg.py
- d:\4th-year\Senior-Project\codedee\codedee_server\app\graphs\dfg.py
- d:\4th-year\Senior-Project\codedee\codedee_server\app\maintainability\engine.py
- d:\4th-year\Senior-Project\codedee\codedee_server\app\taint\walker.py
- d:\4th-year\Senior-Project\codedee\codedee_server\tests\test_treesitter_graphs.py
- d:\4th-year\Senior-Project\codedee\codedee_server\tests\test_maintainability.py
- d:\4th-year\Senior-Project\codedee\codedee_server\tests\test_taint_walker.py

Tasks:
1. Implement Concrete Syntax Tree (CST) parsing using Tree-sitter for Python, JavaScript, and TypeScript in `app/parser/cst_manager.py`. Support both `.ts` and `.tsx` file types. Ensure compatibility with Tree-sitter 0.26 by routing all captures/matches through `tree_sitter.QueryCursor(query)`.
2. Build NetworkX graph builders in `app/graphs/`:
   - `call_graph.py`: Inter-procedural and cross-file function calls with import symbol resolution.
   - `cfg.py`: Control-Flow Graph modeling branching statements (`if`, `for`, `while`, `try-catch`, etc.).
   - `dfg.py`: Data-Flow Graph modeling Def-Use chains, actual argument to formal parameter bindings, and variable propagation.
3. Implement Maintainability Engine in `app/maintainability/engine.py` calculating EXACTLY 8 ISO/IEC 25010 metrics (no SQALE, explicitly excluding LCOM4, DIT, NOM, Raw LOC, and Nesting Depth):
   - Function-level: (1) Cyclomatic Complexity (CC), (2) Cognitive Complexity, (3) Parameter Count, (4) Function SLOC.
   - File-level: (5) File SLOC, (6) Module Coupling (Ce / Ca), (7) Duplicated Blocks, (8) Comment Density.
4. Implement Symbolic Taint Walker in `app/taint/walker.py`:
   - Traverses DFG from taint sources (e.g. `request.args`, `req.query`, `params`, `request.GET`, etc.) to SQL sinks (e.g. `cursor.execute`, `db.query`, `client.query`, `connection.execute`).
   - Tracks concatenation (`+`, `%`, `.format()`, f-strings, template literals).
   - Identifies parameterized query sanitization (e.g. `?`, `%s`, `$1`).
   - Returns structured findings adhering to `SymbolicFinding` and `TaintPath`.
5. Write comprehensive unit test suites:
   - `tests/test_treesitter_graphs.py`: tests CST parsing and NetworkX graph builders (Call Graph, CFG, DFG) for Python, JavaScript, TypeScript.
   - `tests/test_maintainability.py`: tests calculation of exactly the 8 specified ISO/IEC 25010 metrics.
   - `tests/test_taint_walker.py`: tests identifying SQL injection taint paths across Python, JS, TS, including cross-file paths (e.g., from `Security_CWE/cross_file_demo/`).
6. Run `pytest` on all tests (`codedee_server/tests`) and verify 100% passing tests.
7. Verify that `python -m pytest -p no:anyio codedee/tests_e2e/` continues to pass.
8. Document all commands, file paths created, test execution output, and verification methods in:
   `d:\4th-year\Senior-Project\.agents\teamwork\worker_m2\handoff.md`.
9. Send a message to your parent orchestrator with your results.
