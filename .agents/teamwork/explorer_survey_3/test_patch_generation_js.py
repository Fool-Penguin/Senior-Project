import json
import requests
import time

OLLAMA_API = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "qwen2.5-coder:7b"

patch_prompt_js = """You are CodeDEE's Automated Security Program Repair (APR) engine.
Fix the SQL Injection (CWE-89) in the provided JavaScript (node-postgres) function.

STRICT CONSTRAINTS:
1. Preserve the exact function signature: `async function getUserProfile(req, res)`
2. Replace dynamic SQL concatenation with parameterized query placeholder `$1` and pass `[userId]` in parameter array.
3. Keep the code clean, maintainable, and syntactically valid.
4. Output ONLY the fixed JavaScript function inside a ```javascript ... ``` markdown block. No explanations.

[Vulnerable Code]
```javascript
async function getUserProfile(req, res) {
    const userId = req.query.id;
    const client = new Client();
    await client.connect();
    const query = "SELECT * FROM profiles WHERE user_id = '" + userId + "'";
    const result = await client.query(query);
    res.json(result.rows);
}
```
"""

print("Testing JS Patch Generation...")
t0 = time.time()
resp = requests.post(
    OLLAMA_API,
    json={
        "model": MODEL_NAME,
        "prompt": patch_prompt_js,
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
    print("Generated JS Patch:\n", output_text)
else:
    print("Ollama error:", resp.status_code, resp.text)
