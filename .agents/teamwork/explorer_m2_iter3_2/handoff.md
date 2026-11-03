# Handoff Report: Investigation & Design for Defect 3 & Defect 4 in `dfg.py`

**Agent ID:** `explorer_m2_iter3_2`  
**Working Directory:** `d:\4th-year\Senior-Project\.agents\teamwork\explorer_m2_iter3_2`  
**Parent Agent:** `cdd4c46b-fa83-40b4-992f-7161af706ca8` (orchestrator)  
**Date:** 2026-11-01  
**Target:** Milestone 2 DFG Taint Flow Defect Remediation  
**Status:** COMPLETE (Ready for Implementation by Worker Agent)

---

## 1. Observation

### A. Context & Baseline Status
- **Baseline Test Suite:** `pytest codedee/codedee_server/tests -v` completed with **75 passed in 19.10s**.
- **Challenger Adversarial Suite:** `pytest .agents/teamwork/challenger_m2_fix_1/test_adversarial_dfg_taint.py -v` demonstrated **5 confirmed evasion defects**, specifically:
  - **Defect 3:** Python keyword arguments omission in calls (`test_demonstrate_defect_3_keyword_argument_taint_loss`).
  - **Defect 4:** Subscript indexing expression omission (`test_demonstrate_defect_4_subscript_indexing_taint_loss`).

---

### B. Empirical Defect 3: Python Keyword Arguments Omission
- **Source Location:** `codedee/codedee_server/app/graphs/dfg.py:456-466` and `dfg.py:541-556`
- **Code Inspection:**
  In `dfg.py:456-466`:
  ```python
  # Process arguments
  if args_node:
      arg_idx = 0
      for arg_child in args_node.children:
          if arg_child.type in ("(", ")", ",", "[", "]", "{", "}"):
              continue
          arg_ids = self._process_expression(arg_child, source_bytes, language, file_path, func_id, current_defs)
          for aid in arg_ids:
              self.graph.add_edge(aid, call_id, flow_type="ARG_TO_PARAM", operation=f"arg_{arg_idx}")
          arg_idx += 1
  ```
- **Tree-sitter CST Inspection (Python):**
  For `foo(a, b=user, c="static", d=req.args["id"])`:
  ```
  call
    function: identifier ("foo")
    arguments: argument_list
      identifier ("a")
      keyword_argument ("b=user")
        name: identifier ("b")
        =
        value: identifier ("user")
      keyword_argument ("c=\"static\"")
        name: identifier ("c")
        =
        value: string ("\"static\"")
      keyword_argument ("d=req.args[\"id\"]")
        name: identifier ("d")
        =
        value: subscript ("req.args[\"id\"]")
  ```
- **Observed Failure Behavior:**
  When `arg_child` is `keyword_argument`:
  1. `_process_expression(arg_child, ...)` has no branch for `node_type == "keyword_argument"`.
  2. It falls through to the literal fallback at line 542:
     ```python
     lit_id = f"{func_id}::lit_{node.start_point.row + 1}_{node.start_point.column}"
     self.graph.add_node(..., node_kind="EXPRESSION", var_name="b=user", ...)
     return [lit_id]
     ```
  3. `lit_id` is an isolated node with no incoming edges. The inner expression `user` is never visited, so no `VAR_READ` node or `DEF_USE` edge from `def_user` is created.
  4. In `call_6_10` (`"...".format(name=user)`), `lit_id -> call_id` is created, but `def_user` remains completely disconnected from `call_id`.
  5. In `test_demonstrate_defect_3_keyword_argument_taint_loss`, `len(vulns) == 0`.

---

### C. Empirical Defect 4: Subscript Indexing Expression Omission
- **Source Location:** `codedee/codedee_server/app/graphs/dfg.py:541-556` and `dfg.py:138-175`
- **Tree-sitter CST Inspection Across Languages:**
  - **Python (`tree_sitter_python`):**
    ```python
    # Code: container[0], data['key'], matrix[i][j], matrix[i, j]
    subscript
      value: identifier ("container")
      [
      subscript: integer ("0")
      ]
    ```
    - Node type: `"subscript"`
    - Child field `'value'`: Base collection / dictionary / expression.
    - Child field `'subscript'`: Index / key expression (`integer`, `string`, `slice`, `identifier`, etc.).
  - **JavaScript & TypeScript (`tree_sitter_javascript`, `tree_sitter_typescript`):**
    ```javascript
    // Code: container[0], data['key'], matrix[i][j], data?.[0]
    subscript_expression
      object: identifier ("container")
      [
      index: number ("0")
      ]
    ```
    - Node type: `"subscript_expression"`
    - Child field `'object'`: Base array / object / expression.
    - Child field `'index'`: Index / property expression (`number`, `string`, `identifier`, etc.).
    - Optional chaining: field `'optional_chain'` (`?.`).
