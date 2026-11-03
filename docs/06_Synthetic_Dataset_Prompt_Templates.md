# Synthetic Dataset Generation — Prompt Templates
## CodeDEE Task 2: Reproducible GenAI Pipeline

> **Document Purpose:** All synthetic code samples added to the CodeDEE security dataset were generated using the prompt templates in this document. Providing these templates ensures full reproducibility for academic peer review and thesis committee evaluation.

> [!IMPORTANT]
> Only use synthetic samples for vulnerability types where real-world CVE data is unavailable or insufficient (< 5 samples). Synthetic samples are clearly tagged with `"source_type": "synthetic_llm"` in the dataset.

---

## 1. Pipeline Overview

```
Vulnerability Catalogue Entry
        │
        ▼
Template Selection (TMPL-{CWE}-{LANG}-{VER})
        │
        ▼
LLM Generation (GPT-4o / Claude 3.5 Sonnet)
        │
        ▼
Automated Validation (AST parse, not crashing, contains sink)
        │
        ▼
Manual Expert Review (confirm taint flow is genuine)
        │
        ▼
Dataset Entry with source_type="synthetic_llm"
```

### Model Used
- **Primary:** OpenAI GPT-4o (temperature=0.3, top_p=0.95)
- **Secondary / Validation:** Anthropic Claude 3.5 Sonnet
- **Purpose of low temperature:** Reduce hallucination while keeping code diversity

---

## 2. Master Prompt Structure

All prompts follow this 4-part structure:

```
PART 1 — ROLE
You are a security research engineer generating labeled code samples for a 
static analysis benchmark dataset. Your output will be used to train and 
evaluate a vulnerability detection tool.

PART 2 — TASK
Generate a [VULNERABLE | FIXED] {LANGUAGE} code snippet that exhibits {CWE_NAME} 
({CWE_ID}), mapped to {OWASP_CATEGORY}. The snippet must:
  1. Be a realistic, runnable function or route handler (not pseudocode).
  2. Contain an explicit source → sink taint flow (for vulnerable variants).
  3. Be approximately 10–30 lines long.
  4. Include a one-line comment marking the vulnerability point.

PART 3 — CONSTRAINTS
- Language: {LANGUAGE} ({FRAMEWORK} preferred, e.g., Flask/Express).
- The vulnerability must be statically detectable (no runtime-only issues).
- Do NOT add any preamble or explanation — output only the code.
- The fixed variant must apply the canonical remediation from the OWASP 
  Cheat Sheet for {CWE_NAME}.

PART 4 — METADATA OUTPUT
After the code, output exactly this JSON block:
{
  "source_pattern": "<what carries the tainted data>",
  "sink_pattern": "<what executes/outputs the tainted data>",
  "sanitizer_pattern": "<what would sanitize it, or null>",
  "owasp_reference": "<OWASP Cheat Sheet URL>",
  "generation_model": "<model name + version>"
}
```

---

## 3. Vulnerability-Specific Templates

### TMPL-LLM01-PY-001 — Prompt Injection (Python/OpenAI)

