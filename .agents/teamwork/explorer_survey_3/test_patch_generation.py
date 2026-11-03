import json
import requests
import time
import re

OLLAMA_API = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "qwen2.5-coder:7b"

patch_prompt = """You are CodeDEE's Automated Security Program Repair (APR) engine.
Fix the SQL Injection (CWE-89) in the provided Python function.

STRICT CONSTRAINTS:
1. Preserve the exact function signature: `def find_user_by_id(user_id: int):`
2. Replace dynamic SQL string formatting with safe parameterized query placeholder `?` and pass `(user_id,)` as tuple argument.
3. Keep the code clean, maintainable, and syntactically valid.
4. Output ONLY the fixed Python function inside a ```python ... ``` markdown block. No explanations.

[Vulnerable Code]
```python
def find_user_by_id(user_id: int):
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    cursor.execute(query)
    return cursor.fetchone()
```
"""

print("Testing Patch Generation...")
t0 = time.time()
resp = requests.post(
    OLLAMA_API,
    json={
        "model": MODEL_NAME,
        "prompt": patch_prompt,
        "stream": False,
        "options": {
            "temperature": 0.2
        }
    },
    timeout=60
)
t1 = time.time()
print(f"Elapsed: {t1 - t0:.2f}s")
if resp.status_code == 200:
    res_data = resp.json()
    output_text = res_data.get("response")
    print("Generated Patch:\n", output_text)
else:
    print("Ollama error:", resp.status_code, resp.text)