- **Observed Failure Behavior:**
  1. **RHS Subscript Read:**
     In `sql = "SELECT * FROM items WHERE owner = '%s'" % container[0]`, `container[0]` is the operand of `%`.
     Neither `"subscript"` nor `"subscript_expression"` is handled in `_process_expression`.
     It falls through to line 542:
     `lit_id = f"{func_id}::lit_..." (node_kind="EXPRESSION", var_name="container[0]")`.
     Even though `container = [user]` correctly constructed:
     `def_user -> use_user -> coll_id -> def_container`,
     the read `container[0]` has NO edge from `def_container`! The chain stops at `def_container`.
     In `test_demonstrate_defect_4_subscript_indexing_taint_loss`, `len(vulns) == 0`.
  2. **LHS Subscript Assignment Mutation:**
     In `container[0] = user`, `_process_statement` at line 145 checks `if left and left.type == "identifier":`.
     Because `left.type == "subscript"`, the assignment is skipped entirely! `current_defs["container"]` is never updated with the new value.

---

## 2. Logic Chain

1. **Step 1 (Root Cause of Defect 3)**:
   - In Python, keyword arguments are represented as `keyword_argument` syntax nodes wrapping `name` and `value`.
   - Function call arguments are traversed by passing each child of `argument_list` to `_process_expression`.
   - Because `_process_expression` has no case for `keyword_argument`, the node is treated as a literal expression, dropping its `value` child.
   - Therefore, any tainted variable passed as a named argument (such as in `str.format(name=user)` or `helper(query=sql)`) is dropped from the DFG.

2. **Step 2 (Root Cause of Defect 4)**:
   - In Python, indexing is parsed as `subscript` with fields `value` and `subscript`.
   - In JavaScript/TypeScript, indexing is parsed as `subscript_expression` with fields `object` and `index`.
   - Because neither node type is handled in `_process_expression`, reading an element from a collection or dictionary creates a disconnected literal node rather than reading from the container's definition.
   - Consequently, storing tainted values in lists, tuples, or dictionaries and then retrieving them severed all data-flow reachability to SQL execution sinks.

3. **Step 3 (Cross-Language Consistency & Splat Operators)**:
   - In Python, `**kwargs` is `dictionary_splat` and `*args` is `list_splat`.
   - In JavaScript/TypeScript, `...args` is `spread_element`.
   - In JavaScript/TypeScript, named argument passing uses object literals `{ key: val }`, which `_process_expression` already handles via `object` and `pair`.
   - To make DFG construction fully robust across Python, JS, and TS, `_process_expression` must unwrap `keyword_argument`, `dictionary_splat`, `list_splat`, and `spread_element`.

4. **Step 4 (Inter-Procedural Keyword Binding Consistency)**:
   - In `CallGraphBuilder`, arguments like `query=sql` are recorded.
   - In `DFGBuilder.link_inter_procedural_calls`, argument matching currently only expects positional `arg_{idx}` strings.
   - Tagging call argument edges with `kwarg_{name}` enables direct, order-independent parameter binding to formal callee parameters (`param_{name}`).

5. **Step 5 (Empirical Prototype Verification)**:
   - Subclassing `DFGBuilder` as `FixedDFGBuilder` and testing against `test_adversarial_dfg_taint.py`:
     - Defect 3: Detected with `CWE-89 CRITICAL sanitized=False steps=7`.
     - Defect 4: Detected with `CWE-89 CRITICAL sanitized=False steps=11`.
     - JS Subscript: Detected with `CWE-89 CRITICAL sanitized=False steps=11`.
     - TS Subscript: Detected with `CWE-89 CRITICAL sanitized=False steps=10`.
     - LHS Subscript Assignment (`container[0] = user`): Detected with `CRITICAL sanitized=False steps=10`.

---

## 3. Caveats

1. **Read-Only Investigation Compliance:**
   - In accordance with the Explorer mandate, no modifications were made to `codedee/codedee_server/app/graphs/dfg.py`.
   - Prototypes were executed in isolated test scripts within `.agents/teamwork/explorer_m2_iter3_2/`.
2. **Defect 1 & Defect 2 Scope Boundary:**
   - Defect 1 (method call receiver omission) and Defect 2 (Python `await` syntactic wrapper omission) are assigned to peer agent `explorer_m2_iter3_1`.
   - This investigation strictly focuses on Defect 3 and Defect 4, but ensures zero interference with Defect 1 and Defect 2 fixes.
