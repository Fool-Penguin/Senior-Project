from codedee.codedee_server.app.taint.walker import SymbolicTaintWalker

w = SymbolicTaintWalker()
line = 'results = execute_filtered_query(conn, "inventory", f"category = \'{search_term}\'")'
res = w.is_sink_parameterized({}, line)
print(f"is_sink_parameterized returned: {res}")

import re
line_clean = line.strip()
sink_match = re.search(r"(?:execute|executemany|query|raw|rawQuery)\s*\(\s*([^,]+)", line_clean)
print(f"sink_match: {sink_match}")
if sink_match:
    print(f"group(0): {sink_match.group(0)}")
    print(f"group(1): {sink_match.group(1)}")

cleaned = re.sub(r",\s*(?:async\s+)?(?:\([^)]*\)|[a-zA-Z0-9_]+)\s*=>.*", "", line_clean, flags=re.DOTALL)
cleaned = re.sub(r",\s*function\s*\(.*", "", cleaned, flags=re.DOTALL)
param_container_match = re.search(r",\s*(?:\(\s*[^)\s]|\[\s*[^\]\s]|\{\s*[^}\s]|[a-zA-Z_][a-zA-Z0-9_]*)", cleaned)
print(f"param_container_match: {param_container_match}")
