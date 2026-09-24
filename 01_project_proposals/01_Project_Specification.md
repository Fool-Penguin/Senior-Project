# Master Project Specification: Dual-Lens Code Quality & Security Assistant (CodeLens AI)

**Project Title:** Dual-Lens Function-Level Code Quality & Security Assistant with Automated Refactoring and Guardrail Generation  
**Students:** Ongsa, Peem, Brook  
**Advisor:** Prof. Kookaip  
**Target Completion:** Senior Project 2026  

---

## Problem Statement & Research Motivation

Today, developers increasingly use AI coding assistants (like GitHub Copilot and Cursor) to write code faster, while modern apps connect directly to external APIs, databases, and AI agent execution loops. However, this creates two major problems: **code becomes messy and hard to understand (Cognitive Debt)**, and **security vulnerabilities slip into production unnoticed**.

### 1. The Code Quality Problem: Cognitive Debt & Delayed Feedback

* **AI-Generated Code Bloat:**  
  AI assistants help developers write code fast, but they often generate sprawling, deeply nested logic, bloated parameter lists, and monolithic "God functions". Because the code works, developers accept it without cleaning it up. Over time, this piles up **Cognitive Debt**—making the codebase exhausting for humans to read, understand, test, and maintain.

* **Delayed Feedback from CI Scanners (The "After-Push" Problem):**  
  Traditional quality analyzers (such as SonarQube) only run as slow, server-side CI/CD pipeline scans. Developers only get their quality score and feedback **after they commit and push their code**. By the time the feedback arrives minutes or hours later, developers have already moved on to other tasks and lost their mental focus, making refactoring slow, disruptive, and often skipped entirely.  
  * **How our tool solves this:** Our tool gives real-time feedback **right inside the IDE during the active coding phase**. Developers can see their function-level complexity and quality scores immediately as they write code—before ever pushing a commit.

* **Passive Linters with No Actionable Help:**  
  Existing in-editor tools (like SonarLint) are purely passive: they only draw warning squiggly lines on the screen, telling developers that a function is "too complex" but leaving them to figure out how to fix it on their own. Asking generic AI chatbots (like ChatGPT or Copilot Chat) to refactor often breaks code syntax, alters logic, or makes the code even more convoluted.  
  * **How our tool solves this:** Instead of just pointing out warnings, our tool actively helps developers fix the issue with **1-click verified refactoring**. The tool decomposes the function and **mathematically verifies that complexity actually decreased (ΔComplexity > 0)** before the developer accepts the changes.

### 2. The Security Problem: Vulnerabilities in Modern & AI-Connected Code

* **Emergence of Dangerous Attack Vectors:**  
  Modern applications frequently execute system commands, run dynamic database queries, and interface with external AI agent loops. This makes it easy for critical security vulnerabilities to slip in, especially from the **MITRE CWE Top 25** and **OWASP Top 10** (such as **CWE-78** Command Injection, **CWE-89** SQL Injection, **CWE-20** Missing Input Validation, and Prompt Injection in agent tools).

* **Cryptic Linters vs. Actionable Fixes:**  
  Traditional static security tools (like Bandit or ESLint Security) only output cryptic rule codes (such as `B602: subprocess call with shell=True`). They never explain the actual attack scenario or show developers how to fix the flaw safely.  
  * **How our tool solves this:** Our tool explains the exploit scenario in plain English, cross-references official **NIST NVD CVE precedents and CVSS v3.1 severity scores**, and generates **1-click defensive guardrail patches** (such as drop-in Pydantic validation schemas and safe parameterized execution sinks).

### 3. The Need for a Unified In-Editor Solution

Currently, developers are forced to juggle multiple disjointed tools: slow CI dashboards, passive local linters, and external security scanners.  
There is no single lightweight tool that works **interactively at the function level inside VS Code during the coding phase** to simultaneously keep code clean and prevent critical security vulnerabilities.

---

## 1. Executive Summary & Core Pillars