3. **Container Element Tracking vs Aggregate Modeling:**
   - The DFG models data flow at the container level (taint in any container element taints the container access). This is standard and sound for static taint analysis to prevent false negatives.
4. **Dynamic Index Taint:**
   - If the index itself is a variable or expression (e.g. `arr[user_idx]`), it is evaluated and connected. If it is a constant integer/string literal (`arr[0]`, `data['key']`), it is not connected to prevent cluttering the graph with literal nodes.

---

## 4. Conclusion & Proposed Implementation

### A. Concrete Changes to `codedee/codedee_server/app/graphs/dfg.py`

#### Change 1: Add Subscript Handling to `_process_expression`
**Location:** `codedee/codedee_server/app/graphs/dfg.py` (after section 8 / line 502)
```python
        # 8b. Subscript / Indexing Access: container[0], data['key'], matrix[i][j]
        # Python: 'subscript' (child fields: 'value', 'subscript')
        # JS/TS: 'subscript_expression' (child fields: 'object', 'index')
        if node_type in ("subscript", "subscript_expression"):
            sub_id = f"{func_id}::subscript_{node.start_point.row + 1}_{node.start_point.column}"
            self.graph.add_node(
                sub_id,
                node_id=sub_id,
                var_name=node_text,
                file_path=file_path,
                line_number=node.start_point.row + 1,
                col_offset=node.start_point.column,
                node_kind="VAR_READ",
                expression_text=node_text,
                tainted=False,
                taint_source=None,
                ast_node=node,
            )

            # Determine base container node
            base_node = node.child_by_field_name("value") or node.child_by_field_name("object")
            if base_node is None and node.children:
                base_node = node.children[0]

            if base_node:
                base_ids = self._process_expression(base_node, source_bytes, language, file_path, func_id, current_defs)
                for bid in base_ids:
                    self.graph.add_edge(bid, sub_id, flow_type="DEF_USE", operation="subscript")

            # Process dynamic index expression if tainted/non-literal
            index_node = node.child_by_field_name("subscript") or node.child_by_field_name("index")
            if index_node and index_node.type not in ("integer", "number", "string", "slice"):
                idx_ids = self._process_expression(index_node, source_bytes, language, file_path, func_id, current_defs)
                for iid in idx_ids:
                    self.graph.add_edge(iid, sub_id, flow_type="DEF_USE", operation="index")

            return [sub_id]
```

#### Change 2: Add Keyword Argument & Splat/Spread Handling to `_process_expression`
**Location:** `codedee/codedee_server/app/graphs/dfg.py` (around line 532, adjacent to `pair` handling)
```python
        # 9b. Python Keyword Arguments: name=expr
        if node_type == "keyword_argument":
            val_node = node.child_by_field_name("value")
            if val_node:
                return self._process_expression(val_node, source_bytes, language, file_path, func_id, current_defs)
            return []

        # 9c. Splats & Spreads: *args, **kwargs (Python), ...args (JS/TS)
        if node_type in ("dictionary_splat", "list_splat", "spread_element"):
            for child in node.children:
                if child.is_named:
                    return self._process_expression(child, source_bytes, language, file_path, func_id, current_defs)
            return []
```

#### Change 3: Annotate Call Arguments with Keyword Names
**Location:** `codedee/codedee_server/app/graphs/dfg.py:456-466`
```python
            # Process arguments
            if args_node:
                arg_idx = 0
                for arg_child in args_node.children:
                    if arg_child.type in ("(", ")", ",", "[", "]", "{", "}"):
                        continue
                    kw_name = None
                    if arg_child.type == "keyword_argument":
                        k_name_node = arg_child.child_by_field_name("name")
                        if k_name_node:
                            kw_name = self.cst_manager.get_node_text(k_name_node, source_bytes)

                    arg_ids = self._process_expression(arg_child, source_bytes, language, file_path, func_id, current_defs)
                    op_str = f"kwarg_{kw_name}" if kw_name else f"arg_{arg_idx}"
                    for aid in arg_ids:
                        self.graph.add_edge(aid, call_id, flow_type="ARG_TO_PARAM", operation=op_str)
                    arg_idx += 1
```

