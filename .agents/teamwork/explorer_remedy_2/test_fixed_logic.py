import re
import pytest
from codedee.codedee_server.app.taint.walker import SymbolicTaintWalker

class FixedTaintWalker(SymbolicTaintWalker):
    def is_sink_parameterized(self, sink_node_data, code_line: str) -> bool:
        line_clean = code_line.strip()
        
        # If call is to execute_filtered_query, it never takes parameter bindings
        if "execute_filtered_query" in line_clean:
            return False

        # If line uses direct interpolation outside secondary parameter containers [...], (...), it's vulnerable
        outside_containers = re.sub(r",\s*\[[^\]]*\]", "", line_clean)
        outside_containers = re.sub(r",\s*\([^)]*\)", "", outside_containers)
        outside_containers = re.sub(r",\s*\{[^}]*\}", "", outside_containers)
        if "f\"" in outside_containers or "f'" in outside_containers or "${" in outside_containers:
            return False

        # If line contains direct concatenation (+) with SQL keywords
        if "+" in outside_containers and any(k in outside_containers.upper() for k in ["SELECT", "WHERE", "INSERT", "UPDATE", "DELETE", "FROM"]):
            return False

        # If line contains % formatting without secondary parameter container
        if "%" in line_clean and not re.search(r",\s*(?:\(|\[|\{|[a-zA-Z_][a-zA-Z0-9_]*)", line_clean):
            return False

        # Strip JavaScript/TypeScript callback functions before checking for parameter container
        cleaned = re.sub(r",\s*(?:async\s+)?(?:\([^)]*\)|[a-zA-Z0-9_]+)\s*=>.*", "", line_clean, flags=re.DOTALL)
        cleaned = re.sub(r",\s*function\s*\(.*", "", cleaned, flags=re.DOTALL)

        # 1. Reject empty parameter containers: (), [], {}, tuple(), list(), dict(), None, null, undefined
        if re.search(
            r",\s*(?:\(\s*\)|\[\s*\]|\{\s*\}|tuple\s*\(\s*\)|list\s*\(\s*\)|dict\s*\(\s*\)|None|null|undefined)\s*(?:\)|,|$)",
            cleaned,
        ):
            return False

        # 2. Require non-empty container contents or parameter variable identifiers:
        # e.g. cursor.execute(query, (param1, param2)), db.query(sql, [param1]), cursor.execute(sql, {"user": user}),
        # or cursor.execute(query, params) / db.query(sql, values)
        # Note: Do not match string literals like "inventory"
        if re.search(r",\s*(?:\(\s*[^)\s]|\[\s*[^\]\s]|\{\s*[^}\s]|[a-zA-Z_][a-zA-Z0-9_]*)", cleaned):
            return True

        return False

# Test the fixed walker on our tests:
w = FixedTaintWalker()

# 1. Test execute_filtered_query with inline fstring
res1 = w.is_sink_parameterized({}, 'execute_filtered_query(conn, "inventory", f"category = \'{search_term}\'")')
print(f"Test 1 (inline fstring): is_sink_parameterized = {res1} (expected: False)")

# 2. Test execute_filtered_query with variable clause
res2 = w.is_sink_parameterized({}, 'execute_filtered_query(conn, "inventory", clause)')
print(f"Test 2 (var clause): is_sink_parameterized = {res2} (expected: False)")

# 3. Test safe parameterized query
res3 = w.is_sink_parameterized({}, 'cursor.execute("SELECT * FROM users WHERE id = %s", (user,))')
print(f"Test 3 (safe parameterized): is_sink_parameterized = {res3} (expected: True)")

# 4. Test safe param variable
res4 = w.is_sink_parameterized({}, 'cursor.execute("SELECT * FROM users WHERE id = %s", params)')
print(f"Test 4 (safe param var): is_sink_parameterized = {res4} (expected: True)")

# 5. Test empty tuple
res5 = w.is_sink_parameterized({}, 'cursor.execute(sql, ())')
print(f"Test 5 (empty tuple): is_sink_parameterized = {res5} (expected: False)")

# 6. Test direct fstring in cursor.execute
res6 = w.is_sink_parameterized({}, 'cursor.execute(f"SELECT * FROM users WHERE id = {user}", (user,))')
print(f"Test 6 (fstring in execute): is_sink_parameterized = {res6} (expected: False)")