**Target:** OWASP LLM01:2025 — Prompt Injection  
**Attribution:** OWASP Top 10 for LLM Applications 2025, LLM01 ([genai.owasp.org](https://genai.owasp.org/llmrisk/llm01-prompt-injection/))

```
ROLE: You are a security research engineer...

TASK: Generate a VULNERABLE Python function that demonstrates OWASP LLM01:2025 
Prompt Injection. The function should:
  - Accept a user-supplied string (from an HTTP request or function argument)
  - Pass it directly (or with trivial formatting) into the SYSTEM role of an 
    OpenAI chat completions call
  - Show how an attacker can override system instructions

CONSTRAINTS:
  - Use the `openai` Python library (>= 1.0 API style: client.chat.completions.create)
  - Framework: Flask route handler preferred
  - Do NOT sanitize the input — this is the vulnerable version

METADATA OUTPUT: {JSON block as above}
```

**Validated Pattern:**
- Source: `request.args.get(...)` or function parameter
- Sink: `messages=[{"role": "system", "content": "... " + user_input}]`
- Sanitizer (for fixed version): Separate system prompt from user message; never concatenate

---

### TMPL-LLM01-JS-001 — Prompt Injection (JavaScript/Node.js)

**Target:** OWASP LLM01:2025  
**Attribution:** Same as above

```
TASK: Generate a VULNERABLE JavaScript async route handler (Express.js) that 
demonstrates OWASP LLM01:2025 Prompt Injection. The handler should:
  - Read user input from req.body or req.query
  - Inject it into the system role of an OpenAI Node.js SDK call 
    (openai.chat.completions.create)
  - NOT validate or sanitize the input
```

---

### TMPL-LLM02-PY-001 — Sensitive Information Disclosure (Python)

**Target:** OWASP LLM02:2025 — Sensitive Information Disclosure  
**Attribution:** OWASP Top 10 for LLM Applications 2025, LLM02 ([genai.owasp.org](https://genai.owasp.org/llmrisk/llm02-sensitive-information-disclosure/))

```
TASK: Generate a VULNERABLE Python function that demonstrates OWASP LLM02:2025 
Sensitive Information Disclosure. The function should:
  - Read one or more secrets from os.environ (e.g., DB_PASSWORD, API_KEY, 
    ADMIN_TOKEN)
  - Embed those secrets into the system prompt or context window of an LLM call
  - Risk: the LLM may echo secrets back to users, or logs may capture them

CONSTRAINTS:
  - Use os.environ.get() as the secret source
  - Inject via f-string or string concatenation into the messages list
  - The LLM call should use the openai Python SDK
```

**Validated Pattern:**
- Source: `os.environ.get('DB_PASSWORD')`, `os.environ.get('API_KEY')`
- Sink: f-string interpolation into `messages[0]["content"]` (system role)
- Sanitizer: Keep system prompt static; never put secrets in LLM context

---

### TMPL-LLM02-JS-001 — Sensitive Information Disclosure (JavaScript)

**Target:** OWASP LLM02:2025  
**Attribution:** Same as above

```
TASK: Generate a VULNERABLE JavaScript Express route handler demonstrating 
OWASP LLM02:2025 Sensitive Information Disclosure where:
  - process.env credentials (DB_CONNECTION_STRING, ADMIN_TOKEN, etc.) are 
    embedded into the OpenAI system prompt via template literals
  - The handler is publicly accessible (not admin-only)
```

---

### TMPL-CWE94-PY-001 — Code Injection via eval() (Python)

**Target:** CWE-94 / OWASP A03:2021-Injection  
**Attribution:**  
  - CWE-94: [cwe.mitre.org/data/definitions/94](https://cwe.mitre.org/data/definitions/94.html)  
  - Sanitizer pattern: OWASP Cheat Sheet — [Injection Prevention in Python](https://cheatsheetseries.owasp.org/cheatsheets/Injection_Prevention_Cheat_Sheet.html)

```
TASK: Generate a VULNERABLE Flask route handler in Python that demonstrates 
CWE-94 Code Injection. The handler should:
  - Accept user input from request.args or request.json
  - Pass it directly to Python's built-in eval() or exec() function
  - Return or display the result

FIXED VERSION must:
  - Use ast.parse() + a whitelist of safe operations (arithmetic only)
  - Raise ValueError for disallowed node types
```

---

### TMPL-CWE94-JS-001 — Code Injection via new Function() (JavaScript)

**Target:** CWE-94 / OWASP A03:2021-Injection  
**Attribution:**  
  - CWE-94: [cwe.mitre.org/data/definitions/94](https://cwe.mitre.org/data/definitions/94.html)
  - Sink source: MDN Web Docs — [Function constructor](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Function/Function)

```
TASK: Generate a VULNERABLE Express.js route handler in JavaScript that 
demonstrates CWE-94 Code Injection where:
  - User input from req.query or req.body is passed to `new Function(code)()` 
    or `eval(code)`
  - No sanitization or validation is performed

FIXED VERSION must:
  - Use a strict whitelist lookup (e.g., a Map of allowed function names)
  - Return 400 for any unlisted operation
```

---

### TMPL-CWE611-PY-001 — XXE via xml.etree (Python)

**Target:** CWE-611 / OWASP A05:2021-Security Misconfiguration  
**Attribution:**  
  - CWE-611: [cwe.mitre.org/data/definitions/611](https://cwe.mitre.org/data/definitions/611.html)  
  - Sanitizer: OWASP XXE Prevention Cheat Sheet ([cheatsheetseries.owasp.org](https://cheatsheetseries.owasp.org/cheatsheets/XML_External_Entity_Prevention_Cheat_Sheet.html))  
  - defusedxml library: [pypi.org/project/defusedxml](https://pypi.org/project/defusedxml/)

```
TASK: Generate a VULNERABLE Flask POST route handler in Python that demonstrates 
CWE-611 XML External Entity (XXE) Injection:
  - Read raw XML from request.data
  - Parse it using the standard library xml.etree.ElementTree.fromstring()
  - Note that ElementTree in Python 3.8+ partially mitigates XXE, but lxml 
    does not — generate an lxml.etree variant too

FIXED VERSION must:
  - Replace with defusedxml.ElementTree.fromstring()
  - Comment explaining why defusedxml is necessary
```

---

### TMPL-CWE327-PY-001 — Broken Cryptographic Algorithm (Python)

**Target:** CWE-327 / OWASP A02:2021-Cryptographic Failures  
**Attribution:**  
  - CWE-327: [cwe.mitre.org/data/definitions/327](https://cwe.mitre.org/data/definitions/327.html)  
  - OWASP Cryptographic Storage Cheat Sheet: [cheatsheetseries.owasp.org](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)

```
TASK: Generate a VULNERABLE Python function demonstrating CWE-327 Use of a 
Broken Cryptographic Algorithm:
  - Hash a password using hashlib.md5() or hashlib.sha1() without salt
  - Store the result as a user's password hash

FIXED VERSION must:
  - Use bcrypt or argon2-cffi for password hashing
  - Include a random salt
  - Explain the minimum cost factor
```

---

### TMPL-CWE502-JS-001 — Insecure Deserialization (JavaScript)

**Target:** CWE-502 / OWASP A08:2021-Software and Data Integrity Failures  
**Attribution:**  
  - CWE-502: [cwe.mitre.org/data/definitions/502](https://cwe.mitre.org/data/definitions/502.html)  
  - Node.js serialize-javascript / node-serialize attack: [opsecx.com](https://opsecx.com/index.php/2017/02/08/exploiting-node-js-deserialization-bug-for-remote-code-execution/) (Ajin Abraham, 2017)

```
TASK: Generate a VULNERABLE Express.js route handler demonstrating CWE-502 
Deserialization of Untrusted Data in JavaScript/Node.js:
  - Use the `node-serialize` package to deserialize user-supplied JSON
  - Show how an IIFE payload in serialized function strings enables RCE

FIXED VERSION must:
  - Use JSON.parse() only (no executable function deserialization)
  - Apply a JSON Schema validator (e.g., ajv) to enforce expected shape
```

---

### TMPL-LLM05-PY-001 — Improper Output Handling (Shell Execution)

**Target:** OWASP LLM05:2025 / CWE-1427 / CWE-78  
**Attribution:** OWASP Top 10 for LLM Applications 2025, LLM05 ([genai.owasp.org](https://genai.owasp.org/llmrisk/llm05-improper-output-handling/))

```
TASK: Generate a VULNERABLE Python function where:
  - An LLM completion output (resp.choices[0].message.content) is passed 
    directly into a shell execution sink: subprocess.check_output(cmd, shell=True)
  - No allowlisting or syntax validation is applied.

FIXED VERSION must:
  - Use OpenAI Structured Outputs API with a Pydantic schema (BaseModel)
  - Validate action against an immutable ALLOWED_COMMANDS allowlist
  - Execute without shell=True
```

---

### TMPL-LLM05-JS-001 — Improper Output Handling (DOM XSS Injection)

**Target:** OWASP LLM05:2025 / CWE-1427 / CWE-79  
**Attribution:** Same as above

```
TASK: Generate a VULNERABLE Express.js route handler in JavaScript where:
  - The raw string completion from an LLM is returned directly inside 
    an unescaped HTML template: res.send(`<div>${answer}</div>`)
  - No HTML escaping or DOM sanitization is performed.

FIXED VERSION must:
  - Apply DOMPurify.sanitize() before output or return structured JSON via res.json()
```

---

### TMPL-LLM05-TS-001 — Improper Output Handling (Markdown / SSR)

**Target:** OWASP LLM05:2025 / CWE-1427 / CWE-79  
**Attribution:** Same as above

```
TASK: Generate a VULNERABLE TypeScript service function that:
  - Renders raw LLM Markdown into an unescaped HTML container string intended 
    for dangerouslySetInnerHTML in frontend components.

FIXED VERSION must:
  - Sanitize output using isomorphic-dompurify before returning the markup.
```

---

### TMPL-LLM07-PY-001 — System Prompt Leakage (Debug Endpoint)

**Target:** OWASP LLM07:2025 / CWE-200  
**Attribution:** OWASP Top 10 for LLM Applications 2025, LLM07 ([genai.owasp.org](https://genai.owasp.org/llmrisk/llm07-system-prompt-leakage/))

```
TASK: Generate a VULNERABLE Flask API endpoint in Python where:
  - A proprietary system instructions string constant is exposed directly via 
    an unauthenticated GET route (/api/debug/system-prompt).

FIXED VERSION must:
  - Eliminate or disable the route in production builds (abort(404)).
```

---

### TMPL-LLM07-JS-001 — System Prompt Leakage (Public Config Route)

**Target:** OWASP LLM07:2025 / CWE-200  
**Attribution:** Same as above

```
TASK: Generate a VULNERABLE Express.js route in JavaScript where:
  - An agentConfig object containing the private systemPrompt is serialized 
    directly to clients via res.json(agentConfig).

FIXED VERSION must:
  - Strip the systemPrompt property and return only public model metadata.
```

---

### TMPL-LLM07-TS-001 — System Prompt Leakage (Diagnostics Health Check)

**Target:** OWASP LLM07:2025 / CWE-200  
**Attribution:** Same as above

```
TASK: Generate a VULNERABLE TypeScript controller where:
  - A private class member this.systemPrompt is returned inside a diagnostic 
    health check endpoint payload.

FIXED VERSION must:
  - Restrict health check output strictly to operational uptime and status.
```

---

## 3.5. Production Multi-Sample Batch Prompt Templates (Executed Oct 2026)

The following two comprehensive batch prompt templates were utilized to generate the **16 verified synthetic samples** (`SYNTH-PY-LLM01-01` through `SYNTH-JS-LLM07-08`) covering modern frameworks (FastAPI, Flask, Express.js, Next.js, LangChain, LlamaIndex, Vercel AI SDK).

### Template A: Batch 1 — Python Suite (8 Distinct Samples)

```markdown
You are a Principal Software Security Researcher and Data Engineer creating an academic benchmark dataset for the OWASP Top 10 for LLM Applications (2025).

TASK:
Generate a diverse batch of 8 DISTINCT, HIGH-QUALITY code samples in PYTHON covering the 4 in-scope OWASP LLM 2025 categories (2 samples per category).

CATEGORIES & VARIATIONS TO COVER:
1. LLM01: Prompt Injection (2 distinct samples)
   - Sample 1: FastAPI + Raw OpenAI SDK (Direct string concatenation into prompt)
   - Sample 2: Flask + LangChain PromptTemplate (User input injected into template without variable isolation)

2. LLM02: Sensitive Information Disclosure (2 distinct samples)
   - Sample 3: FastAPI + LlamaIndex RAG pipeline (Retrieving multi-tenant confidential internal documents without ACL filtering)
   - Sample 4: Flask + Database Lookup (Injecting unmasked user PII/passwords into prompt context window)

3. LLM05: Improper Output Handling (2 distinct samples)
   - Sample 5: FastAPI + Code Execution Agent (LLM generates Python code passed directly to eval() or exec())
   - Sample 6: Flask + SQL Generator (LLM generates raw SQL executed directly via sqlite3/cursor.execute without parameterization)

4. LLM07: System Prompt Leakage (2 distinct samples)
   - Sample 7: FastAPI (Debug inspection endpoint returning confidential system instructions to public requests)
   - Sample 8: Flask (Chat endpoint lacking guardrails against prompt extraction jailbreaks, returning system prompt content)

STRICT REQUIREMENTS FOR EVERY SAMPLE (1 to 8):
For each of the 8 samples, you MUST provide:
1. Sample ID: e.g. `SYNTH-PY-LLM01-01`
2. Category: e.g. `LLM01:2025 - Direct Prompt Injection`
3. Framework: e.g. `FastAPI + OpenAI SDK`
4. Vulnerable Code (15-30 lines, realistic, self-contained endpoint):
   - Clearly mark `# [SOURCE]` and `# [SINK]`
5. Ground Truth Remediated Code (The secure canonical fix):
   - Clearly mark `# [SANITIZER / FIX]`
6. CVSS v3.1 Base Score & Vector string (e.g., 7.5, CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N)

FORMAT:
Output the 8 samples sequentially using clean Markdown code blocks. Ensure all code is syntactically valid Python 3.10+.
```

### Template B: Batch 2 — JavaScript & TypeScript Suite (8 Distinct Samples)

```markdown
You are a Principal Software Security Researcher and Data Engineer creating an academic benchmark dataset for the OWASP Top 10 for LLM Applications (2025).

TASK:
Generate a diverse batch of 8 DISTINCT, HIGH-QUALITY code samples in JAVASCRIPT & TYPESCRIPT covering the 4 in-scope OWASP LLM 2025 categories (2 samples per category).

CATEGORIES & VARIATIONS TO COVER:
1. LLM01: Prompt Injection (2 distinct samples)
   - Sample 1 (TypeScript): Express.js + OpenAI SDK (Template literal embedding req.body into system prompt)
   - Sample 2 (JavaScript): Next.js Route Handler + Vercel AI SDK (Unsanitized user chat message overriding instructions)

2. LLM02: Sensitive Information Disclosure (2 distinct samples)
   - Sample 3 (TypeScript): Express.js + Vector Store Retrieval (Feeding cross-tenant private user documents into LLM context without tenant ID check)
   - Sample 4 (JavaScript): Node.js + LangChain.js (LLM prompt populated with unredacted environment secrets or customer PII)

3. LLM05: Improper Output Handling (2 distinct samples)
   - Sample 5 (TypeScript): Express.js + child_process (LLM output used directly as shell arguments in exec())
   - Sample 6 (JavaScript): Next.js API + Raw Database Query (LLM response passed directly into db.query() or innerHTML rendering)

4. LLM07: System Prompt Leakage (2 distinct samples)
   - Sample 7 (TypeScript): Express.js (Public API route returning server-side system prompt configuration object)
   - Sample 8 (JavaScript): Node.js (Chat handler echoing back internal system prompt upon adversarial user extraction attempt)

STRICT REQUIREMENTS FOR EVERY SAMPLE (1 to 8):
For each of the 8 samples, you MUST provide:
1. Sample ID: e.g. `SYNTH-TS-LLM01-01`
2. Category: e.g. `LLM01:2025 - Direct Prompt Injection`
3. Framework: e.g. `Express.js + TypeScript`
4. Vulnerable Code (15-30 lines, realistic, self-contained endpoint):
   - Clearly mark `// [SOURCE]` and `// [SINK]`
5. Ground Truth Remediated Code (The secure canonical fix):
   - Clearly mark `// [SANITIZER / FIX]`
6. CVSS v3.1 Base Score & Vector string (e.g., 7.5, CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N)

FORMAT:
Output the 8 samples sequentially using clean Markdown code blocks. Ensure all code is syntactically valid modern JS/TS.
```

---

## 4. Validation Checklist (Per Generated Sample)

Before adding any synthetic sample to the dataset, verify:

| Check | Pass Criteria |
|-------|---------------|
| Syntax valid | Code parses without error (`ast.parse()` / `babel.parse()` / Tree-sitter) |
| Taint flow explicit | A human reviewer can trace source → sink in ≤ 3 steps |
| Realistic framework | Uses Flask, FastAPI, Express, or modern OpenAI SDK v1+ |
| Correct CWE mapping | CWE ID matches the actual vulnerability, not a superficial pattern |
| Fixed version compiles | Remediated code runs without import errors |
| Source cited | `notes` field includes OWASP reference and generation model |

---

## 5. AI vs. Real-Repo Comparison (Empirical Summary)

| Metric | Real-World Repos (CVEfixes) | GenAI Synthetic (Task 2 Suite) | Human-Curated (Custom Suite) |
|--------|:---:|:---:|:---:|
| **Sample Count ($N$)** | **1,728** | **24** | **1,147** |
| **Mean LOC** | **99.2 lines** | **14.3 lines** | **15.9 lines** |
| **Median LOC** | **6 lines** | **14 lines** | **14 lines** |
| **Mean Cyclomatic Complexity** | **292.1** | **1.7** | **2.8** |
| **AST Parse Validity** | **94.8%** | **100.0%** | **99.1%** |
| **Canonical Fix Completeness** | **99.1%** | **100.0%** | **4.4%** |
| **Explicit Taint Ground Truth** | **100.0%** | **100.0%** | **48.3%** |

> [!TIP]
> See [09_Task2_Synthetic_vs_Real_Repo_Empirical_Comparison.md](file:///d:/4th-year/Senior-Project/docs/09_Task2_Synthetic_vs_Real_Repo_Empirical_Comparison.md) for the full empirical benchmark breakdown and statistical methodology.

---

## 6. Citation

If referencing this pipeline in the thesis:

> CodeDEE Team. (2026). *Systematic Synthetic Dataset Generation for Security Vulnerability Benchmarking*. Senior Project, Computer Engineering Department. Prompt templates available at `docs/06_Synthetic_Dataset_Prompt_Templates.md`.

**Datasets cited:**
1. Bhandari, G. et al. (2021). CVEfixes: Automated Collection of Vulnerabilities and Their Fixes from Open-Source Software. *MSR 2021*. https://doi.org/10.1145/3463274.3463340
2. Meta FAIR Security. (2024). CyberSecEval 2: A Wide-Ranging Cybersecurity Evaluation Suite for LLMs. *arXiv:2404.13161*.
3. OWASP. (2025). *OWASP Top 10 for LLM Applications 2025*. https://genai.owasp.org/
4. OWASP. (2021). *OWASP Top 10:2021*. https://owasp.org/Top10/
5. MITRE. (2024). *CWE Top 25 Most Dangerous Software Weaknesses*. https://cwe.mitre.org/top25/
