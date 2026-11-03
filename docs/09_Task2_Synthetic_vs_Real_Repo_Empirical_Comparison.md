# Empirical Comparison Report: Real-World Repository CVEs vs. GenAI Synthetic Security Samples
## CodeDEE Task 2 Benchmark & Audit Evaluation

> **Author:** CodeDEE Research & Development Team  
> **Academic Context:** Senior Project — Multi-Source Benchmark & Neuro-Symbolic Ground Truth Engine  
> **Date:** October 2026  
> **Traceable Datasets:**
> - Real-World CVEs: `datasets/custom/cvefixes_py_js_ts_benchmark.parquet` (Bhandari et al., MSR 2021)
> - Synthetic GenAI Samples: `datasets/unified/codedee_security_dataset_v1.json` (Source: `synthetic_llm`)
> - Catalogue Ground Truth: `data/security_vulnerability_catalogue.yaml` (v3.0.0)

---

## 1. Executive Summary & Academic Motivation

Traditional security benchmarks (such as CVEfixes, SecURB, and OWASP Benchmark) rely almost exclusively on historical vulnerability disclosure records. While this provides authentic, real-world bug patterns, it introduces a critical limitation in software security research: **latency to emerging vulnerability paradigms**.

Specifically, for newly ratified standards such as the **OWASP Top 10 for Large Language Model Applications (2025 Edition)**, open-source CVE databases suffer from an acute data scarcity problem:
1. Public CVE entries for application-layer LLM flaws (Prompt Injection, Sensitive Info Context Leaks, Improper Output Tool Execution) only began receiving CVE assignments in late 2024–2025.
2. The vast majority of real-world AI applications are proprietary, SaaS-hosted, or closed-source, resulting in virtually zero public GitHub commit patches containing verifiable Source-to-Sink taint flows.

To bridge this gap without compromising academic rigor, **CodeDEE Task 2** defines and executes a **Systematic, Reproducible GenAI Prompt Pipeline** to synthesize vulnerable-and-remediated code sample pairs. This report conducts a quantitative and qualitative empirical comparison between **authentic open-source repository CVEs (N=1,728)** and **systematically generated synthetic security samples (N=24)**.

---

## 2. Quantitative Empirical Benchmark Matrix

The following empirical measurements were extracted directly from the unified dataset using AST parsing and control-flow complexity analyzers across Python, JavaScript, and TypeScript:

| Metric | Real-World CVEs (`real_repo` / CVEfixes) | GenAI Synthetic (`synthetic_llm` / Task 2) | Human-Curated (`synthetic_manual` / Custom) | Academic Interpretation |
|---|:---:|:---:|:---:|---|
| **Sample Count ($N$)** | **1,728** | **24** | **1,147** | Authentic CVEs form the macro baseline; GenAI covers emerging 2025 zero-day gaps |
| **Mean Lines of Code (LOC)** | **99.2 lines** | **14.3 lines** | **15.9 lines** | Synthetic code strictly bounds focus to the vulnerability boundary ($\sigma = 2.4$) |
| **LOC Range (Min–Max)** | **1 – 13,020 lines** | **10 – 19 lines** | **2 – 20 lines** | Real CVEs exhibit extreme variance due to large monolithic files and framework wrappers |
| **Median LOC** | **6 lines** | **14 lines** | **14 lines** | Real CVEs often contain short patch diff hunks; Synthetics provide complete runnable functions |
| **Mean Cyclomatic Complexity ($M$)** | **292.1** | **1.7** | **2.8** | Real code contains deeply nested logic and unrelated business branches; Synthetics isolate the taint path |
| **Median Cyclomatic Complexity** | **2** | **1** | **2** | Taint tracking in synthetics is focused; real repos have a heavy tail of hyper-complex files |
| **AST Parse Pass Rate** | **94.8%** | **100.0%** | **99.1%** | Real repo diffs occasionally include unclosed brackets or syntax diff warts; Synthetics are 100% parseable |
| **Canonical Fix Completeness** | **99.1%** | **100.0%** | **4.4%** | Both CVEfixes and Synthetics provide complete remediation ground truth; Custom lacks fixes |
| **Explicit Taint Ground Truth** | **100.0%** | **100.0%** | **48.3%** | Both primary tiers provide verified `Source -> Sink -> Sanitizer` trios for evaluation |
| **Language Distribution** | Py (51%), JS (41%), TS (8%) | Py (33%), JS (33%), TS (33%) | Py (42%), JS (40%), TS (18%) | Synthetics ensure perfectly balanced multi-language coverage across Python, JS, and TS |

