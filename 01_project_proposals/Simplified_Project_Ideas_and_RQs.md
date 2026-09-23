# Simplified Project Ideas & Research Questions (RQs)

---

## Idea 1: Function-Level Code Quality & Refactoring Assistant (ComplexityLens)

### 💡 The Idea
A VS Code extension that allows developers to check the quality of **individual functions on demand** while writing code, rather than waiting for a slow, full-project scan like SonarQube.
* Shows instant metrics above each function (Cyclomatic Complexity, Cognitive Complexity, nesting depth, and code smells).
* If a function is too complex, it suggests a clean refactoring (e.g., splitting into smaller functions, using guard clauses) and shows how much the complexity will drop.

### 🎯 Research Questions (RQs)
* **RQ1 (Measurement Accuracy & Speed):** How accurately and quickly can real-time AST parsing calculate function-level complexity compared to full-project analyzers like SonarQube?
* **RQ2 (Complexity Reduction):** How much do the automated refactoring suggestions reduce a function's Cognitive and Cyclomatic Complexity?
* **RQ3 (Developer Impact):** Does seeing real-time complexity scores per function encourage developers to refactor messy code more frequently?

---

## Idea 2: Function-Level Security & CWE Detector (AgentShield)

### 💡 The Idea
A lightweight VS Code extension that scans individual functions for **security vulnerabilities (CWEs)**, especially in modern code that connects to APIs, LLMs, or executes external tools (e.g., command injection, prompt injection, or unsafe inputs).
* Focuses on function boundaries and parameter validation.
* Rather than just alerting, it offers an instant one-click patch with defensive guardrails (input validation and sanitization).

### 🎯 Research Questions (RQs)
* **RQ1 (Detection Accuracy):** How accurately can the tool detect function-level CWE vulnerabilities compared to standard security linters (e.g., Bandit, Semgrep)?
* **RQ2 (Real-World Prevalence):** How common are these function-level security vulnerabilities across real-world open-source repositories?
* **RQ3 (Patch Safety & Effectiveness):** Do the automated security guardrails successfully block exploits without breaking existing software behavior?

---

## Idea 3: Static Analysis + LLM to Eliminate False Positives

### 💡 The Idea
A tool that solves **Alert Fatigue** in static code analyzers. Traditional tools (like SonarQube, Semgrep, or ESLint) produce too many false alarms (30%–70% false positives) and confusing error messages, so developers tend to ignore them.
* Runs the static analyzer in the background.
* Uses an LLM to verify whether the alert is a true issue or a false alarm based on surrounding code context.
* Explains verified issues in plain English and provides a one-click automated fix.

### 🎯 Research Questions (RQs)
* **RQ1 (False Positive Reduction):** To what extent does the LLM filter reduce false positive warnings compared to raw static analysis tools?
* **RQ2 (Fix Correctness):** What percentage of the LLM-generated fixes resolve the warning while keeping the code compilable and passing tests?
* **RQ3 (Developer Productivity):** Does filtering false alarms and improving warning explanations help developers resolve code warnings faster?
* **RQ4 (False Positive Classification):** How effectively can LLMs classify false-positive static-analysis warnings, and which types of static-analysis warnings are most amenable to LLM-based filtering
