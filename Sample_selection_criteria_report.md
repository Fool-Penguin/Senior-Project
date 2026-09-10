# Senior Project Research Methodology Report: Sample Selection Criteria for Agentic Software Repositories

**Project Title:** Empirical Evaluation of Software Quality and Ecosystem Sustainability in Open-Source Agentic AI Systems  
**Date:** 9 September 2026  
**Final Dataset Artifact:** [`Repos_Final_Sample.csv`](175 Repositories)

---

## 1. Research Context & Objectives

This study investigates how emerging open-source agentic software repositories maintain their code quality, manage technical debt, and ensure sustainable development over time.

### Core Research Questions
* **Main Research Question (MRQ):** *How do open-source agentic software repositories maintain their software quality and manage ecosystem sustainability over time?*
* **RQ1 (Structural Complexity & Modularity):** *What is the structural complexity and modularity of the source code in agentic software repositories?*
* **RQ2 (Maintenance Efficiency):** *How efficient is the repository’s maintenance process in terms of issue resolution time and pull request integration?*
* **RQ3 (Issue Churn & Software Regression):** *What is the prevalence of issue churn (reopened issues) and how does it correlate with software regression?*

---

## 2. Theoretical & Architectural Definition of "Agentic Software"

To establish a defensible, peer-reviewable sample boundary, candidate repositories were evaluated against a formal two-tier definition: **Functional Scope** and **System Architecture**.

### 2.1 Functional Definition
> *"Agentic software refers to autonomous programs powered by Agentic AI that can plan, make decisions, and execute multi-step workflows to achieve specific goals with limited human supervision."*

### 2.2 The 5-Component Architectural Formula
Every included repository must manifest the five structural pillars of an agentic system:

$$\mathbf{\text{Agentic Software}} = \mathbf{\text{Agent (Reasoning)}} + \mathbf{\text{Tools (Action)}} + \mathbf{\text{Memory (State)}} + \mathbf{\text{Loop (Orchestration)}} + \mathbf{\text{Environment \& Guardrails}}$$

```
                                  ┌───────────────────────────┐
                                  │   Agent (Reasoning Core)  │
                                  │    - LLM / Cognitive Model│
                                  └─────────────┬─────────────┘
                                                │
                                                ▼
     ┌───────────────────────┐    ┌───────────────────────────┐    ┌───────────────────────┐
     │ Tools (Means of Acting)│ ◄──┤    Orchestration Loop     ├──► │ Memory (State Engine) │
     │  - Files, Bash, APIs  │    │ (Planning, Exec, Observe) │    │  - Session & Context  │
     └───────────────────────┘    └─────────────┬─────────────┘    └───────────────────────┘
                                                │
                                                ▼
                                  ┌───────────────────────────┐
                                  │   Environment & Guardrails│
                                  │   (CLI/IDE/OS + Risk Limits)
                                  └───────────────────────────┘
```

1. **Agent (Reasoning Core):** Driven by an LLM or neural decision engine that decomposes high-level goals into tactical execution steps.
2. **Tools (Means of Acting):** Capabilities allowing the agent to modify external state (editing code, running bash/terminal commands, browser automation, API integration, or compiling workflows).
3. **Memory (State Engine):** Stateful execution preserving context, session history, and execution state across multiple steps or sessions.
4. **Orchestration Loop:** An autonomous iterative control loop ($\text{Plan} \rightarrow \text{Execute Tool} \rightarrow \text{Observe Output} \rightarrow \text{Self-Correct}$).
5. **Environment & Guardrails:** Operating within a concrete host environment (CLI, IDE, OS, Web, or Messaging channel) with defined boundary constraints and execution limits.

---

## 3. Inclusion & Exclusion Criteria Matrix

To ensure that statistical calculations for **RQ1 (complexity)**, **RQ2 (PR speed)**, and **RQ3 (issue churn)** reflect true software development realities, three tiers of criteria were applied:

### Tier A: Product & Behavioral Criteria
* **Actionable Execution:** Must perform system actions or natural-language prompt-to-workflow compilation (e.g. `openclaw`, `opencode`, `n8n`, `Dify`).
* **Multi-Step Autonomy:** Excludes single-turn prompt-completion chatbots or static RAG lookup utilities that lack autonomous planning and iteration.
* **Flexible Interface:** Accepts CLI/TUI tools, IDE extensions, Desktop clients, and Messaging bots (Telegram, Slack, WhatsApp, Discord).
* **Domain Scope:** Embraces both general-purpose coding/task agents (`claude-code`, `OpenHands`) and domain-specialized agents (e.g., `nofx` for financial trading, `inbox-zero` for email management, `open-design` for UI design).

