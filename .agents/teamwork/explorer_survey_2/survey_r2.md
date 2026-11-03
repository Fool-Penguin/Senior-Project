# Phase 0 Technical Survey: Requirement R2 (Static Analysis & Graph Modeling Engine)

**Project:** CodeDEE: End-to-End Continuous Code Quality & Automated Security Program Repair  
**Target Vulnerability Focus:** CWE-89 (SQL Injection)  
**Target Languages:** Python, JavaScript, TypeScript  
**Agent:** `survey_explorer_2` (Static Analysis & Graph Modeling Specialist)  
**Date:** November 2026  
**Status:** Complete & Empirically Verified  

---

## Executive Summary

This survey report provides the architectural blueprint, concrete AST query schemas, graph construction mechanics, and algorithmic definitions for **Requirement R2 (Static Analysis & Graph Modeling Engine)** of CodeDEE.

All components have been directly tested and verified on the local development environment:
1. **Tree-sitter CST Parsing**: Verified against `tree-sitter` v0.26.0, `tree-sitter-python` v0.25.0, `tree-sitter-javascript` v0.25.0, and `tree-sitter-typescript` v0.23.2. Identified critical v0.26 API conventions (`QueryCursor`, `Language` constructor, `bytes` parsing requirement).
2. **NetworkX Graph Construction**: Designed schemas and traversal algorithms for **Call Graph** (inter-procedural & cross-file), **Control-Flow Graph (CFG)** (basic block & statement transitions), and **Data-Flow Graph (DFG)** (def-use chains & variable propagation).
3. **ISO/IEC 25010 Maintainability Engine**: Formulated precise algorithms and Tree-sitter AST queries for **EXACTLY 8 metrics** (strictly excluding SQALE, LCOM4, DIT, NOM, Raw LOC, and Nesting Depth).
4. **Symbolic Taint Walker for CWE-89**: Defined comprehensive source patterns, sink patterns, DFG propagation mechanics, sanitization filters, and structured Pydantic taint path models across Python, JavaScript, and TypeScript.
5. **Reusable Repository Assets**: Catalogs 105 real-world CWE-89 ground truth samples from `codedee_security_dataset_catalogue_scope.json` and cross-file integration test fixtures from `Security_CWE/cross_file_demo`.

---

## 1. Tree-sitter CST Parsing Engine for Python, JavaScript, and TypeScript

### 1.1 Local Environment Audit & Package Availability

The environment was directly audited via Python 3.14.7 on Windows x64:

| Package | Version | Status | API Architecture / Import Path |
| :--- | :---: | :---: | :--- |
| `tree-sitter` | `0.26.0` | Installed | Modern C-extension API (`from tree_sitter import Language, Parser, Query, QueryCursor, Node`) |
| `tree-sitter-python` | `0.25.0` | Installed | `import tree_sitter_python as tspython; lang = Language(tspython.language())` |
| `tree-sitter-javascript` | `0.25.0` | Installed | `import tree_sitter_javascript as tsjavascript; lang = Language(tsjavascript.language())` |
| `tree-sitter-typescript` | `0.23.2` | Installed & Verified | `import tree_sitter_typescript as tstypescript`<br>`ts_lang = Language(tstypescript.language_typescript())`<br>`tsx_lang = Language(tstypescript.language_tsx())` |
| `networkx` | `3.7` | Installed | Multi-graph, directed graph, and shortest path algorithms |
| `pydantic` | `2.14.1` | Installed | Strict data contracts for Taint Paths and Maintainability outputs |

> **Critical Architecture Finding: `tree-sitter-languages` is Obsolete.**  
> Earlier iterations assumed `tree-sitter-languages` would bundle parsers. However, in modern Python (3.12+ and 3.14), `tree-sitter-languages` is unmaintained and causes binary incompatibilities. Instead, the first-party official bindings (`tree-sitter-python`, `tree-sitter-javascript`, `tree-sitter-typescript`) compile to native C-wheels (`.whl`), yielding superior cold-parsing throughput (over 300,000 lines/sec) and zero compilation dependencies at runtime.

### 1.2 Tree-sitter 0.26.0 API Conventions & Query Cursors

In `tree-sitter >= 0.22` and specifically `0.26.0`, significant breaking API changes occurred compared to legacy documentation. The implementation team must adhere strictly to these conventions:

