import json
import requests
import time

OLLAMA_API = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "qwen2.5-coder:7b"

assessment_prompt = """You are CodeDEE's Neural Security Oracle.
Evaluate the following symbolic finding for potential false positives or true positives.

[Target Context]
Language: python
Vulnerability: CWE-89 (SQL Injection)
Symbolic Taint Path: user_id -> query (via f-string) -> cursor.execute(query)

[Vulnerable Function Slice]
```python
def find_user_by_id(user_id: int):
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    cursor.execute(query)
    return cursor.fetchone()
```

Provide your assessment strictly in the following JSON format:
{
  "confidence_score": <float between 0.0 and 1.0>,
  "risk_level": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
  "sanitizer_detected": <true or false>,
  "sanitizer_details": <string or null>,
  "is_false_positive": <true or false>,
  "reasoning": "<concise explanation of why the vulnerability is genuine or sanitized>"
}
"""

print("Testing Assessment Mode...")
t0 = time.time()
resp = requests.post(
    OLLAMA_API,
    json={
        "model": MODEL_NAME,
        "prompt": assessment_prompt,
        "stream": False,
        "format": "json"
    },
    timeout=60
)
t1 = time.time()
print(f"Elapsed: {t1 - t0:.2f}s")
if resp.status_code == 200:
    res_data = resp.json()
    print("Raw response:\n", res_data.get("response"))
    try:
        parsed = json.loads(res_data.get("response"))
        print("Parsed JSON successfully:", parsed)
    except Exception as e:
        print("JSON parse error:", e)
else:
    print("Ollama error:", resp.status_code, resp.text)
