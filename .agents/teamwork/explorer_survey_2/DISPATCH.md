# DISPATCH

## 2026-11-01T08:52:36Z
Sender: cdd4c46b-fa83-40b4-992f-7161af706ca8
Priority: MESSAGE_PRIORITY_HIGH

You are survey_explorer_2, an exploration agent for CodeDEE.
Your working directory is: d:\4th-year\Senior-Project\.agents\teamwork\explorer_survey_2
You MUST read the original request file first: d:\4th-year\Senior-Project\.agents\teamwork\ORIGINAL_REQUEST.md

Your mission is Phase 0 Survey for R2 (Static Analysis & Graph Modeling Engine):
1. Tree-sitter CST Parsing for Python, JavaScript, and TypeScript:
   - Check which tree-sitter packages and bindings are available in the local Python environment (e.g. `tree_sitter`, `tree_sitter_languages`, `tree_sitter_python`, etc.).
   - Test parser initialization and AST inspection for Python, JS, and TS code snippets. Check API conventions (e.g. node.type, node.children, query cursors).
2. Graph Construction using NetworkX:
   - Design Call Graph: Inter-procedural and cross-file function calls. How nodes (functions/methods) and edges (call sites) should be modeled.
   - Design Control-Flow Graph (CFG): Branching statements (`if`, `for`, `while`, `try-catch`, etc.) modeling control transitions between statements.
   - Design Data-Flow Graph (DFG): Def-Use chains and variable propagation (tracking assignments, mutations, and read occurrences).
3. Maintainability Engine under ISO/IEC 25010:
   - Must calculate EXACTLY 8 metrics (no SQALE, explicitly excluding LCOM4, DIT, NOM, Raw LOC, and Nesting Depth):
     Function-level:
       (1) Cyclomatic Complexity (CC)
       (2) Cognitive Complexity
       (3) Parameter Count
       (4) Function SLOC
     File-level:
       (5) File SLOC
       (6) Module Coupling (Ce / Ca)
       (7) Duplicated Blocks
       (8) Comment Density
   - Provide precise algorithms and AST queries for each of these 8 metrics.
4. Symbolic Taint Walker:
   - Define exact source patterns for Python, JS, TS (e.g. `request.args`, `req.query`, `params`, `request.GET`, etc.).
   - Define exact sink patterns for Python, JS, TS (e.g. `cursor.execute`, `db.query`, `client.query`, `connection.execute`, etc.).
   - Define propagation mechanics along DFG edges (concatenation, formatting, f-strings, template literals).
   - Define taint path data structure (source node, propagation steps, sink node).
5. Inspect any existing code/benchmarks in `d:\4th-year\Senior-Project` (such as `benchmarks_parser`, `Security_CWE`, etc.) to see existing patterns or reusable test assets.
6. Document all findings, AST query schemas, algorithms, and recommendations in:
   `d:\4th-year\Senior-Project\.agents\teamwork\explorer_survey_2\survey_r2.md` and `d:\4th-year\Senior-Project\.agents\teamwork\explorer_survey_2\handoff.md`.
7. Send a completion message to your parent orchestrator with a summary of findings.