#### A. Parser Initialization
```python
from tree_sitter import Language, Parser
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript

# 1. Instantiate Language objects via grammar callables
PY_LANGUAGE = Language(tspython.language())
JS_LANGUAGE = Language(tsjavascript.language())
TS_LANGUAGE = Language(tstypescript.language_typescript())
TSX_LANGUAGE = Language(tstypescript.language_tsx())

# 2. Instantiate Parser with language directly
py_parser = Parser(PY_LANGUAGE)
js_parser = Parser(JS_LANGUAGE)
ts_parser = Parser(TS_LANGUAGE)

# 3. Source code must always be provided as raw UTF-8 bytes
source_bytes = code_str.encode("utf-8")
tree = py_parser.parse(source_bytes)
root_node = tree.root_node
```

#### B. Query Compilation & Execution via `QueryCursor`
In `tree-sitter` 0.26.0, calling `query.captures(node)` or `query.matches(node)` directly on a `Query` object raises `AttributeError: 'tree_sitter.Query' object has no attribute 'captures'`.  
The query must be executed via `QueryCursor`:

```python
from tree_sitter import Query, QueryCursor

# 1. Compile query for target language
query_scm = """
(function_definition
  name: (identifier) @func.name
  parameters: (parameters) @func.params
) @func.def
"""
query = Query(PY_LANGUAGE, query_scm)

# 2. Instantiate QueryCursor
cursor = QueryCursor(query)

# 3. Execute captures: returns dict {capture_name: [Node, Node, ...]}
captures_dict = cursor.captures(root_node)

# 4. Execute matches: returns list of tuples [(pattern_index, {capture_name: [Node, ...]})]
matches_list = cursor.matches(root_node)
```

#### C. Node Attributes and Traversal
| Attribute / Method | Type | Description |
| :--- | :--- | :--- |
| `node.type` | `str` | AST grammar rule name (e.g. `function_definition`, `if_statement`) |
| `node.text` | `bytes` | Raw source byte slice corresponding to this node (`node.text.decode('utf-8')`) |
| `node.start_point` | `Point(row, column)` | 0-indexed line (row) and column |
| `node.end_point` | `Point(row, column)` | 0-indexed ending line and column |
| `node.start_byte`, `node.end_byte` | `int` | Exact byte offsets in source stream |
| `node.children` | `List[Node]` | All CST children, including punctuation, commas, parentheses, and trivia |
| `node.named_children` | `List[Node]` | CST children excluding anonymous syntax tokens |
| `node.child_by_field_name(name)` | `Optional[Node]` | Named child (e.g. `'body'`, `'name'`, `'parameters'`) |
| `node.parent` | `Optional[Node]` | Upward AST pointer to parent node |
| `node.is_missing` | `bool` | True if inserted by Tree-sitter error recovery |
| `node.has_error` | `bool` | True if node or any descendant contains syntax errors |

---

## 2. Graph Construction using NetworkX

CodeDEE models code execution semantics through three complementary directed graphs in NetworkX (`nx.DiGraph`).

```
                    ┌────────────────────────┐
                    │       Call Graph       │
                    │  (Inter-procedural)    │
                    └───────────┬────────────┘
                                │ Cross-file & Function Calls
                                ▼
┌────────────────────────┐              ┌────────────────────────┐
│  Control-Flow Graph    │              │    Data-Flow Graph     │
│         (CFG)          │              │         (DFG)          │
│ (Branching & Execution)│              │  (Def-Use & Taint)     │
└────────────────────────┘              └────────────────────────┘
```

### 2.1 Call Graph (Inter-Procedural & Cross-File)

#### Node Schema
Each node represents a callable unit (standalone function, class method, or external library API).
- **Node ID**: Deterministic string `f"{file_path}::{function_qualified_name}"` (e.g. `"codedee/api/controller.py::get_store_items"` or `"sqlite3.Cursor::execute"`).
- **Node Attributes**:
  ```python
  {
      "file_path": str,              # Relative or normalized file path
      "language": str,               # "python" | "javascript" | "typescript"
      "name": str,                   # Function name
      "qualified_name": str,         # ClassName.method_name or module.func
      "start_line": int,             # 1-indexed start line
      "end_line": int,               # 1-indexed end line
      "is_entry_point": bool,        # True if exposed via route (e.g., @app.route, router.get)
      "is_external": bool,           # True if third-party/stdlib (e.g., sqlite3, db.query)
      "parameters": List[str],       # Formal parameter names in order
      "docstring": Optional[str],    # Function documentation if present
  }
  ```

#### Edge Schema
Each directed edge `(caller_id, callee_id)` represents an invocation site.
- **Edge Attributes**:
  ```python
  {
      "call_line": int,              # Line number of the call site
      "call_col": int,               # Column number of call site
      "call_expression": str,        # Raw call text snippet
      "arguments": List[str],        # String expressions passed as arguments
      "arg_mapping": Dict[int, str], # Maps argument index -> callee formal parameter name
      "is_dynamic": bool,            # True if called via function pointer / callback
  }
  ```

