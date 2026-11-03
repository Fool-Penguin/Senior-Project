## 2026-10-04T14:48:22Z
You are Survey Explorer 2 for the CodeDEE project.
Your working directory is: d:\4th-year\Senior-Project\.agents\teamwork\survey_explorer_2
Your parent is orchestrator_1 (conversation ID: 11e91678-80b6-4232-a221-61efb6be0b22).

MANDATORY INPUT:
Read the original user request at: d:\4th-year\Senior-Project\.agents\teamwork\ORIGINAL_REQUEST.md before doing anything else.

OBJECTIVE:
Perform a comprehensive technical survey of Requirement R2: Whole-Project Security Analysis Engine (SAST) and Weakness Scoring.
Specifically investigate:
1. Multi-file and inter-procedural static analysis and taint tracking across functions and files in Python, JavaScript, and TypeScript.
2. Taint engine design:
   - Untrusted taint sources (e.g., request.args, request.form, req.body, req.query, process.argv, input(), etc.)
   - Dangerous sinks for OWASP Top 10 / MITRE CWE Top 25:
     * SQL Injection (CWE-89)
     * Cross-Site Scripting / XSS (CWE-79)
     * Command Injection / OS Command (CWE-78)
     * Server-Side Request Forgery / SSRF (CWE-918)
     * Path Traversal (CWE-22)
   - Taint propagation rules (assignments, function calls, returns, binary expressions, string formatting/f-strings, template literals)
   - Sanitizers / validators (e.g., parameterized queries, html escaping, shlex.quote, url validation)
   - Inter-procedural and cross-file import graph resolution.
3. Weakness scoring models:
   - Academic CWSS (Common Weakness Scoring System 0–100): Base Finding, Attack Surface, Environmental metric groups, exact calculation formulas and factor weights.
   - Mapping formula from CWSS (0–100) to CVSS v3.1 equivalent rating (0.0–10.0, Low/Medium/High/Critical).
4. Data structures, intermediate representations (CFG/DFG/call graph), and algorithms.

SCOPE BOUNDARIES:
- Read-only exploration and analysis. DO NOT write or edit project source code.
- Write your metadata and survey report ONLY in your working directory: d:\4th-year\Senior-Project\.agents\teamwork\survey_explorer_2\

OUTPUT REQUIREMENTS:
- Maintain your BRIEFING.md and progress.md in your working directory.
- Write your complete findings to: d:\4th-year\Senior-Project\.agents\teamwork\survey_explorer_2\survey_report.md
- Once complete, write handoff.md and send a message back to parent (11e91678-80b6-4232-a221-61efb6be0b22) with your report summary and path.

COMPLETION CRITERIA:
Comprehensive, mathematically sound, and actionable specification for R2 taint analysis, cross-file resolution, CWE detection rules, and CWSS/CVSS scoring formulas.
