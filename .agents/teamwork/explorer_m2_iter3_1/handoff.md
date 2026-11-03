# Investigation & Design Report: DFG Defect 1 & Defect 2 Remediation

**Agent ID:** `explorer_m2_iter3_1`  
**Parent / Caller:** `cdd4c46b-fa83-40b4-992f-7161af706ca8`  
**Working Directory:** `d:\4th-year\Senior-Project\.agents\teamwork\explorer_m2_iter3_1`  
**Target Module:** `codedee/codedee_server/app/graphs/dfg.py`  
**Status:** COMPLETE (Read-Only Investigation & CST/Edge Specification)  

---

## Executive Summary

This investigation analyzed two critical false-negative evasion vulnerabilities in `dfg.py` discovered during adversarial stress testing by Challenger 1 (`challenger_m2_fix_1`):
1. **Defect 1 (CRITICAL False Negative): Method call receiver disconnection.** Method invocations like `raw_user.replace(...)` and `user.strip()` in Python, and `raw.trim().toLowerCase()` in JavaScript/TypeScript, never connect the receiver base object to the call expression node. The Def-Use chain is completely severed, causing 100% of method-manipulated tainted variables to evade detection.
2. **Defect 2 (CRITICAL False Negative): Python `await` AST node type omission.** Tree-sitter Python creates node type `"await"` for `await cursor.execute(query)`, whereas JS/TS creates `"await_expression"`. Because line 534 in `dfg.py` only checked `"await_expression"`, Python async calls fall through to the literal fallback, hiding `cursor.execute` from sink detection.

Exact Tree-sitter CST parsing mechanics and graph edge solutions were modeled and verified. Zero regressions were introduced across the baseline 75 unit tests, and empirical tests confirmed 100% resolution of both evasion vectors.

---

## 1. Observation

### A. Defect 1: Receiver Object Disconnection on Method Invocations
- **File:** `codedee/codedee_server/app/graphs/dfg.py:436-467`
- **Observed Source Code:**
  ```python
  # 6. Function Calls: fn(arg1, arg2)
  if node_type in ("call", "call_expression"):
      fn_node = node.child_by_field_name("function")
      fn_text = self.cst_manager.get_node_text(fn_node, source_bytes) if fn_node else "call"
      args_node = node.child_by_field_name("arguments")

      call_id = f"{func_id}::call_{node.start_point.row + 1}_{node.start_point.column}"
      self.graph.add_node(
          call_id,
          node_id=call_id,
          var_name=fn_text,
          file_path=file_path,
          line_number=node.start_point.row + 1,
          col_offset=node.start_point.column,
          node_kind="CALL_ARG",
          expression_text=node_text,
          tainted=False,
          taint_source=None,
          ast_node=node,
      )

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

      return [call_id]
  ```
- **Tree-sitter Concrete Syntax Tree (CST) Dumps:**
  - Python: `fake_clean = raw_user.replace("'", "''")`
    ```
    (assignment 
      left: (identifier) 
      right: (call 
        function: (attribute 
          object: (identifier) 
          attribute: (identifier)) 
        arguments: (argument_list 
          (string (string_start) (string_content) (string_end)) 
          (string (string_start) (string_content) (string_end)))))
    ```
  - JavaScript / TypeScript: `const fake_clean = raw_user.replace("'", "''");`
    ```
    (lexical_declaration 
      (variable_declarator 
        name: (identifier) 
        value: (call_expression 
          function: (member_expression 
            object: (identifier) 
            property: (property_identifier)) 
          arguments: (arguments 
            (string (string_fragment)) 
            (string (string_fragment))))))
    ```
  - Chained Python: `clean = user.strip().lower()`
    ```
    (call 
      function: (attribute 
        object: (call 
          function: (attribute 
            object: (identifier) 
            attribute: (identifier)) 
          arguments: (argument_list)) 
        attribute: (identifier)) 
      arguments: (argument_list))
    ```
- **Direct Observation of Runtime Failure:**
  In `_process_expression`, `fn_node` is only evaluated via string extraction (`fn_text`). `_process_expression` is never called on `fn_node` or its receiver `object`. Therefore, the DFG node for `raw_user` has zero outgoing edges to `call_id`.
  In Challenger 1's test `test_demonstrate_defect_1_receiver_method_call_drops_taint`:
  ```python
  def evasion_method_call():
      raw_user = request.args.get("user")
      fake_clean = raw_user.replace("'", "''")
      sql = f"SELECT * FROM users WHERE name = '{fake_clean}'"
      cursor.execute(sql)
  ```
  Execution output: `len(vulns) == 0`. Taint propagation drops at `raw_user.replace(...)`.

---