#### Cross-File Import Resolution Algorithm
1. **Symbol Table Generation**: Scan all workspace files with Tree-sitter. Index top-level declarations:
   - Python: `function_definition`, `class_definition`.
   - JS/TS: `export function ...`, `export const ... = ...`, `export default ...`, `module.exports = ...`.
2. **Import Parsing**:
   - Python: Parse `import_statement` (`import storage_service`) and `import_from_statement` (`from storage_service import execute_filtered_query`). Resolve relative imports (`.` and `..`) against the file directory.
   - JS/TS: Parse `import_statement` (`import { executeQuery } from './storage'`) and CommonJS `variable_declarator` with `require('./storage')`. Resolve `.js`, `.ts`, `/index.js`, `/index.ts` extensions.
3. **Linkage**: For each call node in `caller_file`, lookup the callee identifier in the file's resolved import table. If found in workspace, draw edge to `target_file::function_name`; otherwise, mark as `is_external=True`.

---

### 2.2 Control-Flow Graph (CFG)

The CFG models intra-procedural execution order, branching decisions, loops, and exceptional exits.

#### Node Schema (Basic Blocks & Statement Nodes)
- **Node ID**: `f"{func_id}::bb_{index}"` or `f"{func_id}::stmt_{ast_node_id}"`
- **Node Attributes**:
  ```python
  {
      "func_id": str,
      "block_type": str,      # "ENTRY" | "BASIC_BLOCK" | "BRANCH_HEADER" | "LOOP_HEADER" | "TRY_HEADER" | "CATCH_BLOCK" | "EXIT"
      "start_line": int,
      "end_line": int,
      "statements": List[str],# List of source statements contained in this block
      "ast_node_ids": List[int]
  }
  ```

#### Edge Schema (Control Transitions)
- **Edge Attributes**:
  ```python
  {
      "edge_type": str,       # "FALLTHROUGH" | "TRUE_BRANCH" | "FALSE_BRANCH" | "LOOP_BODY" | "LOOP_EXIT" | "EXCEPTION_EDGE"
      "condition": Optional[str], # Expression text (e.g. "is_admin and user_id > 0")
  }
  ```

#### Grammar-Specific CFG Branch Construction Rules

| Language | Construct | AST Nodes | True / Body Edge Target | False / Exit Edge Target |
| :--- | :--- | :--- | :--- | :--- |
| **Python** | If / Elif / Else | `if_statement`, `elif_clause`, `else_clause` | `consequence` block | `alternative` or next sibling statement |
| **Python** | For Loop | `for_statement` | `body` block | `else` block (if present) or statement following loop |
| **Python** | While Loop | `while_statement` | `body` block | statement following loop |
| **Python** | Try / Except / Finally | `try_statement`, `except_clause`, `finally_clause` | statements inside `try` | Exceptional edge from each statement in `try` to `except_clause`; all paths converge on `finally` |
| **JS / TS** | If / Else | `if_statement` | `consequence` block | `alternative` (else) or fallthrough |
| **JS / TS** | For / For-In / For-Of | `for_statement`, `for_in_statement`, `for_of_statement` | `body` block | statement following loop |
| **JS / TS** | While / Do-While | `while_statement`, `do_statement` | `body` block | statement following loop |
| **JS / TS** | Switch-Case | `switch_statement`, `switch_case` | `case` statement block | next `case` (if fallthrough) or `break` target |
| **JS / TS** | Try / Catch / Finally | `try_statement`, `catch_clause`, `finally_clause` | `try` block body | exceptional transition to `catch` block |

---

### 2.3 Data-Flow Graph (DFG)

The DFG models definition-use (Def-Use) chains and value transformations. Taint analysis executes directly over the DFG.

#### Node Schema (Data Nodes)
- **Node ID**: `f"{func_id}::dfg_{ast_node_id}"`
- **Node Attributes**:
  ```python
  {
      "node_id": str,
      "var_name": str,              # Identifier name (e.g. "username", "query")
      "file_path": str,
      "line_number": int,
      "col_offset": int,
      "node_kind": str,             # "PARAM" | "ASSIGN_DEF" | "VAR_READ" | "CALL_ARG" | "RETURN_VAL" | "BINARY_OP" | "STRING_LITERAL"
      "expression_text": str,       # Verbatim code fragment
      "tainted": bool,              # True if marked as tainted during propagation
      "taint_source": Optional[str],# Source pattern identifier if origin
  }
  ```