### Tier B: Repository Maturity & Activity Criteria (RQ Feasibility)
* **Star Threshold:** $\ge 100$ Stars (guarantees community adoption and real-world usage).
* **Maintenance Activity:** $\text{PRs} \ge 50$ **OR** $\text{Issues} \ge 50$ (ensures sufficient historical records to statistically calculate issue resolution duration in RQ2 and issue churn in RQ3).
* **Documentation & Governance:** Must contain at least one governance/guidance file (`CONTRIBUTING.md`, `SECURITY.md`, `AGENTS.md`, or `SKILL.md`).

### Tier C: Explicit Disqualification Rules
1. **Non-Software / Educational Repositories:** Excluded tutorials, courses, books, prompt collections, and curated lists (e.g., `microsoft/generative-ai-for-beginners`, `Prompt-Engineering-Guide`, `awesome-ai-agents`).
2. **Non-AI General Software:** Excluded traditional applications with zero agentic capabilities (e.g., `ansible`, `supabase`, `navidrome`, `firefly-iii`, `monica`).
3. **Pure Developer Code SDK Libraries:** Excluded low-level code frameworks that lack an interactive user-facing agent, studio, or CLI (e.g., `langchain`, `llama_index`, `haystack`, `crawlee`, `langgraph`).
4. **Static Skill / Instruction Packages:** Excluded markdown instruction sets that are loaded into agents rather than functioning as software programs themselves (e.g., `superpowers`, `skills`, `ui-ux-pro-max-skill`, `agent-skills`, `taste-skill`).

---

## 4. Dataset Provenance & Candidate Breakdown