#### Change 4: Support Keyword Argument Inter-Procedural Binding
**Location:** `codedee/codedee_server/app/graphs/dfg.py:610-634` (`link_inter_procedural_calls`)
```python
            for call_node in matching_call_nodes:
                # Find arguments feeding into this call node
                in_edges = self.graph.in_edges(call_node, data=True)
                for src, _, ed in in_edges:
                    op = ed.get("operation", "")
                    param_name = None
                    if op.startswith("kwarg_"):
                        param_name = op[len("kwarg_"):]
                    elif op.startswith("arg_"):
                        try:
                            arg_idx = int(op.split("_")[1])
                            if arg_idx < len(callee_params):
                                param_name = callee_params[arg_idx]
                        except ValueError:
                            continue

                    if param_name:
                        target_param_nodes = [
                            n for n, d in self.graph.nodes(data=True)
                            if d.get("var_name") == param_name
                            and d.get("node_kind") == "PARAM"
                            and (d.get("file_path") == callee_file or callee_name in n)
                        ]
                        for tp in target_param_nodes:
                            self.graph.add_edge(
                                src,
                                tp,
                                flow_type="ARG_TO_PARAM",
                                operation=f"bind({param_name})",
                            )
```

#### Change 5: Support Subscript on LHS of Statement Assignment
**Location:** `codedee/codedee_server/app/graphs/dfg.py:138-175` (`_process_statement`)
```python
        # PYTHON ASSIGNMENT: var = expr OR container[0] = expr
        if stmt_type in ("assignment", "augmented_assignment"):
            left = stmt.child_by_field_name("left")
            right = stmt.child_by_field_name("right")

            rhs_nodes = self._process_expression(right, source_bytes, language, file_path, func_id, current_defs) if right else []

            if left and left.type == "identifier":
                var_name = self.cst_manager.get_node_text(left, source_bytes)
                def_id = f"{func_id}::def_{var_name}_{left.start_point.row + 1}_{left.start_point.column}"
                expr_text = self.cst_manager.get_node_text(stmt, source_bytes)

                self.graph.add_node(
                    def_id,
                    node_id=def_id,
                    var_name=var_name,
                    file_path=file_path,
                    line_number=left.start_point.row + 1,
                    col_offset=left.start_point.column,
                    node_kind="ASSIGN_DEF",
                    expression_text=expr_text,
                    tainted=False,
                    taint_source=None,
                    ast_node=left,
                )

                for r_id in rhs_nodes:
                    self.graph.add_edge(r_id, def_id, flow_type="ASSIGNMENT", operation="=")

                if stmt_type == "augmented_assignment" and var_name in current_defs:
                    prev_def = current_defs[var_name]
                    self.graph.add_edge(prev_def, def_id, flow_type="STRING_CONCAT", operation="+=")

                current_defs[var_name] = def_id
                return

            # Subscript assignment: container[0] = user or data['key'] = user
            if left and left.type in ("subscript", "subscript_expression"):
                base_node = left.child_by_field_name("value") or left.child_by_field_name("object")
                if base_node and base_node.type == "identifier":
                    var_name = self.cst_manager.get_node_text(base_node, source_bytes)
                    def_id = f"{func_id}::def_{var_name}_{left.start_point.row + 1}_{left.start_point.column}"
                    expr_text = self.cst_manager.get_node_text(stmt, source_bytes)

                    self.graph.add_node(
                        def_id,
                        node_id=def_id,
                        var_name=var_name,
                        file_path=file_path,
                        line_number=left.start_point.row + 1,
                        col_offset=left.start_point.column,
                        node_kind="ASSIGN_DEF",
                        expression_text=expr_text,
                        tainted=False,
                        taint_source=None,
                        ast_node=left,
                    )

                    if var_name in current_defs:
                        self.graph.add_edge(current_defs[var_name], def_id, flow_type="CONTAINER_MUTATE", operation="update")

                    for r_id in rhs_nodes:
                        self.graph.add_edge(r_id, def_id, flow_type="CONTAINER_ELEMENT", operation="set_item")

                    current_defs[var_name] = def_id
                    return
```

---

## 5. Verification Method

### A. Independent Verification Commands
```powershell
# 1. Verify prototype detection on Defect 3 and Defect 4 test cases
python d:\4th-year\Senior-Project\.agents\teamwork\explorer_m2_iter3_2\test_solutions.py

# 2. Run server unit tests (must remain 100% passing)
pytest codedee/codedee_server/tests -v

# 3. Verify adversarial tests after worker applies patch
pytest .agents/teamwork/challenger_m2_fix_1/test_adversarial_dfg_taint.py -v
```

### B. Invalidation Conditions
This design is invalidated if:
1. `"...".format(name=user)` with tainted `user` fails to produce a finding or drops `user` from `taint_path`.
2. `container = [user]; sql = "... %s" % container[0]` fails to report a `CRITICAL` unsanitized CWE-89 finding.
3. Existing 75 unit tests in `codedee/codedee_server/tests` produce any regression or failure.