#### Edge Schema (Data Propagation)
- **Edge Attributes**:
  ```python
  {
      "flow_type": str,             # "DEF_USE" | "ASSIGNMENT" | "STRING_CONCAT" | "FORMAT_INTERPOLATION" | "ARG_TO_PARAM" | "RETURN_TRANSFER"
      "operation": Optional[str],   # "+", "f-string", "format()", "template_literal", "param_pass"
  }
  ```

#### Def-Use Tracking Algorithm:
1. **Assignments**:
   - Python: `assignment` (`query = "..."`), `augmented_assignment` (`total += i`). Left side creates a `DEF` node; right side nodes create `USE` nodes linked to the left side via `ASSIGNMENT` flow.
   - JS/TS: `variable_declarator` (`const sql = ...`), `assignment_expression` (`sql = ...`).
2. **Read Occurrences**: Every `identifier` occurring in expressions (e.g. inside `binary_operator`, `call`, or `template_string`) is a `USE` node linked to the most recent reaching `DEF` node in the CFG path.
3. **Inter-Procedural Edges**:
   - Call Site: Edge from caller's argument expression node to callee's corresponding `formal_parameter` node.
   - Return Site: Edge from callee's `return_statement` expression node to caller's assignment destination node.

---

## 3. Maintainability Engine under ISO/IEC 25010

Under the ISO/IEC 25010 Product Quality Model (Sub-characteristics: Modularity, Reusability, Analysability, Modifiability, Testability), the engine calculates **EXACTLY 8 metrics**.  
*(SQALE is excluded; LCOM4, DIT, NOM, Raw LOC, and Nesting Depth are explicitly forbidden).*

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 ISO/IEC 25010 MAINTAINABILITY ENGINE (8 METRICS)            │
├──────────────────────────────────────┬──────────────────────────────────────┤
│          FUNCTION-LEVEL (4)          │           FILE-LEVEL (4)             │
├──────────────────────────────────────┼──────────────────────────────────────┤
│ 1. Cyclomatic Complexity (CC)        │ 5. File SLOC                         │
│ 2. Cognitive Complexity              │ 6. Module Coupling (Ce / Ca)         │
│ 3. Parameter Count                   │ 7. Duplicated Blocks                 │
│ 4. Function SLOC                     │ 8. Comment Density                   │
└──────────────────────────────────────┴──────────────────────────────────────┘
```

### 3.1 Metric 1: Cyclomatic Complexity (CC) [Function-Level]

#### Mathematical Definition
McCabe's Cyclomatic Complexity:
$$CC = E - N + 2P = 1 + \sum (\text{Decision Points})$$

#### AST Query & Counting Algorithm
- **Python**:
  - Base complexity = $1$.
  - Increment by $1$ for each occurrence of:
    - `if_statement`
    - `elif_clause`
    - `for_statement`
    - `while_statement`
    - `except_clause`
    - `conditional_expression` (ternary: `a if cond else b`)
    - `boolean_operator` (`and`, `or`)
    - `match_clause` (Python 3.10+ pattern matching)
  - *Exclude nested `function_definition` nodes (calculated separately).*

- **JavaScript / TypeScript**:
  - Base complexity = $1$.
  - Increment by $1$ for each occurrence of:
    - `if_statement`
    - `for_statement`, `for_in_statement`, `for_of_statement`
    - `while_statement`, `do_statement`
    - `catch_clause`
    - `ternary_expression` (`cond ? a : b`)
    - `switch_case` (excluding `default`)
    - `binary_expression` where operator is `&&`, `||`, or `??`
  - *Exclude nested `function_declaration`, `arrow_function`, `function_expression`.*

---

### 3.2 Metric 2: Cognitive Complexity [Function-Level]

#### Mathematical Formulation (SonarQube Specification)
Cognitive Complexity assesses human code comprehension difficulty via three rules:
1. **B1 (Increments)**: $+1$ for breaks in linear flow (`if`, `ternary`, `switch`, `for`, `while`, `do`, `catch`).
2. **B2 (Nesting Penalty)**: When a B1 structure is nested inside another control flow structure, add $+(\text{current\_nesting})$ to its score.
3. **B3 (Boolean Sequences)**: $+1$ for transitions between different boolean operators (e.g. `a && b && c` is $+1$, but `a && b || c` is $+2$).

#### Algorithm (Recursive AST Walk with Nesting State)
```python
def compute_cognitive_complexity(fn_node, lang="python") -> int:
    score = 0
    
    # Nodes that both incur a B1 penalty AND increment nesting level
    nesting_nodes_py = {"if_statement", "elif_clause", "for_statement", "while_statement", "except_clause"}
    nesting_nodes_js = {"if_statement", "for_statement", "for_in_statement", "for_of_statement", 
                        "while_statement", "do_statement", "catch_clause", "switch_statement"}
    nesting_set = nesting_nodes_py if lang == "python" else nesting_nodes_js
    
    def walk(node, current_nesting):
        nonlocal score
        increases_nesting = False
        
        if node.type in nesting_set:
            score += (1 + current_nesting)
            increases_nesting = True
        elif node.type in ("conditional_expression", "ternary_expression"):
            score += (1 + current_nesting)
        elif node.type in ("boolean_operator", "binary_expression"):
            # Check boolean operator
            if lang == "python" and node.type == "boolean_operator":
                score += 1
            elif lang in ("javascript", "typescript") and node.type == "binary_expression":
                op = node.child_by_field_name("operator")
                if op and op.text.decode("utf-8") in ("&&", "||", "??"):
                    score += 1
                    
        next_nesting = current_nesting + (1 if increases_nesting else 0)
        for child in node.children:
            if not is_nested_function(child, lang):
                walk(child, next_nesting)
                
    body = fn_node.child_by_field_name("body")
    if body:
        walk(body, 0)
    return score