The table below illustrates the exact qualification breakdown of all 273 unique candidate repositories evaluated from the master list ([`Repos_275.csv`](file:///d:/4th-year/Senior-Project/Repos_275.csv)):

### Initial Master Qualification Breakdown (221 Repositories Stage)

| Source Dataset | Total in Source | Qualified (`TRUE`) | Disqualified (`FALSE`) | Notes / Reasons |
| :--- | :---: | :---: | :---: | :--- |
| **From `Repos_66.csv` (Friend's Manual Review)** | **66** | **58 repos** | **8 repos** | 58 qualified. 8 were disqualified due to low PR/issue activity (< 50) or missing all guidance docs. |
| **From `Repos_69.csv` Only (Guidance Docs Match)** | **44** | **42 repos** | **2 repos** | 42 qualified (e.g., `n8n`, `dify`, `posthog`). 2 were disqualified (`generative-ai-for-beginners`, `generative-ai` as non-software tutorials). |
| **From Never-Filtered Set in `Repos_275.csv`** | **163** | **121 repos** | **42 repos** | 121 qualified (e.g., `autogen`, `MetaGPT`, `SuperAGI`, `letta`, `mastra`, `FastGPT`, `chatbox`). 42 disqualified (awesome lists, books, low activity). |
| **TOTAL UNIQUE CANDIDATES** | **273** | **221 repos** | **52 repos** | **Initial qualified candidate pool prior to strict software engine refinement** |

$$\text{Initial Qualified (221)} = \underbrace{58}_{\text{From Repos\_66}} + \underbrace{42}_{\text{From Repos\_69 only}} + \underbrace{121}_{\text{From Never-Filtered Set}}$$

---

## 5. Detailed Disqualification Audit & Reasons by Stream

To provide complete methodological traceability, this section documents the exact repositories disqualified from each dataset stream and the specific rationale for their exclusion:

### Stream 1: Disqualified Repositories from `Repos_66.csv` (8 Repositories)

| Repository Name | Stars | PRs | Issues | Disqualification Reason |
| :--- | :-: | :-: | :-: | :--- |
| **`ADeus`** | 3,426 | 69 | 39 | **Missing all guidance docs** (No `SECURITY.md`, `CONTRIBUTING.md`, `SKILL.md`, or `AGENTS.md`). |
| **`Auto-Deep-Research`** | 1,729 | 0 | 35 | **Low activity** ($\text{PRs}=0$, $\text{Issues}=35$, both $< 50$) AND missing all guidance docs. |
| **`BotsApp`** | 5,529 | 97 | 88 | **Missing all guidance docs** (Lacks any community governance/security files). |
| **`Data-Analysis-Agent`** | 2,441 | 5 | 9 | **Low activity** ($\text{PRs}=5$, $\text{Issues}=9$, both $< 50$). Insufficient event data for RQ2/RQ3. |
| **`career-ops`** | 68,447 | 2,021 | 1,126 | **Excluded as interview preparation guide** (Matched career/interview preparation topic tags). |
| **`deepbot`** | 2,272 | 1 | 3 | **Low activity** ($\text{PRs}=1$, $\text{Issues}=3$, both $< 50$) AND missing all guidance docs. |
| **`secure-openclaw`** | 1,188 | 5 | 2 | **Low activity** ($\text{PRs}=5$, $\text{Issues}=2$, both $< 50$) AND missing all guidance docs. |
| **`zclaw`** | 2,221 | 30 | 20 | **Low activity** ($\text{PRs}=30$, $\text{Issues}=20$, both $< 50$) AND missing all guidance docs. |

---

### Stream 2: Disqualified Repositories from `Repos_69.csv` Only (2 Repositories)

| Repository Name | Stars | PRs | Issues | Disqualification Reason |
| :--- | :-: | :-: | :-: | :--- |
| **`generative-ai-for-beginners`** | 118,556 | 886 | 244 | **Non-Software Tutorial / Educational Course:** Microsoft's 21-lesson curriculum repository consisting purely of markdown lessons and sample notebooks, not an executable software application. |
| **`generative-ai`** | 43,120 | 512 | 128 | **Non-Software Sample Repository:** Google Cloud Platform's collection of prompt guides, tutorial notebooks, and documentation rather than a standalone agentic codebase. |

---

### Stream 3: Disqualified Repositories from the Never-Filtered Set (163 Candidate Repositories)

The 163 never-filtered candidate repositories underwent systematic multi-stage filtering to eliminate non-software, passive tools, pure libraries, and static skills:

```
163 Candidates ──▶ [Activity & Educational Filter] ──▶ 120 Candidates
               ──▶ [Passive & Non-AI Software Filter] ──▶ 87 Candidates
               ──▶ [Pure Code SDK Filter (langchain, etc.)] ──▶ 82 Candidates
               ──▶ [Orchestration Graph Engine Filter (langgraph)] ──▶ 81 Candidates
               ──▶ [Static Skill Packages Filter (superpowers, etc.)] ──▶ 75 Qualified Repositories
```

#### 1. Disqualified by Activity & Educational Rules (43 Repositories)
* **Educational / Lists / Books / Cheatsheets:** `Prompt-Engineering-Guide`, `JavaGuide`, `awesome-ai-agents`, `LLMs-from-scratch`, `DeepLearning.ai-Summary`, `Front-End-Checklist`, `Self-Hosting-Guide`, `ai-agent-book`, `ai-engineering-hub`, `LLM-engineer-handbook`.
* **Low Activity ($\text{PRs} < 50$ AND $\text{Issues} < 50$):** `context-engineering-intro` ($\text{PRs}=28, \text{Issues}=22$), `openbrowser` ($\text{PRs}=33, \text{Issues}=0$), `GordenPPTSkill` ($\text{PRs}=0, \text{Issues}=10$), `J.A.R.V.I.S` ($\text{PRs}=29, \text{Issues}=23$), `marvin-template` ($\text{PRs}=27, \text{Issues}=4$), `OrbitOS` ($\text{PRs}=4, \text{Issues}=5$).

#### 2. Disqualified by Passive & Non-AI Software Filter (33 Repositories)
* **Traditional Non-AI Software (Zero Agentic Loops):** `supabase` (PostgreSQL backend), `maybe` (Personal finance app), `navidrome` (Music streaming server), `firefly-iii` (Financial manager), `monica` (CRM app), `actual` (Budgeting tool), `wtf` (Terminal dashboard), `academicpages.github.io` (Jekyll academic template).
* **LLM Telemetry & Evaluation (No Autonomous Action Loop):** `ragas` (RAG evaluation framework), `opik` (LLM observability platform), `openllmetry` (OpenTelemetry tracing for LLMs).
* **Passive Note-taking / Documentation Shells:** `blinko` (Notes tool), `foam` (Personal wiki), `Trilium` (Hierarchical note manager).

#### 3. Disqualified as Pure Code SDK Libraries (5 Repositories)
* **`langchain` & `langchainjs`:** Low-level programming library (`import { OpenAI } from "langchain"`). Lacks an interactive end-user agent, Studio, or CLI where users can prompt the system to generate workflows.
* **`llama_index`:** Low-level RAG data indexing library.
* **`haystack`:** Low-level NLP search pipeline library.
* **`crawlee`:** Low-level web scraping library.

#### 4. Disqualified as Orchestration Graph Engine (1 Repository)
* **`langgraph`:** Graph state orchestration engine for code integration rather than a prompt-driven autonomous agent application.

#### 5. Disqualified as Static Agent Skill Packages (6 Repositories)
* **`superpowers`** (277k stars): Methodology and markdown prompt instructions for coding agents.
* **`skills`** (236k stars): Engineering prompt skill files stored in `.agents/skills`.
* **`ui-ux-pro-max-skill`** (120k stars): UI/UX design prompt package.
* **`agent-skills`** (89k stars): Markdown best-practice instructions.
* **`taste-skill`** (80k stars): Frontend aesthetic prompt rules.
* **`Skill_Seekers`** (3.4k stars): Documentation-to-skill conversion script.

---

## 6. Final Dataset Synthesis (`Repos_Final_Sample.csv`)

Combining the qualified repositories from all three streams yields the final, pristine empirical research sample:

$$\mathbf{\text{Final Master Sample (175)}} = \underbrace{58}_{\text{Stream 1: Repos\_66 (Manual Review)}} + \underbrace{42}_{\text{Stream 2: Repos\_69 (Doc Match Only)}} + \underbrace{75}_{\text{Stream 3: Strict Agentic Software (Never-Filtered Set)}}$$

```
                       ┌───────────────────────────────────────────┐
                       │ Master Candidate Pool (Repos_275.csv: 274) │
                       └─────────────────────┬─────────────────────┘
                                             │
         ┌───────────────────────────────────┼───────────────────────────────────┐
         │                                   │                                   │
         ▼                                   ▼                                   ▼
┌──────────────────┐               ┌──────────────────┐                ┌──────────────────┐
│ Stream 1:        │               │ Stream 2:        │                │ Stream 3:        │
│ Repos_66.csv     │               │ Repos_69.csv     │                │ Explored Pool    │
│ (Manual Review)  │               │ (Doc-Match Only) │                │ (Strict Agentic) │
│ - 58 Qualified   │               │ - 42 Qualified   │                │ - 75 Qualified   │
│ - 8 Disqualified │               │ - 2 Disqualified │                │ - 88 Disqualified│
└────────┬─────────┘               └────────┬─────────┘                └────────┬─────────┘
         │                                  │                                   │
         └──────────────────────────────────┼───────────────────────────────────┘
                                            │
                                            ▼
                       ┌───────────────────────────────────────────┐
                       │ Final Research Sample (175 Repositories)  │
                       │ File: Repos_Final_Sample.csv              │
                       └───────────────────────────────────────────┘
```

---

## 7. Summary Statistics of the Final Sample (`Repos_Final_Sample.csv`)

| Metric | Minimum | Median | Mean | Maximum |
| :--- | :---: | :---: | :---: | :---: |
| **GitHub Stars** | 108 | 13,653 | 42,891 | 387,625 |
| **Pull Requests (PRs)** | 50 | 1,480 | 6,312 | 78,596 |
| **Issues** | 2 | 1,240 | 5,189 | 86,937 |
| **Repository Age (Days)** | 67 | 482 | 894 | 5,285 |

### Integrity Verification
* **Total Records:** Exactly **175 unique repositories**.
* **Deduplication:** 0 duplicate repository names.
* **Metadata Completeness:** Full commit history, contributor metrics, issue/PR activity, guidance file flags, and descriptions are attached to every row.

---

## 8. Next Steps for RQ Execution

With [`Repos_Final_Sample.csv`](file:///d:/4th-year/Senior-Project/Repos_Final_Sample.csv) established as the ground-truth empirical sample:
1. **RQ1 (Code Complexity & Modularity):** Clone codebases to compute Cyclomatic Complexity, Maintainability Index, and Coupling/Cohesion modularity metrics.
2. **RQ2 (Maintenance Efficiency):** Mine GitHub REST/GraphQL API to compute Mean Time to Resolution (MTTR) for closed issues and Mean Time to Merge (MTTM) for pull requests.
3. **RQ3 (Issue Churn & Regression):** Extract issue event logs to identify reopen events (`reopened`), cross-referencing commit histories for regression bug fixes.