This project unites two complementary developer tools into a single, high-impact VS Code extension:
1. **Pillar 1 (ComplexityLens):** Function-Level Cognitive Debt & Complexity Guard (on-demand Cognitive Complexity, Cyclomatic Complexity, LOC, and automated refactoring with a guaranteed complexity drop).
2. **Pillar 2 (AgentShield):** Function-Level Security & Vulnerability Guard (detecting critical vulnerabilities mapped to **MITRE CWE Top 25**, **NIST NVD (CVE, CVSS v3.1, CPE)**, **OWASP Top 10 (2021)**, and **OWASP Top 10 for LLMs (2025)** with 1-click defensive guardrail patches).

```mermaid
flowchart TD
    subgraph Editor ["VS Code Active Editor (Python & TypeScript/JavaScript)"]
        F1["Function Definition (Active Cursor)"]
    end

    subgraph FastLocalEngine ["Fast Local Deterministic Engine (< 20ms, Zero API Cost)"]
        F1 -->|"Tree-sitter AST Walker"| Q1["Quality Lens: Cognitive Complexity, CC, LOC, LCOM"]
        F1 -->|"Semgrep OSS / Local Linters"| S1["Security Lens: CWE, NVD & OWASP Pattern Matching"]
    end

    subgraph InEditorDisplay ["Dual In-Editor UI (Native Hover + CodeLens & Sidebar)"]
        Q1 & S1 --> UI1["CodeLens Badge: '🟢 Quality: 6 | ⚠️ Security: 1 Issue (CWE-78 / CVE Linked)'"]
        Q1 & S1 --> UI2["Native Hover Tooltips & Lightbulb QuickFix"]
    end

    subgraph OnDemandLLM ["On-Demand LLM Generation Engine (Triggered on Click)"]
        UI1 & UI2 -->|"Click 'Apply Verified Refactor'"| LLM1["Intelligent Refactoring: Decomposes function & proves Delta-Complexity > 0"]
        UI1 & UI2 -->|"Click 'Explain Vulnerability'"| LLM2["Security Explainer: Plain-English attack scenario + NVD/CWE context"]
        UI1 & UI2 -->|"Click 'Inject Security Guardrail'"| LLM3["Defensive Guardrail Patch: Pydantic schemas, validation, safe sinks"]

```

Note: Dual In-Editor UI provides 2 complementary ways to present diagnostics (Native Hover/QuickFix vs. CodeLens & Webview Side Panel); we will evaluate both and select the ideal UX during testing.
### Confirmed Design Choices:
1. **Scope:** **Dual-Lens Assistant** combining Code Quality/Complexity (Cognitive Complexity, Cyclomatic Complexity, LOC) and Security Flaw Detection (MITRE CWE Top 25, NIST NVD CVEs, CVSS v3.1, OWASP Top 10, OWASP LLM) in a single unified VS Code extension.
2. **Target Languages:** **Python** and **TypeScript / JavaScript** using multi-language **Tree-sitter** AST parsers (covering > 75% of our 170 curated open-source repositories).
3. **Detection Engine:** **Hybrid Engine**—using local Semgrep OSS and Bandit/ESLint for rapid candidate security pattern matching, alongside Tree-sitter for sub-second complexity metrics.
4. **LLM Role (Zero API Waste):** Instant local static evaluation runs with zero latency and zero API cost. The LLM is invoked on-demand strictly for:
   - Synthesizing structural refactorings with mathematically proven ΔComplexity drops.
   - Explaining vulnerability attack vectors and generating drop-in security guardrails.