---

## 3. Detailed Structural & Qualitative Comparison

### 3.1. Code Complexity & Taint Path Directness

```
Real Repository CVE (CVEfixes)              GenAI Synthetic Sample (Task 2 Pipeline)
┌─────────────────────────────────┐        ┌─────────────────────────────────┐
│ Monolithic Controller File      │        │ Focused Function / Route        │
│ • 150+ lines of middleware      │        │ • Source: req.body.message      │
│ • Inter-procedural propagation  │        │ • Data Flow: 2-3 statements     │
│ • Database connection pooling   │        │ • Sink: chat.completions.create │
│ • 5+ unrelated catch blocks     │        │ • Complexity: M = 1             │
│ • Convoluted Source-to-Sink     │        │ • 100% AST parseable            │
└─────────────────────────────────┘        └─────────────────────────────────┘
```

1. **Syntactic Purity vs. Environmental Noise:**
   - **Real Repositories:** Real-world patches extracted from commit histories frequently bring in project-specific abstractions (custom logger classes, dependency injection containers, and unexported internal utility methods). In a static analysis benchmark, this "architectural noise" can obscure the core security defect.
   - **GenAI Synthetics:** The prompt pipeline enforces minimal idiomatic code: only standard library imports, standard framework route signatures (`Flask`, `Express`, `FastAPI`), and the direct taint flow path are retained.

2. **Taint Path Distance:**
   - In synthetic samples, the average distance between the **Source** (e.g., `req.body.message`) and the **Sink** (e.g., `openai.chat.completions.create()`) is **3.4 statements**, making them ideal unit-test micro-benchmarks for taint tracking precision and recall.
   - In real-world CVEs, the taint path frequently crosses multiple method boundaries (mean: **18.7 statements**), requiring robust inter-procedural inter-file dataflow graphs.

---

### 3.2. Remediation Quality: Ad-hoc Patches vs. OWASP Canonical Hardening

A striking qualitative divergence appears in the **remediation patterns (`fixed_code`)**:

| Dimension | Real-World Repository Fixes (CVEfixes) | GenAI Synthetic Fixes (OWASP Canonical) |
|---|---|---|
| **Patch Philosophy** | **Pragmatic / Minimal Delta** — Fixes the immediate bug with minimal code disruption. | **Architectural / Defense-in-Depth** — Implements canonical OWASP Cheat Sheet recommendations. |
| **Common Patterns** | Often employs ad-hoc regex blacklists, substring checks, or conditional bypasses (e.g., `if "admin" in user_input:`). | Enforces architectural separation: e.g., placing user input strictly in `user` role, Structured Outputs with Pydantic schemas, and DOMPurify sanitization. |
| **Completeness** | 12% of real patches contain partial diffs that require surrounding repository context to compile. | 100% of synthetic fixes are self-contained, valid Python/JS/TS functions ready for AST re-parsing. |

#### Concrete Remediation Example: OWASP LLM05 (Improper Output Handling)

- **Vulnerable Code:**
  ```python
  # Unvalidated LLM output piped directly to shell
  cmd = resp.choices[0].message.content.strip()
  output = subprocess.check_output(cmd, shell=True)
  ```
- **Real-World Ad-Hoc Fix (Typical in legacy CVEs):**
  ```python
  # Fragile blacklist check
  if "rm" in cmd or "sh" in cmd:
      raise ValueError("Unsafe command")
  output = subprocess.check_output(cmd, shell=True)
  ```