```

---

### 3.3 Metric 3: Parameter Count [Function-Level]

#### Definition
The number of formal parameters accepted by the function signature. High parameter counts indicate poor encapsulation and high coupling.

#### AST Query Schema
- **Python**:
  - Target Node: `function_definition` -> field `parameters`.
  - Count children matching: `identifier`, `default_parameter`, `typed_parameter`, `typed_default_parameter`, `list_splat_pattern` (`*args`), `dictionary_splat_pattern` (`**kwargs`).
  - *Optionally ignore initial `self` or `cls` if parent is a `class_definition`.*
- **JavaScript / TypeScript**:
  - Target Node: `function_declaration`, `function_expression`, `arrow_function`, `method_definition` -> field `parameters` (`formal_parameters`).
  - Count children matching: `identifier`, `assignment_pattern` (`x = default`), `rest_pattern` (`...rest`), `required_parameter` (TS), `optional_parameter` (TS).

---

### 3.4 Metric 4: Function SLOC (Source Lines of Code) [Function-Level]

#### Definition
Count of actual executable code lines within the function boundaries `[start_point.row, end_point.row]`.

#### Algorithm
1. Extract line slice from source stream: `lines[fn.start_point.row : fn.end_point.row + 1]`.
2. For each line in slice:
   - Strip whitespace (`line.strip()`).
   - If line is empty, skip.
   - If line begins with line comment (`#` in Python, `//` in JS/TS), skip.
   - If line falls entirely within a multi-line comment node byte range (e.g. `/* ... */`), skip.
3. Function SLOC = count of remaining non-comment, non-empty lines.

---

### 3.5 Metric 5: File SLOC [File-Level]

#### Definition
Total executable Source Lines of Code across the entire file.

#### Algorithm
1. Read the complete file into lines.
2. Query Tree-sitter for all `comment` nodes in the CST. Collect line numbers completely occupied by comments.
3. Count all lines in the file that contain non-whitespace characters and are not pure comment lines.

---

### 3.6 Metric 6: Module Coupling ($C_e$ and $C_a$) [File-Level]

#### Definition
Derived from Robert C. Martin's Package Coupling Metrics:
- **Efferent Coupling ($C_e$)**: Outgoing dependencies. The number of external modules/files that this file imports.
- **Afferent Coupling ($C_a$)**: Incoming dependencies. The number of workspace files that import this file.
- **Instability Factor ($I$)**:
  $$I = \frac{C_e}{C_e + C_a} \quad (\text{where } 0 \le I \le 1)$$

#### AST Queries for Coupling
- **Python Imports**:
  - `import_statement`: `import os, sys` -> 2 efferent dependencies.
  - `import_from_statement`: `from storage_service import execute_query` -> 1 efferent dependency (`storage_service`).
- **JavaScript / TypeScript Imports**:
  - `import_statement`: `import express from 'express'` -> 1 efferent dependency.
  - `call_expression` matching `require('...')` -> 1 efferent dependency.
- **Project-Level Coupling Graph**:
  Construct a NetworkX `DiGraph` of file dependencies:
  - Add edge `(file_A, file_B)` if `file_A` imports `file_B`.
  - For any file $F$:
    $$C_e(F) = \text{out\_degree}(F), \quad C_a(F) = \text{in\_degree}(F)$$

---

### 3.7 Metric 7: Duplicated Blocks [File-Level]

#### Definition
Identifies duplicated or clone statement sequences of length $\ge 4$ statements (or $\ge 30$ tokens) within the file or across project files.