5. **Evaluation Strategy:** **Dual-Track Evaluation**:
   - *Track 1 (Standard Benchmarks):* **Juliet Test Suite v1.3** & **OWASP Benchmark v1.2** + **NIST NVD CVEFixes** (for CWE/CVE detection accuracy) and **CodeComplex / Qualitas Corpus** (for complexity metric accuracy).
   - *Track 2 (Real-World Commit-Level Evaluation):* Mining historical bug-fixing and refactoring commits across our **170 curated repositories** ([`Repos_Final_Sample.csv`](file:///d:/4th-year/Senior-Project/02_repo_sampling/data/Repos_Final_Sample.csv)) to measure human ΔComplexity vs. our tool's automated ΔComplexity reduction.
6. **UI/UX Strategy:** Support both **Native Hovers/QuickFixes** and **CodeLens + Rich Side Panel Webview**, allowing side-by-side testing during development.

---

## 2. Core Functional Pillars & Complete Metric Specifications

### Pillar 1: ComplexityLens (Quality, Cognitive Debt & Full Metrics Suite)

Every metric used by the quality engine is mathematically defined with clear interpretation thresholds:

| Metric Name | Mathematical Definition / Formula | Interpretation & Thresholds | Impact on Maintainability |
| :--- | :--- | :--- | :--- |
| **Cognitive Complexity** | Incremental scoring based on G. Ann Campbell's formal whitepaper:<br/>• `+1` for each break in linear flow (`if`, `ternary`, `switch`, `for`, `while`, `catch`, `goto`, `break`, `continue`)<br/>• `+1` for each nesting level of control structures<br/>• `+1` for logical operator sequences (`a && b && c`)<br/>• `+1` for recursion | • **≤ 8**: Healthy / Clean Code<br/>• **9 – 14**: Moderate Complexity<br/>• **≥ 15**: Critical (Refactoring Trigger) | Direct indicator of human mental comprehension effort. High scores lead to bugs and developer misunderstandings. |
| **McCabe Cyclomatic Complexity (CC)** | `CC = E - N + 2P`<br/>Where `E` = CFG edges, `N` = CFG nodes, `P` = connected components.<br/>Equivalently: `CC = 1 + Decision Points` | • **1 – 5**: Simple / High Testability<br/>• **6 – 10**: Moderate / Testable<br/>• **11 – 15**: High Complexity<br/>• **> 15**: Untestable / Complex | Measures the minimum number of independent test cases required for complete branch test coverage. |
| **Source Lines of Code (SLOC)** | Number of physical lines containing executable statements, excluding blank lines and pure comment lines. | • **≤ 30**: Ideal<br/>• **31 – 50**: Acceptable<br/>• **> 50**: Long Method smell<br/>• **> 100**: God Function | Strong correlation with defects and violation of Single Responsibility Principle. |
| **Maximum Nesting Depth** | Maximum hierarchical depth of nested AST statement blocks (`if` inside `for` inside `try`...). | • **≤ 2**: Healthy<br/>• **3**: Warning<br/>• **≥ 4**: Critical Nesting Smell | Deep nesting creates severe visual friction and cognitive overload. |
| **Parameter Count (Arity)** | Total number of formal parameters declared in the function signature. | • **≤ 3**: Optimal<br/>• **4**: Acceptable<br/>• **> 4**: Long Parameter List smell | High arity indicates excessive coupling; calls for Parameter Object refactoring. |
| **Lack of Cohesion in Methods (LCOM-4)** | Number of connected components in an undirected graph where nodes are functions and edges represent shared instance variables. | • **LCOM = 1**: Cohesive<br/>• **LCOM > 1**: Low Cohesion (Split recommended) | Identifies methods that operate on disparate data fields and should be split into modular units. |
| **Halstead Complexity Suite** | • Distinct Operators (`n1`), Distinct Operands (`n2`)<br/>• Total Operators (`N1`), Total Operands (`N2`)<br/>• Vocabulary: `n = n1 + n2`<br/>• Length: `N = N1 + N2`<br/>• Volume: `V = N * log2(n)`<br/>• Difficulty: `D = (n1 / 2) * (N2 / n2)`<br/>• Effort: `E = D * V` | • **High Volume** (`V > 1000`): Overly verbose logic.<br/>• **High Difficulty** (`D > 30`): Difficult to maintain. | Captures lexical size, operational difficulty, and cognitive mental effort required to implement the function. |
| **ΔComplexity Guarantee (Core Novelty)** | `ΔComplexity = Cognitive_before - Cognitive_after`<br/><br/>`%ΔComplexity = ((Cognitive_before - Cognitive_after) / Cognitive_before) * 100%` | • **ΔComplexity > 0**: Verified Complexity Reduction<br/>• **Target**: ≥ 40% reduction on complex functions (Cognitive ≥ 15) | **Guaranteed Refactoring Quality:** Mathematically proves that the AI refactoring reduced structural and mental friction. |al friction. |

---

### Pillar 2: AgentShield (Security, CWE, NVD & OWASP Complete Standards Suite)

AgentShield comprehensively integrates all major international vulnerability, weakness, and risk taxonomies:

#### A. MITRE CWE Top 25 Most Dangerous Software Weaknesses (Itemized)
The extension implements detection and remediation rules for every weakness in the official MITRE CWE Top 25 list:

* **CWE-78:** Improper Neutralization of Special Elements used in an OS Command ('OS Command Injection')
* **CWE-89:** Improper Neutralization of Special Elements used in an SQL Command ('SQL Injection')
* **CWE-79:** Improper Neutralization of Input During Web Page Generation ('Cross-Site Scripting' - XSS)
* **CWE-20:** Improper Input Validation
* **CWE-22:** Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal')
* **CWE-352:** Cross-Site Request Forgery (CSRF)
* **CWE-862:** Missing Authorization
* **CWE-200:** Exposure of Sensitive Information to an Unauthorized Actor
* **CWE-918:** Server-Side Request Forgery (SSRF)
* **CWE-502:** Deserialization of Untrusted Data
* **CWE-77:** Improper Neutralization of Special Elements used in a Command ('Command Injection')
* **CWE-94:** Improper Control of Generation of Code ('Code Injection')
* **CWE-434:** Unrestricted Upload of File with Dangerous Type
* **CWE-306:** Missing Authentication for Critical Function
* **CWE-287:** Improper Authentication
* **CWE-798:** Use of Hard-coded Credentials
* **CWE-863:** Incorrect Authorization
* **CWE-269:** Improper Privilege Management
* **CWE-319:** Cleartext Transmission of Sensitive Information
* **CWE-400:** Uncontrolled Resource Consumption
* **CWE-611:** Improper Restriction of XML External Entity Reference (XXE)
* **CWE-916:** Use of Password Hash With Insufficient Computational Effort
* **CWE-601:** URL Redirection to Untrusted Site ('Open Redirect')
* **CWE-1321:** Improperly Controlled Modification of Object Prototype Attributes ('Prototype Pollution')
* **CWE-676:** Use of Potentially Dangerous Function

#### B. NIST NVD (National Vulnerability Database) Data Suite
* **NVD Data Feeds:** Ingests official NIST NVD JSON 2.0 schema feeds (`services.nvd.nist.gov/rest/json/cves/2.0`).
* **CVE Identifiers (Common Vulnerabilities and Exposures):** Every detected weakness is cross-referenced with real-world CVE records (e.g. `CVE-2024-XXXXX`) to show developers documented exploit examples.
* **CVSS v3.1 Severity Scoring:**
  * **Base Score (0.0 – 10.0):**
    * **Critical:** 9.0 – 10.0
    * **High:** 7.0 – 8.9
    * **Medium:** 4.0 – 6.9
    * **Low:** 0.1 – 3.9
    * **None:** 0.0
  * **CVSS Vector String:** Computes Attack Vector (AV:N/A/L/P), Attack Complexity (AC:L/H), Privileges Required (PR:N/L/H), User Interaction (UI:N/R), Scope (S:U/C), Confidentiality (C:N/L/H), Integrity (I:N/L/H), Availability (A:N/L/H).
* **CPE (Common Platform Enumeration):** Uses CPE 2.3 formatted strings (`cpe:2.3:a:vendor:package:version:*:*:*:*:*:*:*`) to validate imported dependencies in `requirements.txt` or `package.json` against known vulnerable package versions.
* **NVD Advisory URLs:** Provides direct clickable links to official NIST advisory writeups (`https://nvd.nist.gov/vuln/detail/CVE-...`).
* **NIST NVD CVEFixes Dataset:** Ingests historical CVE-fixing commits to ground automated guardrail patch generation in real-world developer security patches.

#### C. OWASP Top 10 (2021) - Standard Software & Web Application Security
* **A01:2021 – Broken Access Control:** (Encompasses CWE-862, CWE-22, CWE-601)
* **A02:2021 – Cryptographic Failures:** (Encompasses CWE-327, CWE-319, CWE-798)
* **A03:2021 – Injection:** (Encompasses CWE-78, CWE-89, CWE-79, CWE-77, CWE-94)
* **A04:2021 – Insecure Design:** (Encompasses CWE-20, architectural logic flaws)
* **A05:2021 – Security Misconfiguration:** (Default credentials, verbose debug logging)
* **A06:2021 – Vulnerable and Outdated Components:** (CPE-matched packages)
* **A07:2021 – Identification and Authentication Failures:** (Encompasses CWE-306, CWE-287)
* **A08:2021 – Software and Data Integrity Failures:** (Encompasses CWE-502, unverified updates)
* **A09:2021 – Security Logging and Monitoring Failures:** (Missing audit trails on sensitive actions)
* **A10:2021 – Server-Side Request Forgery (SSRF):** (Encompasses CWE-918)

#### D. OWASP Top 10 for Large Language Model Applications (2025 - Agent & AI Applications)
* **LLM01:2025 – Prompt Injection:** Untrusted input dynamically alters system instructions or tool execution paths.
* **LLM02:2025 – Sensitive Information Disclosure:** Unintentional leakage of API keys, proprietary prompts, or memory states.
* **LLM03:2025 – Supply Chain Vulnerabilities:** Vulnerable third-party plugins, MCP servers, or unverified model weights.
* **LLM04:2025 – Data and Model Poisoning:** Tampered training data or poisoned context embeddings.
* **LLM05:2025 – Improper Output Handling:** Raw LLM outputs passed directly into execution sinks (`subprocess`, SQL, `eval`).
* **LLM06:2025 – Excessive Agency:** Autonomous tools performing destructive operations without human-in-the-loop authorization gates.
* **LLM07:2025 – System Prompt Leakage:** Exposing system instructions, hidden guardrails, or backend configuration schemas.
* **LLM08:2025 – Vector and Embedding Weaknesses:** Poisoned or unauthenticated vector database retrievals.
* **LLM09:2025 – Misinformation:** Hallucinated outputs accepted by backend services without schema verification.
* **LLM10:2025 – Unbounded Consumption:** Uncapped recursive tool calls or denial of wallet/compute loops.

---

## 3. Technical Methodology & System Pipeline

The system operates across a 5-phase deterministic and generative pipeline:

```mermaid
flowchart TD
    subgraph Phase1 ["Phase 1: Local AST & Rule Extraction (< 20ms)"]
        P1A["Active File Buffer (Python / TS)"] --> P1B["Tree-sitter Incremental AST Parser"]
        P1B --> P1C["Cognitive Complexity Walker (Campbell Spec)"]
        P1B --> P1D["McCabe CC Calculator (CFG Edges/Nodes)"]
        P1B --> P1E["Semgrep OSS Local Engine (CWE/OWASP Sink Scan)"]
    end

    subgraph Phase2 ["Phase 2: Security & Vulnerability Mapping"]
        P1E --> P2A["Match Flagged Sinks to MITRE CWE Top 25"]
        P2A --> P2B["Query NVD Knowledge Base (CVE ID + CVSS v3.1 Score)"]
        P2A --> P2C["Cross-reference Dependencies via CPE 2.3"]
        P2A --> P2D["Map to OWASP 2021 & OWASP LLM 2025"]
    end

    subgraph Phase3 ["Phase 3: Dual-Mode In-Editor Presentation"]
        P1C & P1D & P2A --> P3A["Render In-Editor Diagnostics (Squigglies & Gutter Icons)"]
        P1C & P1D & P2A --> P3B["Render CodeLens Line: '🟢 Quality: 4 | ⚠️ Security: CWE-78 (CVSS 9.8)'"]
        P3A --> P3C["Provide Lightbulb QuickFix Actions"]
        P3B --> P3D["Interactive Webview Side Panel (Full Telemetry & Charts)"]
    end

    subgraph Phase4 ["Phase 4: On-Demand LLM Generation Engine"]
        P3C & P3D -->|"Click 'Apply Verified Refactor'"| P4A["Extract AST Function Scope Window"]
        P4A --> P4B["LLM Structural Refactoring Prompt"]
        P4B --> P4C["Re-parse Candidate Diff with Tree-sitter"]
        P4C --> P4D{"Verify: Delta-Complexity > 0 and Syntax Valid?"}
        P4D -->|"Yes"| P4E["Display Side-by-Side Split Diff to Developer"]
        P4D -->|"No"| P4F["Discard / Self-Correct Candidate Patch"]
        
        P3C & P3D -->|"Click 'Inject Security Guardrail'"| P4G["LLM Vulnerability Explanation & Guardrail Generator"]
        P4G --> P4H["Inject Drop-in Defensive Schema (Pydantic / Parameterized Sink)"]
    end

    subgraph Phase5 ["Phase 5: Empirical Evaluation & Validation"]
        P5A["Benchmark Testing: Juliet v1.3 + OWASP Benchmark + CodeComplex"]
        P5B["Real-World Testing: Commit-Level Delta-Complexity on 170 Repos"]
    end

    Phase1 --> Phase2 --> Phase3
    Phase4 --> Phase5
```

<p align="center">
  <img src="LLM%20Security%20Vulnerability-2026-09-24-071106-1.png" alt="System Architecture Pipeline" width="850"/>
</p>

### Detailed Pipeline Mechanics:
1. **Local Deterministic Parsing (Phase 1):**  
   Tree-sitter performs incremental AST parsing directly inside the VS Code language client. An AST visitor walks the function node to evaluate G. Ann Campbell's Cognitive Complexity rules, McCabe Cyclomatic Complexity, nesting depth, and parameter counts in < 20ms. In parallel, Semgrep OSS runs localized pattern-matching rules on the active buffer to identify dangerous sink invocations.
2. **Standardized Security Mapping (Phase 2):**  
   Flagged sinks are enriched with MITRE CWE identifiers, NIST NVD CVE historical references, CVSS v3.1 base score vectors, and OWASP categories.
3. **Dual In-Editor Interface (Phase 3):**  
   Results are rendered simultaneously via native VS Code Diagnostics (squigglies/hovers) and a CodeLens header badge above the function. Clicking opens a rich Webview sidebar showing full telemetry and radar charts.
4. **On-Demand LLM Generation & Mathematical Verification (Phase 4):**  
   When the user triggers a refactor, the LLM generates a decomposed function diff. Before presenting the diff, the tool re-runs the Tree-sitter complexity calculator on the generated code to verify that ΔComplexity > 0 and executes local syntax checks. For security alerts, the LLM generates a drop-in defensive guardrail patch.
5. **Empirical Evaluation Pipeline (Phase 5):**  
   Validation across official synthetic benchmarks and real-world repository commit histories.

---

## 4. Formal Research Questions (RQs) for Thesis Defense

* **RQ1 (Complexity Reduction & Metric Fidelity):**  
  * *How accurately does our localized Tree-sitter AST parser compute Cognitive and Cyclomatic Complexity compared to server-side enterprise analyzers (SonarQube, Radon)?*  
  * *What magnitude of complexity reduction (**ΔComplexity**) is achieved by our automated refactoring recommendations on real-world high-complexity functions?*
* **RQ2 (Security Vulnerability Detection, NVD/CWE Mapping & Patch Safety):**  
  * *How accurately does AgentShield detect critical CWE/CVE vulnerabilities across standard security benchmark suites (Juliet Suite v1.3, OWASP Benchmark v1.2, NVD CVEFixes) compared to baseline linters (Bandit, ESLint Security)?*  
  * *What percentage of LLM-generated security guardrail patches successfully neutralize the targeted CWE without breaking functional unit tests?*
* **RQ3 (Real-World Commit-Level Evaluation across 170 Repositories):**  
  * *How does the complexity delta (**ΔComplexity**) achieved by our tool's automated refactorings compare to human maintainers' historical refactoring and bug-fixing commits across the 170 curated open-source repositories?*  
  * *Can our tool uncover real, unpatched CWE vulnerabilities in active open-source agentic repositories that traditional linters overlooked?*

---

## 5. Benchmark Datasets & Testing Pipeline

```mermaid
flowchart LR
    subgraph QualityBenchmarks ["Quality & Complexity Testing"]
        QB1["CodeComplex (9,800 Programs)"]
        QB2["Qualitas Corpus (Precomputed OO Metrics)"]
        QB3["170 Repos Commit History (Delta-Complexity Baseline)"]
    end

    subgraph SecurityBenchmarks ["Security, CWE & NVD Testing"]
        SB1["Juliet Test Suite v1.3 (NIST SARD: Good vs. Bad Functions)"]
        SB2["OWASP Benchmark v1.2 (2,740 Tests with Ground Truth)"]
        SB3["NIST NVD CVEFixes / PrimeVul (Real-World CVE/CWE Diffs)"]
    end

    QualityBenchmarks --> Engine["Dual-Lens Extension Testing"]
    SecurityBenchmarks --> Engine
    Engine --> Output["Publication-Grade Thesis Findings (Precision, Recall, Delta-Complexity)"]
```

1. **Juliet Suite v1.3, OWASP Benchmark & NVD CVEFixes Testing:**
   * Run baseline Bandit/ESLint on the benchmark test cases.
   * Run AgentShield on the same test cases.
   * Measure detection Recall and Precision across CWE-78, CWE-89, CWE-20, CWE-22, and CWE-862, cross-referencing against NVD CVE vulnerability records.
2. **Commit-Level ΔComplexity Testing:**
   * Sample historical refactoring and bug-fixing commits from [`dataset_5000_commits.csv`](file:///d:/4th-year/Senior-Project/04_commit_classification/data/dataset_5000_commits.csv) and [`Repos_Final_Sample.csv`](file:///d:/4th-year/Senior-Project/02_repo_sampling/data/Repos_Final_Sample.csv).
   * Compute human before-and-after complexity changes.
   * Run our tool on the pre-commit code and compare the tool's suggested refactoring against the human developer's actual commit.

---

## 6. Implementation Roadmap & Milestones

| Phase | Milestone Description | Key Technical Deliverables | Timeline |
| :---: | :--- | :--- | :---: |
| **Phase 1** | **Core AST & Rule Engines** | - Tree-sitter parsers for Python and TypeScript/JavaScript.<br/>- Local Cognitive Complexity & Cyclomatic Complexity calculators.<br/>- Semgrep OSS and Bandit/ESLint rule execution harness. | Weeks 1–3 |
| **Phase 2** | **NVD Knowledge Base & LLM Generation Layer** | - NIST NVD CVE/CVSS mapping database integration.<br/>- AST function context window extraction.<br/>- Automated refactoring prompt engine with ΔComplexity re-verification.<br/>- Security guardrail generator (schema validation, parameterization). | Weeks 4–6 |
| **Phase 3** | **Dual VS Code Interface** | - Mode 1: Native Hover providers and CodeAction QuickFixes.<br/>- Mode 2: CodeLens badges (`🟢 Quality | 🛡️ Security [CWE/NVD]`) + Rich Webview Sidebar.<br/>- Interactive split-diff preview for refactoring. | Weeks 7–9 |
| **Phase 4** | **Empirical Evaluation & Thesis Writing** | - Run Juliet, OWASP, and NVD CVEFixes benchmark evaluations (RQ1, RQ2).<br/>- Run commit-level ΔComplexity study across 170 repositories (RQ3).<br/>- Finalize senior project thesis defense presentation and report. | Weeks 10–12 |

---

## 7. TL;DR Summary: The Project at a Glance

```mermaid
flowchart TD
    subgraph CorePillars ["The Two Unified Pillars"]
        P1["Pillar 1: ComplexityLens<br/>Function-Level Cognitive Debt & Complexity Guard"]
        P2["Pillar 2: AgentShield<br/>Function-Level Security, CWE & NVD Guard"]
    end

    subgraph TheTech ["What We Use"]
        T1["Local Tree-sitter AST: Sub-second, zero-cost complexity computation"]
        T2["Semgrep OSS Rules: Fast pattern & sink matching"]
        T3["On-Demand LLM: Generates verified refactorings & security guardrails"]
    end

    subgraph TheMetrics ["Metrics & Standards"]
        M1["Complexity: Cognitive Complexity, Cyclomatic Complexity, LOC, LCOM, Delta-Complexity"]
        M2["Security: MITRE CWE Top 25 (1-25), NIST NVD (CVE & CVSS v3.1, CPE), OWASP Top 10 (A01-A10), OWASP LLM (LLM01-LLM10)"]
    end

    subgraph TheEvaluation ["Evaluation Datasets"]
        E1["Complexity: CodeComplex, ComplexCodeEval, Qualitas Corpus"]
        E2["Security: Juliet Test Suite v1.3, OWASP Benchmark v1.2, NIST NVD CVEFixes"]
        E3["Real-World: Commit-level Delta-Complexity on our 170 curated repos"]
    end

    CorePillars --> TheTech --> TheMetrics --> TheEvaluation
```

### Executive TL;DR Bullet Points:
* **The Product:** A single, lightweight VS Code extension giving developers instant function-level telemetry on **Code Quality (Cognitive Complexity)** and **Security (CWE / NVD Flaws)** while they code.
* **The Two Pillars:**
  1. **ComplexityLens:** Computes Cognitive Complexity, Cyclomatic Complexity, and LOC in < 20ms. If a function is too complex, the LLM refactors it and **mathematically proves that ΔComplexity > 0**.
  2. **AgentShield:** Detects security flaws mapped to **MITRE CWE Top 25 (CWE-1 through CWE-25)**, **NIST NVD (CVE & CVSS v3.1, CPE)**, **OWASP Top 10 (A01–A10)**, and **OWASP Top 10 for LLMs (LLM01–LLM10)**. The LLM explains the attack vector and **generates 1-click defensive guardrail patches**.
* **Why We Beat Competitors:**
  * **vs. SonarQube:** Runs on-demand at the function level inside the editor with zero server CI build delays.
  * **vs. SonarLint:** Actively synthesizes structural refactorings with a proven drop in Cognitive Complexity, rather than just showing passive squigglies.
  * **vs. Snyk / Bandit:** Detects modern AI/Agent application flaws (tool execution, prompt injection) and writes drop-in security guardrails directly into the function.
* **How the LLM Is Used:**  
  The LLM is invoked on-demand (zero background API waste) strictly to:
  1. Synthesize verified structural refactorings that reduce Cognitive Complexity.
  2. Explain vulnerability attack vectors and generate drop-in defensive guardrail code.
* **How We Test & Validate (Thesis Defense):**
  * **Complexity Accuracy:** Tested against **CodeComplex** and **Qualitas Corpus**.
  * **Security Accuracy:** Tested against **Juliet Test Suite v1.3**, **OWASP Benchmark v1.2**, and **NIST NVD CVEFixes**.
  * **Real-World Impact:** Evaluated on historical commits from our **170 curated open-source repositories** ([`Repos_Final_Sample.csv`](file:///d:/4th-year/Senior-Project/02_repo_sampling/data/Repos_Final_Sample.csv)) to measure human ΔComplexity vs. our tool's automated ΔComplexity reduction.
