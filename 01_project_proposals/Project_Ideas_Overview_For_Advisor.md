# Senior Project Direction Pivot: Project Ideas Overview & Advisor Discussion Guide

**Prepared for:** Meeting with Thesis Advisor (Prof. Kookaip)  
**Students:** Ongsa, Thanadon (Peem), Brook  
**Date:** September 2026  
**Context:** Pivoting from an empirical Git-commit classification study to an applied Software Engineering Tool project  

---

## 1. Background & Context of the Pivot

During our deep empirical re-analysis of 5,000 commits across 50 repositories ([`ai_commit_classification_validation_report.md`](file:///d:/4th-year/Senior-Project/ai_commit_classification_validation_report.md)), we discovered significant methodological limitations in attempting to classify AI vs. Pure Human code from Git history:
1. **Squash-and-Merge Information Loss:** Maintainers routinely squash commits or use merge queues, stripping AI trailers (`Co-authored-by: Claude`) from the Git commit log.
2. **Voluntary Self-Reporting Bias:** AI disclosure via PR checklists (`- [x] AI-generated`) or commit trailers is completely voluntary, leading to "silent AI" commits that silently contaminate the human control group.
3. **Bot Conflation:** Distinguishing between generative AI agents (Sweep, Devin) and deterministic DevOps bots (Dependabot, Renovate) requires complex heuristic pipelines that are vulnerable to committee skepticism.

As Prof. Kookaip advised:
> *"ลองคิดในมุมมองของการพัฒนา tool ดูมั้ยคะ ว่าสิ่งที่เรา explore ไปกันเนี่ย ถ้าเราจะทำ tool เพื่อช่วย developer ในการพัฒนาซอฟต์แวร์ได้ดีขึ้น หรือช่วย detect อะไรบางอย่าง จะพอเป็นไปได้ไหม"*

Pivoting to a **Software Engineering Tool Development** project transforms our thesis from an observational study burdened by classification validity threats into an **actionable, evaluable engineering thesis** with concrete metrics (Precision, Recall, Latency, False Positive Reduction, Usability).

---

## 2. Comparative Matrix of the 3 Proposed Ideas

We have formulated 3 distinct, high-impact project proposals based on our team discussions and literature review:

| Evaluation Dimension | [Proposal 1: IntelliTriage](file:///d:/4th-year/Senior-Project/Idea_1_Static_Analysis_LLM_Triage.md) | [Proposal 2: ComplexityLens](file:///d:/4th-year/Senior-Project/Idea_2_Function_Quality_Cognitive_Debt.md) | [Proposal 3: AgentShield](file:///d:/4th-year/Senior-Project/Idea_3_Agentic_Security_CWE_Detector.md) |
| :--- | :--- | :--- | :--- |
| **Core Concept** | **Static Analysis + LLM Triage** to eliminate false positives and provide 1-click fixes. | **On-Demand Function Complexity & Cognitive Debt Guard** with guaranteed delta-complexity drops. | **Function-Level CWE & Security Linter** for AI/Agent applications (tool calling, prompt injection). |
| **Primary Pain Point** | Developers ignore static linters due to high false-alarm rates (30–70%) and cryptic warnings (Alert Fatigue). | Developers using AI (Copilot/Cursor) write bloated, deeply-nested "God functions" (Cognitive Debt). | Modern apps connecting to LLMs/Agents have severe security blind spots that generic SAST tools miss. |
| **Academic Novelty** | **Very High** (Hot research topic in ICSE/FSE/MSR). | **Moderate to High** (Focuses on live cognitive metrics and mathematical refactoring proof). | **Extremely High** (Early, pioneering work in Agentic Software Security & CWEs). |
| **Direct Reuse of Past Assets** | Uses validation pipelines, AST parsers, and testbed of open-source repositories. | **Directly implements** all metrics from [`Data fields.txt`](file:///d:/4th-year/Senior-Project/Data%20fields.txt) (CC, Cognitive Complexity, LOC, LCOM). | **Directly scans** the 170 curated agentic repositories in [`Repos_Final_Sample.csv`](file:///d:/4th-year/Senior-Project/Repos_Final_Sample.csv). |
| **Evaluation Method** | Benchmark Suites (Juliet, OWASP Benchmark) + Developer User Study. | 1,000 Function Benchmark + Test Suite Verification + Developer Experiment. | Ground-Truth Vulnerability Benchmark + Empirical Mining of 170 Agent Repos. |
| **Implementation Risk** | **Low to Moderate** (Straightforward pipeline: Semgrep + Tree-sitter + LLM API). | **Low** (Local Tree-sitter AST parser + VS Code CodeLens). | **Moderate** (Requires writing customized Semgrep/Tree-sitter taint rules). |
| **Deliverable Artifacts** | VS Code Extension + Python Triage CLI + Benchmark Evaluation Report. | VS Code Extension + Complexity Analytics Engine + Usability Study. | VS Code Extension + CWE Rule Registry + Empirical Survey of 170 Repos. |

---

## 3. Detailed Summary of Each Proposal

### [Proposal 1: IntelliTriage — LLM-Augmented Static Analysis Triage](file:///d:/4th-year/Senior-Project/Idea_1_Static_Analysis_LLM_Triage.md)
* **What it does:** Wraps static analysis tools (e.g. Semgrep, ESLint, Bandit) inside VS Code. When warnings are triggered, an LLM analyzes the enclosing AST scope, verifies dataflow/sanitization, suppresses false positives, explains the real risk in plain English, and provides a verified one-click diff.
* **Why it shines:** It tackles one of the most widely recognized problems in software engineering (Alert Fatigue). It has clear, objective evaluation metrics (Precision, Recall, False Positive Reduction Rate).
* **Full Design Document:** [Idea_1_Static_Analysis_LLM_Triage.md](file:///d:/4th-year/Senior-Project/Idea_1_Static_Analysis_LLM_Triage.md)

### [Proposal 2: ComplexityLens — Function-Level Cognitive Debt & Complexity Guard](file:///d:/4th-year/Senior-Project/Idea_2_Function_Quality_Cognitive_Debt.md)
* **What it does:** Renders a real-time "Complexity Gauge" above each function inside VS Code (calculating Cognitive Complexity, Cyclomatic Complexity, LOC, and Smells via Tree-sitter in $<50\text{ ms}$). If a function becomes too complex, it offers an automated decomposition that mathematically guarantees a reduction in Cognitive Complexity ($\Delta \text{Complexity}$).
* **Why it shines:** It takes the complexity metrics we already planned in [`Data fields.txt`](file:///d:/4th-year/Senior-Project/Data%20fields.txt) and turns them into an interactive product that solves "AI code bloat."
* **Full Design Document:** [Idea_2_Function_Quality_Cognitive_Debt.md](file:///d:/4th-year/Senior-Project/Idea_2_Function_Quality_Cognitive_Debt.md)

### [Proposal 3: AgentShield — Function-Level CWE & Security Guard for Agentic Systems](file:///d:/4th-year/Senior-Project/Idea_3_Agentic_Security_CWE_Detector.md)
* **What it does:** A specialized security linter that detects AI/Agent-specific CWEs (e.g., CWE-78 command injection via agent tools, CWE-20 prompt injection, CWE-862 missing authorization in autonomous loops) and injects defensive guardrail wrappers.
* **Why it shines:** It builds directly on the 170 agentic repositories we already curated ([`Repos_Final_Sample.csv`](file:///d:/4th-year/Senior-Project/Repos_Final_Sample.csv)), allowing us to write a dual-contribution thesis: (1) The Tool, and (2) An Empirical Security Audit of 170 real-world AI agent systems.
* **Full Design Document:** [Idea_3_Agentic_Security_CWE_Detector.md](file:///d:/4th-year/Senior-Project/Idea_3_Agentic_Security_CWE_Detector.md)

---

## 4. Recommended Pitch & Meeting Strategy for Prof. Kookaip

### Meeting Structure (Suggested Agenda):
1. **Acknowledge the Classification Finding (2 mins):**
   - Briefly explain that after testing 5,000 commits, we found Git metadata has systematic blind spots (squash merges, voluntary checkboxes) that weaken the AI vs. Non-AI empirical boundary.
2. **Present the Pivot to Tool Development (3 mins):**
   - Follow her suggestion to build a developer tool. Show that none of our previous work was wasted because our AST metric definitions and repository datasets will directly serve as the tool's engine and evaluation benchmark.
3. **Pitch the 3 Proposals (10 mins):**
   - Present the 3 options using the comparison matrix above.
4. **Our Team Recommendation:**
   - **Top Pick:** **Proposal 1 (IntelliTriage)** or a **Hybrid of Proposal 1 & 2** (Static analysis triage that also inspects function cognitive complexity).
   - **Alternative High-Impact Pick:** **Proposal 3 (AgentShield)** if the professor prefers a strong security/AI-safety angle.

### Thai Discussion Script for Meeting:
> *"อาจารย์ครับ จากที่เราลงไปตรวจสอบ 5,000 commits อย่างละเอียด เราพบว่าการแบ่งกลุ่ม AI vs. Human ใน Git commit จริงๆ มีจุดอ่อนเชิงระเบียบวิธีวิจัยค่อนข้างเยอะ โดยเฉพาะเรื่อง Squash-and-merge ที่ลบ Git trailer ทิ้ง และการติ๊ก Checkbox ใน PR ที่ขึ้นอยู่กับความสมัครใจของ developer ทำให้เสี่ยงที่จะโดนกรรมการทักเรื่อง Control group contamination ได้*  
> 
> *ตามที่อาจารย์แนะนำให้ลองคิดในมุมการทำ Tool เราเลยตกผลึกไอเดียออกมา 3 ทิศทาง โดยดึงเอาความรู้เรื่อง Code Complexity Metrics และชุดข้อมูล 170 Repositories ที่เราทำไว้แล้ว มาต่อยอดเป็นแกนหลักครับ:*  
> 
> 1. **IntelliTriage:** แก้ปัญหา Alert Fatigue ของ Static Analysis โดยใช้ LLM มาช่วยกรอง False Positives ทิ้ง และเขียนอธิบายเป็นภาษาง่ายๆ พร้อมปุ่ม 1-Click Fix (มี Benchmark มาตรฐานวัด Precision/Recall ชัดเจน)  
> 2. **ComplexityLens:** เครื่องมือเช็ค Cognitive Complexity และ Code Smell ที่ระดับฟังก์ชันใน VS Code ทันทีขณะพิมพ์ เพื่อคุมหนี้ทางความคิดเวลาใช้ AI ช่วยเขียนโค้ด พร้อมฟีเจอร์คำนวณ $\Delta\text{Complexity}$ ว่าลดลงจริงหลัง Refactor  
> 3. **AgentShield:** เครื่องมือตรวจจับช่องโหว่ความปลอดภัย (CWE และ OWASP LLM) ในโค้ดที่ต่อกับ AI Agent (เช่น Tool execution หรือ Prompt injection) ซึ่งเราสามารถนำไปรันสแกน 170 Repositories ที่เรามีอยู่แล้วเพื่อทำเป็น Empirical Study ได้ทันที  
> 
> *ทางกลุ่มเรามองว่าไอเดียที่ 1 (IntelliTriage) หรือไอเดียที่ 3 (AgentShield) เป็นตัวเลือกที่น้ำหนักทางวิชาการแน่นที่สุดและวัดผลได้อย่างเป็นรูปธรรม อาจารย์มีความเห็นอย่างไรกับ 3 ทิศทางนี้บ้างครับ?"*

---

## 5. Next Action Items Upon Advisor Decision

1. **If Proposal 1 is selected:**
   - Set up VS Code Extension scaffolding (`yo code`).
   - Integrate Semgrep OSS CLI output into a Python triage backend.
   - Run baseline scan on OWASP Benchmark to establish initial false positive rates.
2. **If Proposal 2 is selected:**
   - Implement Tree-sitter Cognitive Complexity visitor in TypeScript/Python.
   - Build in-editor CodeLens provider rendering complexity badges over functions.
3. **If Proposal 3 is selected:**
   - Define custom Semgrep YAML rules for AI tool calling and dangerous sinks (`eval`, `exec`, `subprocess`).
   - Run initial scan across the 170 repositories in `Repos_Final_Sample.csv` to gather preliminary vulnerability statistics.