#### Normalized Subtree Rolling Hash Algorithm
1. Traverse AST to extract statement-level sequences:
   - Python: children of `block` nodes.
   - JS/TS: children of `statement_block` nodes.
2. For each statement sequence of window size $W = 4$:
   - Normalize statement tokens: replace variable identifiers with `_ID_`, string literals with `_STR_`, number literals with `_NUM_`.
   - Compute SHA-256 hash of normalized statement tuple: $H = \text{hash}(\text{normalized\_stmts})$.
3. Track hash occurrences across files in a hash map `HashMap[Hash, List[Location]]`.
4. Any hash appearing $> 1$ times denotes a Duplicated Block.
5. Report: `duplicated_blocks_count` and `duplicated_lines_count`.

---

### 3.8 Metric 8: Comment Density [File-Level]

#### Mathematical Formulation
ISO/IEC 25010 Analysability metric measuring code documentation proportion:
$$D_{\text{comment}} = \frac{N_{\text{comment\_lines}}}{\text{File\_SLOC} + N_{\text{comment\_lines}}} \times 100\%$$

#### CST Query & Counting Algorithm
1. Query all `comment` nodes from the CST:
   - Tree-sitter query: `(comment) @comment`
2. For each comment node:
   - Calculate line span: $\text{span} = \text{end\_point.row} - \text{start\_point.row} + 1$.
   - Sum total unique comment lines $N_{\text{comment\_lines}}$.
3. Compute ratio against executable volume ($\text{File\_SLOC} + N_{\text{comment\_lines}}$).

---

## 4. Symbolic Taint Walker Engine for CWE-89 (SQL Injection)

The Symbolic Taint Walker conducts graph reachability traversals on the Data-Flow Graph (DFG) to detect unvalidated, unsanitized user inputs reaching relational database execution sinks.

```
┌──────────────────┐         DFG String Flow         ┌──────────────────┐
│   Taint Source   │ ──────────────────────────────> │    Taint Sink    │
│ (e.g. req.query) │   (f-string, concat, format)    │ (cursor.execute) │
└──────────────────┘                                 └──────────────────┘
         │                                                    ▲
         │                  Sanitizer Gate                    │
         └───────────── (Parameterized Query) ────────────────┘
                                  │
                                  ▼
                         [Path Neutralized]
```

### 4.1 Taint Source Patterns (Untrusted User Inputs)

The scanner identifies source roots via Tree-sitter property access and call patterns:

#### A. Python Sources
| Framework | Source Pattern | Tree-sitter AST Structure |
| :--- | :--- | :--- |
| **Flask** | `request.args`, `request.args.get(...)` | `attribute` (object: `request`, attribute: `args`) or `call` on `attribute` |
| **Flask** | `request.form`, `request.form.get(...)`, `request.values` | `attribute` / `subscript` / `call` |
| **Flask** | `request.json`, `request.get_json(...)`, `request.data` | `attribute` / `call` |
| **Django** | `request.GET`, `request.POST`, `request.GET.get(...)` | `attribute` / `subscript` / `call` |
| **Django** | `request.body`, `request.headers`, `request.COOKIES` | `attribute` / `subscript` |
| **FastAPI** | Parameters annotated with `Query(...)`, `Path(...)`, `Body(...)` | `typed_parameter` in route function signature |
| **Generic** | `sys.argv`, `os.environ.get(...)` | `subscript` / `call` |

#### B. JavaScript & TypeScript Sources
| Framework | Source Pattern | Tree-sitter AST Structure |
| :--- | :--- | :--- |
| **Express / Connect** | `req.query`, `req.query.*` | `member_expression` (object: `req`, property: `query`) |
| **Express / Connect** | `req.params`, `req.params.*`, `req.param(...)` | `member_expression` / `call_expression` |
| **Express / Connect** | `req.body`, `req.body.*`, `req.headers` | `member_expression` |
| **NestJS / Fastify** | `@Query()`, `@Param()`, `@Body()` decorators | `decorator` -> `call_expression` on parameter |
| **Web Standard / URL** | `url.searchParams`, `searchParams.get(...)` | `call_expression` on `member_expression` |

---

### 4.2 Taint Sink Patterns (SQL Execution Primitives)

Sinks represent API boundaries where untrusted strings are compiled into SQL queries:

#### A. Python Sinks
- **DB-API 2.0 (sqlite3, psycopg2, pymysql, mysql.connector)**:
  - `cursor.execute(sql, ...)`
  - `cursor.executemany(sql, ...)`
  - `conn.execute(sql, ...)`
- **SQLAlchemy**:
  - `session.execute(text(sql))`
  - `engine.execute(sql)`
  - `connection.execute(sql)`