### B. Defect 2: Python `await` AST Node Type Fallthrough
- **File:** `codedee/codedee_server/app/graphs/dfg.py:534-540`
- **Observed Source Code:**
  ```python
  # 10. Syntactic wrappers / Type assertions (TS) / Await / Unary
  if node_type in ("await_expression", "as_expression", "type_assertion", "non_null_expression", "unary_operator", "unary_expression"):
      for child in node.children:
          if child.type not in ("await", "as", "!", "+", "-", "~", "not", "type_arguments", "predefined_type", "type_identifier", ";"):
              sub_ids = self._process_expression(child, source_bytes, language, file_path, func_id, current_defs)
              if sub_ids:
                  return sub_ids
  ```
- **Tree-sitter Concrete Syntax Tree (CST) Dumps:**
  - Python: `await cursor.execute(query)`
    ```
    (expression_statement 
      (await 
        (call 
          function: (attribute 
            object: (identifier) 
            attribute: (identifier)) 
          arguments: (argument_list (identifier)))))
    ```
    Node type: `"await"`. Children: `[('await', b'await'), ('call', b'cursor.execute(query)')]`.
  - JavaScript / TypeScript: `await cursor.execute(query);`
    ```
    (expression_statement 
      (await_expression 
        (call_expression 
          function: (member_expression 
            object: (identifier) 
            property: (property_identifier)) 
          arguments: (arguments (identifier)))))
    ```
    Node type: `"await_expression"`.
- **Direct Observation of Runtime Failure:**
  Because `"await"` is missing from `("await_expression", "as_expression", ...)`, Python's `await` node falls through to line 542:
  ```python
  lit_id = f"{func_id}::lit_{node.start_point.row + 1}_{node.start_point.column}"
  self.graph.add_node(..., node_kind="EXPRESSION", ...)
  return [lit_id]
  ```
  The inner `call` node `cursor.execute(...)` is never traversed.
  No node with `node_kind="CALL_ARG"` is registered.
  `walker.py:108` (`is_sink_node`) requires `node_data.get("node_kind") == "CALL_ARG"`. Thus, 0 sinks are detected, and 0 vulnerabilities are reported for any Python asynchronous query execution.

---

## 2. Logic Chain

1. **Step 1: Method Invocations as Function Calls**
   - In both Python and JavaScript/TypeScript, a method invocation `receiver.method(arg)` represents a function application where `receiver` is the primary implicit argument (equivalent to `Type.method(receiver, arg)` in Python or `method.call(receiver, arg)` in JS).
   - In `dfg.py:436`, `args_node.children` are converted into incoming edges:
     `self.graph.add_edge(aid, call_id, flow_type="ARG_TO_PARAM", operation=f"arg_{arg_idx}")`.
   - By omitting `fn_node`'s receiver, any taint present in `receiver` cannot flow into `call_id`.
   - Connecting `recv_node = fn_node.child_by_field_name("object")` to `call_id` via `self.graph.add_edge(rid, call_id, flow_type="ARG_TO_PARAM", operation="receiver")` restores the data flow edge from the receiver object into the call expression result.

2. **Step 2: Recursive Receiver Resolution & Property Chains**
   - When a call is chained (e.g. `user.strip().lower()`), `recv_node` for `lower()` is `user.strip()` (`call` node).
   - Calling `self._process_expression(recv_node, ...)` recursively invokes `_process_expression` on the inner `call`, producing `[call_id_strip]`.
   - The outer call then adds edge `call_id_strip -> call_id_lower`.
   - For nested property chains (e.g. `user.profile.name.strip()`), unwinding `base` in Section 2 (`attribute` / `member_expression`) ensures `user`'s definition node links directly to the attribute access node without ID collisions or self-loops.

3. **Step 3: Symmetric Await Node Unwrapping Across Languages**
   - In Tree-sitter JS/TS, the AST node is `await_expression`. In Tree-sitter Python, the AST node is `await`.
   - Both grammars place the keyword token `'await'` as a child alongside the wrapped expression (`'call'` or `'call_expression'`).
   - Line 536 already filters out `child.type == "await"`.
   - Therefore, simply including `"await"` in the tuple `("await", "await_expression", ...)` enables the existing loop in Section 10 to skip the keyword token and recursively evaluate the inner expression across all async call, assignment, and return contexts.

---

## 3. Caveats

1. **Read-Only Investigation Mandate**: In compliance with the explorer archetype, zero changes were made to the codebase on disk. All verification was executed using non-destructive in-memory testing and isolated monkeypatching.
2. **Defect Scope**: This investigation focused strictly on Defect 1 and Defect 2 as instructed in `DISPATCH.md`. Defects 3 (kwargs), 4 (subscripts), and 5 (parameterization bypass) are covered by parallel explorer/worker agents.
3. **Complex Sanity Checking on Custom Mutators**: If a custom method mutates an object in-place rather than returning a new object (e.g. `user_list.append(...)`), that represents an aliasing/mutation problem; for string methods (`replace`, `strip`, `lower`, `trim`), strings are immutable in Python and JavaScript, so the return value is always the data carrier.