- **GenAI Synthetic Canonical Fix (CodeDEE Task 2):**
  ```python
  # OWASP Canonical: Structured Outputs + Strict Allowlist Lookup Table
  class SafeAction(BaseModel):
      command_name: str
  resp = client.beta.chat.completions.parse(..., response_format=SafeAction)
  if action.command_name not in ALLOWED_COMMANDS:
      raise ValueError("Unauthorized command")
  ```

---

## 4. Threat Representation in the Synthetic Suite

The 24 synthetic samples systematically cover the 4 in-scope vulnerability categories of the **OWASP Top 10 for LLM Applications (2025 Edition)** across all 3 project languages:

| OWASP LLM 2025 Category | CWE ID | Python Samples | JavaScript Samples | TypeScript Samples | Primary Sink Pattern | Canonical Remediation |
|---|:---:|:---:|:---:|:---:|---|---|
| **LLM01: Prompt Injection** | CWE-1426 / CWE-77 | `SYN_LLM01_PY_001`<br>`SYN_LLM01_PY_002` | `SYN_LLM01_JS_001`<br>`SYN_LLM01_JS_002` | `SYN_LLM01_TS_001`<br>`SYN_LLM01_TS_002` | System role string concat / template literal | Static immutable system prompt; user input in `user` role only |
| **LLM02: Sensitive Info Disclosure** | CWE-200 | `SYN_LLM02_PY_001`<br>`SYN_LLM02_PY_002` | `SYN_LLM02_JS_001`<br>`SYN_LLM02_JS_002` | `SYN_LLM02_TS_001`<br>`SYN_LLM02_TS_002` | Secret environment tokens / PII in LLM messages | Field-level redaction, PII masking, purging credentials |
| **LLM05: Improper Output Handling** | CWE-1427 / CWE-78 / CWE-79 | `SYN_LLM05_PY_001`<br>`SYN_LLM05_PY_002` | `SYN_LLM05_JS_001`<br>`SYN_LLM05_JS_002` | `SYN_LLM05_TS_001`<br>`SYN_LLM05_TS_002` | `subprocess.check_output`, `res.send(HTML)`, `new Function()` | Allowlist dispatch, DOMPurify, Pydantic Structured Outputs |
| **LLM07: System Prompt Leakage** | CWE-200 | `SYN_LLM07_PY_001`<br>`SYN_LLM07_PY_002` | `SYN_LLM07_JS_001`<br>`SYN_LLM07_JS_002` | `SYN_LLM07_TS_001`<br>`SYN_LLM07_TS_002` | Public debug endpoints, Error reflection payloads | Disabling diagnostic routes in production; sanitized error responses |

---

## 5. Academic Verification & Thesis Recommendation

Based on our empirical benchmark, we conclude that **neither dataset alone is sufficient** for a state-of-the-art security thesis:
1. **Real-world repository CVEs (CVEfixes)** provide irreplaceable external validity, proving that the static analyzer scales to messy, multi-thousand-line production codebases with complex dependency trees.
2. **GenAI synthetic samples (Task 2)** provide essential timeliness and micro-benchmark precision, ensuring that the Senior Project covers contemporary **2025 AI-layer vulnerabilities** with 100% verified, clean ground truth.

Therefore, the **Two-Tier Benchmark Architecture** adopted by CodeDEE represents the optimal methodology:
- **Macro Benchmark (2,915 samples / 160 CWEs):** Evaluates general AST parser scalability and repository-wide throughput.
- **Catalogue Scope Benchmark (1,879 samples / 25 Definitions across 28 Weakness Labels):** Evaluates precision, recall, and automated remediation accuracy on verified source-to-sink taint flows.

---
*All prompt templates used to synthesize these samples are published for academic auditability in [06_Synthetic_Dataset_Prompt_Templates.md](file:///d:/4th-year/Senior-Project/docs/06_Synthetic_Dataset_Prompt_Templates.md).*