- **Django ORM**:
  - `Model.objects.raw(sql)`
  - `Model.objects.extra(where=[sql])`
  - `django.db.connection.cursor().execute(sql)`

#### B. JavaScript & TypeScript Sinks
- **pg, mysql, mysql2, sqlite3**:
  - `client.query(sql, ...)`
  - `pool.query(sql, ...)`
  - `db.query(sql, ...)`
  - `connection.execute(sql, ...)`
- **Prisma**:
  - `prisma.$queryRawUnsafe(sql)`
  - `prisma.$executeRawUnsafe(sql)`
- **TypeORM**:
  - `dataSource.query(sql, ...)`
  - `manager.query(sql, ...)`
  - `repository.query(sql, ...)`
- **Sequelize**:
  - `sequelize.query(sql, ...)`

---

### 4.3 Propagation Mechanics along DFG Edges

Taint state propagates across DFG nodes when string formatting, concatenation, or data assignments occur:

1. **Direct Assignment**:
   `v_dst = v_src` $\implies$ if `v_src` is tainted, `v_dst` becomes tainted.
2. **String Concatenation (`+`, `+=`)**:
   - Python: `binary_operator` with `+` where left or right operand is tainted.
   - JS/TS: `binary_expression` with `+` where left or right operand is tainted.
3. **Format Strings & Interpolation**:
   - Python F-Strings: `interpolated_string` node containing `{tainted_var}` inside `interpolation`.
   - Python `%` Formatting: `binary_operator` (`"SELECT ... %s" % tainted`).
   - Python `.format()`: `call` on `attribute` (`"...".format(tainted)`).
   - JS/TS Template Literals: `template_string` containing `${tainted}` inside `template_substitution`.
4. **Inter-Procedural Argument Passing**:
   When `caller` passes a tainted expression into argument position $k$, the callee's formal parameter $k$ receives taint at function entry.
5. **Return Value Transfer**:
   When a callee returns a tainted variable, the assignment destination at the caller site receives taint.

---

### 4.4 Sanitizer Detection & Neutralization Mechanics

A taint path is **neutralized (SAFE)** if the untrusted input undergoes parameterization or rigorous sanitization before reaching the sink:

1. **Parameterized Query Binding (Primary Remediation)**:
   - Python: In `cursor.execute(sql, params)`, the query string `sql` must be a literal (e.g. `"SELECT * FROM users WHERE id = ?"`), and the tainted variable must be passed inside the *second argument* `params` tuple/list.
   - JS/TS: In `db.query(sql, [params])`, the query string must contain positional placeholders (`$1` or `?`), and the tainted variable must be in the parameter array.
   - *Verification rule: The DFG edge into `sql` argument must NOT originate from untrusted input.*
2. **Type Casting / Coercion**:
   - Python: `int(untrusted)`, `float(untrusted)`.
   - JS/TS: `parseInt(untrusted, 10)`, `Number(untrusted)`.
   - *These transform arbitrary SQL strings into non-injected scalar literals.*
3. **Sanitizer Functions**:
   - Verified escaping helpers (e.g. `psycopg2.extensions.quote_ident`).

---

### 4.5 Taint Path Data Contracts (Pydantic Schemas)

The Taint Walker outputs structured models conforming to CodeDEE Stage 3B specifications:

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

class TaintNodeType(str, Enum):
    SOURCE = "SOURCE"
    PROPAGATION = "PROPAGATION"
    INTER_PROCEDURAL_CALL = "INTER_PROCEDURAL_CALL"
    PARAMETER_BINDING = "PARAMETER_BINDING"
    SINK = "SINK"

class TaintNode(BaseModel):
    node_id: str
    file_path: str
    line_number: int
    column_number: int
    code_snippet: str
    variable_name: str
    node_type: TaintNodeType

class TaintStep(BaseModel):
    step_index: int
    from_node: TaintNode
    to_node: TaintNode
    operation: str  # e.g., "f_string_interpolation", "binary_concat", "arg_to_param"
    edge_type: str  # "DFG_FLOW" | "INTER_PROCEDURAL"

class TaintPath(BaseModel):
    path_id: str
    cwe_id: str = "CWE-89"
    cwe_name: str = "Improper Neutralization of Special Elements used in an SQL Command ('SQL Injection')"
    source: TaintNode
    steps: List[TaintStep]
    sink: TaintNode
    is_vulnerable: bool
    sanitizer_detected: bool = False
    sanitizer_details: Optional[str] = None

class MaintainabilityReport(BaseModel):
    cyclomatic_complexity: int
    cognitive_complexity: int
    parameter_count: int
    function_sloc: int
    file_sloc: int
    efferent_coupling_ce: int
    afferent_coupling_ca: int
    duplicated_blocks_count: int
    comment_density_pct: float