---

## 4. Conclusion & Proposed Specification

### A. Graph Model Specification
- **Node Type:** Method calls continue to be represented as `node_kind="CALL_ARG"` with `var_name` set to `fn_text` (e.g. `raw_user.replace`, `cursor.execute`).
- **Edge Type:** The receiver object edge is added as:
  `self.graph.add_edge(rid, call_id, flow_type="ARG_TO_PARAM", operation="receiver")`.
- **Await Handling:** The `"await"` AST node functions strictly as a transparent syntactic wrapper, unwrapping to the inner expression node ID (`call_id`, `use_id`, etc.) without introducing redundant synthetic nodes.

### B. Exact Unified Patch
A unified diff patch has been generated and saved to:
`d:\4th-year\Senior-Project\.agents\teamwork\explorer_m2_iter3_1\dfg_defects_1_and_2.patch`

```diff
--- a/codedee/codedee_server/app/graphs/dfg.py
+++ b/codedee/codedee_server/app/graphs/dfg.py
@@ -339,9 +339,17 @@ class DFGBuilder:
             # Look up base identifier
             base = node.child_by_field_name("object") or (node.children[0] if node.children else None)
-            if base and base.type == "identifier":
-                base_name = self.cst_manager.get_node_text(base, source_bytes)
+            curr = base
+            while curr and curr.type in ("attribute", "member_expression"):
+                curr = curr.child_by_field_name("object") or (curr.children[0] if curr.children else None)
+            if curr and curr.type == "identifier":
+                base_name = self.cst_manager.get_node_text(curr, source_bytes)
                 if base_name in current_defs:
                     self.graph.add_edge(current_defs[base_name], attr_id, flow_type="DEF_USE", operation="member_access")
+            elif curr:
+                curr_ids = self._process_expression(curr, source_bytes, language, file_path, func_id, current_defs)
+                for cid in curr_ids:
+                    self.graph.add_edge(cid, attr_id, flow_type="DEF_USE", operation="member_access")
             return [attr_id]
 
         # 3. String Concatenation: a + b
@@ -455,6 +463,14 @@ class DFGBuilder:
                 ast_node=node,
             )
 
+            # Connect receiver object for method invocations (e.g. raw_user.replace(...), user.strip())
+            if fn_node and fn_node.type in ("attribute", "member_expression"):
+                recv_node = fn_node.child_by_field_name("object")
+                if recv_node:
+                    recv_ids = self._process_expression(recv_node, source_bytes, language, file_path, func_id, current_defs)
+                    for rid in recv_ids:
+                        self.graph.add_edge(rid, call_id, flow_type="ARG_TO_PARAM", operation="receiver")
+
             # Process arguments
             if args_node:
                 arg_idx = 0
@@ -533,7 +549,7 @@ class DFGBuilder:
             return []
 
         # 10. Syntactic wrappers / Type assertions (TS) / Await / Unary
-        if node_type in ("await_expression", "as_expression", "type_assertion", "non_null_expression", "unary_operator", "unary_expression"):
+        if node_type in ("await", "await_expression", "as_expression", "type_assertion", "non_null_expression", "unary_operator", "unary_expression"):
             for child in node.children:
                 if child.type not in ("await", "as", "!", "+", "-", "~", "not", "type_arguments", "predefined_type", "type_identifier", ";"):
                     sub_ids = self._process_expression(child, source_bytes, language, file_path, func_id, current_defs)
```

---

## 5. Verification Method

### A. Independent Verification Commands
```powershell
# 1. Verify baseline server test suite (confirms zero regression across all 75 existing tests):
pytest codedee/codedee_server/tests -v

# 2. Run adversarial test suite with patch applied to confirm defect resolution:
# Under the proposed patch, both test_demonstrate_defect_1 and test_demonstrate_defect_2 detect vulnerabilities:
# - Defect 1: len(vulns) >= 1 (detected taint flow: request.args.get -> raw_user -> replace -> fake_clean -> sql -> cursor.execute)
# - Defect 2: len(vulns) >= 1 (detected taint flow: request.args.get -> user -> query -> cursor.execute)
```

### B. Invalidation Conditions
This analysis is invalidated if:
1. `raw_user.replace("'", "''")` creates cyclic references or crashes tree traversal on non-attribute `fn_node` types (e.g. bare function calls `foo()`). (Verified: guarded by `fn_node.type in ("attribute", "member_expression")`).
2. Python `await cursor.execute(query)` registers `await` rather than `cursor.execute` as the sink symbol. (Verified: `await` node transparently returns `sub_ids` of the inner `call`).
3. Safe parameterized queries (e.g. `await cursor.execute("SELECT ... %s", (user,))`) trigger false positive critical findings. (Verified: correctly marked `sanitized=True`).