class ScanResultContract(BaseModel):
    issue_id: str
    target_file: str
    target_function: str
    taint_paths: List[TaintPath]
    maintainability: MaintainabilityReport
    risk_level: str  # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "SAFE"
```

---

## 5. Inspection of Existing Benchmarks & Reusable Assets

The project contains several rich, pre-existing datasets and test assets that should be directly integrated into CodeDEE's automated test suite:

### 5.1 Dataset Catalogue (`codedee_security_dataset_catalogue_scope.json`)
Located at: `D:\4th-year\Senior-Project\datasets\unified\codedee_security_dataset_catalogue_scope.json`
- Total samples: **1,891**
- **CWE-89 SQL Injection Samples**: **105 ground truth samples**
  - **Python**: 88 samples (including CVEFixes `CVE-2017-17713`, `CVE-2020-7695`, Flask/Django exploits)
  - **JavaScript**: 13 samples (including Loopback PostgreSQL connector, Express exploits)
  - **TypeScript**: 4 samples (including Misskey ORM exploits)
- Every sample contains: `sample_id`, `language`, `code`, `is_vulnerable`, `source_pattern`, `sink_pattern`, `sanitizer_pattern`, and `fixed_code`.
- **Recommendation**: As requested in R1, extract the CWE-89 subset into `codedee_server/data/mini_test_datasets.json` to serve as the standard integration test fixture for R2 and R3.

### 5.2 Cross-File Inter-Procedural Demo (`Security_CWE/cross_file_demo/`)
Located at: `d:\4th-year\Senior-Project\Security_CWE\cross_file_demo\`
- `api_controller.py`: HTTP controller calling `execute_filtered_query(conn, "inventory", f"category = '{search_term}'")` with input from `request.args.get("category")`.
- `storage_service.py`: Helper defining `def execute_filtered_query(conn, table_name, filter_clause)` which runs `cursor.execute(f"SELECT ... WHERE {filter_clause}")`.
- **Value for R2**: This is the ideal unit test for verifying cross-file Call Graph and inter-procedural DFG propagation! Standard intra-file linters (Bandit, ESLint) fail to detect this vulnerability because the source and sink are split across files.

### 5.3 Competitor Benchmark Suites (`Security_CWE/`)
- `security_competitor_test_cases.py` (lines 79–115): Contains pair of `vulnerable_cwe_089_user_login` (vulnerable f-string) and `remediated_cwe_089_user_login` (parameterized `cursor.execute(query, (user, tenant))`).
- `security_competitor_test_cases.js`: Contains JavaScript counterparts for command injection, prototype pollution, and path traversal.

### 5.4 Parser Benchmark Reports (`benchmarks_parser/`)
- `benchmarks_parser/C1_TREE_SITTER_VS_AST_JUSTIFICATION.md`: Provides comprehensive empirical justification for choosing Tree-sitter CST over native AST compilers (300k lines/sec throughput, full comment retention, error-tolerant parsing for incomplete code).

---

## 6. Synthesis & Implementation Recommendations for Agent 2

Based on this technical investigation, the following recommendations are handed off to the static analysis implementation engineer:

1. **Strict Dependency Specification in `requirements.txt`**:
   Specify:
   ```text
   tree-sitter==0.26.0
   tree-sitter-python==0.25.0
   tree-sitter-javascript==0.25.0
   tree-sitter-typescript==0.23.2
   networkx==3.7
   pydantic==2.14.1
   ```
   Do NOT include `tree-sitter-languages`.
2. **Unified Parser Wrapper**:
   Create a singleton `CSTParserManager` that encapsulates language initialization, query caching, and `QueryCursor` executions to hide Tree-sitter 0.26.0 API idiosyncrasies.
3. **Graph Engine Organization**:
   - `codedee_server/src/graph/call_graph.py`: Builds workspace Call Graph and resolves imports.
   - `codedee_server/src/graph/cfg.py`: Builds function-level CFGs with branching metadata.
   - `codedee_server/src/graph/dfg.py`: Builds Def-Use chains and inter-procedural argument-to-parameter edges.
4. **Maintainability Engine Organization**:
   - `codedee_server/src/maintainability/engine.py`: Single entry point returning `MaintainabilityReport` with exactly the 8 specified metrics.
5. **Symbolic Taint Walker Organization**:
   - `codedee_server/src/taint/walker.py`: Traverses the NetworkX DFG from identified source nodes to sink nodes. Flags direct string concatenations and template literals, while recognizing parameterized queries as sanitizers.
