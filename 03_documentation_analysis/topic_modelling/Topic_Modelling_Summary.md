# Topic Modelling Summary

**What this is:** a short summary of what the documentation in our 175 agentic-software repositories is about, based on the BERTopic model in `topic_modelling/`. Full method and evaluation details are in `Documentation_Collection_Summary.md` (section *Topic modeling*).

**Inputs used:** `topic_modelling/documentation_topics.csv` (one row per documentation file), `topic_modelling/documentation_topic_names.json` (topic names and descriptions) and `topic_modelling/bertopic_documentation_topics.py` (pipeline). Output produced on 13 September 2026; summary written on 14 September 2026.

## In one paragraph

We collected 96,231 documentation files from 163 repositories. After removing empty, non-English and non-documentation files, 54,380 English documents were modeled, and 42,571 of them (78%) were grouped into **40 topics** covering 162 repositories. The documentation is mostly about **building agents** (frameworks, model providers, memory, MCP, skills) and **what agents can do** (web search, browsers, chat channels, security, video). Software engineering practices such as **code review, releases, documentation and testing** have fewer files but appear in most repositories.

## 1. From raw files to topics

| Step | Files | Share of all files |
|---|---:|---:|
| All documentation files collected | 96,231 | 100% |
| Removed: non-English, or no prose after cleaning | 30,717 | 31.9% |
| Removed: excluded path or file type (vendored code, logs, fixtures, most `.txt`) | 10,976 | 11.4% |
| Removed: empty | 158 | 0.2% |
| **Modeled (English documentation)** | **54,380** | **56.5%** |
| Not close enough to any topic (`No clear topic`) | 11,809 | 12.3% |
| **Assigned to one of 40 topics** | **42,571** | **44.2%** |

Most of the non-English files are translated documentation sites. For example, crewAI keeps its docs in several languages and in many versions.

## 2. What the documentation is about

To make the 40 topics easier to read, we grouped them by hand into six themes. The grouping is our own interpretation and not part of the model.

| Theme | Topics | Files | Share of assigned files |
|---|---|---:|---:|
| **Agent building blocks** | Agent Frameworks & Runtimes; LLM Providers & Model APIs; Scheduling & Task Queues; Model Context Protocol (MCP); Agent Memory; Implementation Plans & Specs; Vector Stores & Embeddings; Agent Skills; Plugins & Extensions; Agent Personas & Roles | 15,017 | 35.3% |
| **Agent capabilities and application domains** | Web Search & Scraping Tools; Cybersecurity; Video Production & Animation; Messaging Channels & Chat Bots; Voice Agents & Speech; Browser Automation; Market & Geopolitical Data; Deep Research Agents; Email & Workspace Agents | 9,685 | 22.8% |
| **Building, deploying and operating** | Observability, Tracing & Telemetry; Authentication & Credentials; Docker & Kubernetes Deployment; Sandboxes & Isolated Execution; JavaScript/TypeScript Build Configuration; REST & OpenAPI APIs; Model Training & Distributed Inference; Building from Source & Native Builds; Microservices (go-micro) | 7,154 | 16.8% |
| **Software engineering practice** | Code Review; Release & Version Management; Testing; Documentation Writing; Evaluation, Benchmarks & Performance; Translation & i18n | 4,567 | 10.7% |
| **User interface and design** | Agent Chat UI & Agent-User Interaction; Design Systems & Typography; React & Frontend Components | 4,041 | 9.5% |
| **Mixed or single-repository** (exclude from comparisons) | Mixed: Runtime Internals; Repo-specific: agno Cookbook Test Logs; Repo-specific: agent-zero Module Docs | 2,107 | 4.9% |

### Top 10 topics by number of files

Together, these 10 topics hold 20,516 files, or 48.2% of all assigned files.

| Rank | Topic | Files | Share of assigned files | Repositories (of 162) | Largest repository (share of topic files) |
|---:|---|---:|---:|---:|---|
| 1 | Agent Frameworks & Runtimes | 4,459 | 10.5% | 132 | crewAI (43%) |
| 2 | LLM Providers & Model APIs | 2,481 | 5.8% | 110 | crewAI (16%) |
| 3 | Web Search & Scraping Tools | 2,418 | 5.7% | 65 | crewAI (87%) |
| 4 | Cybersecurity | 2,071 | 4.9% | 73 | Anthropic-Cybersecurity-Skills (75%) |
| 5 | Observability, Tracing & Telemetry | 1,687 | 4.0% | 93 | crewAI (44%) |
| 6 | Agent Chat UI & Agent-User Interaction | 1,625 | 3.8% | 71 | CopilotKit (72%) |
| 7 | Code Review | 1,525 | 3.6% | 129 | posthog (9%) |
| 8 | Design Systems & Typography | 1,492 | 3.5% | 58 | open-design (55%) |
| 9 | Scheduling & Task Queues | 1,413 | 3.3% | 88 | crewAI (22%) |
| 10 | Authentication & Credentials | 1,345 | 3.2% | 84 | Anthropic-Cybersecurity-Skills (12%) |

File counts include duplicate files and version copies. In four of these topics, more than half of the files come from a single repository: Web Search, Cybersecurity, Agent Chat UI and Design Systems. Their rank therefore reflects the size of that repository more than how common the subject is. Finding 2 ranks topics by the number of repositories instead.

## 3. Key findings

### Finding 1: Count repositories, not files

A few large repositories inflate file counts, so the number of repositories that mention a topic is the fairer measure of how common that topic is.

| Topic | Files | Repositories (of 162) | Why the two numbers differ |
|---|---:|---:|---|
| Web Search & Scraping Tools | 2,418 | 65 | 87% of files are crewAI tool pages repeated across doc versions |
| Cybersecurity | 2,071 | 73 | 75% of files come from one skills collection |
| Agent Chat UI & Agent-User Interaction | 1,625 | 71 | 72% of files are from CopilotKit |
| Code Review | 1,525 | **129** | Spread thinly across almost every repository |
| Release & Version Management | 818 | **117** | Same: small per repository, but nearly everywhere |

### Finding 2: The most widespread topics

These are the topics found in the most repositories. The last column counts only repositories with at least 3 files on the topic, which filters out passing mentions.

| Rank | Topic | Repositories with ≥1 file | Repositories with ≥3 files |
|---:|---|---:|---:|
| 1 | Agent Frameworks & Runtimes | 132 | 92 |
| 2 | Code Review | 129 | 81 |
| 3 | Release & Version Management | 117 | 48 |
| 4 | LLM Providers & Model APIs | 110 | 79 |
| 5 | Documentation Writing | 102 | 64 |
| 6 | Testing | 100 | 55 |
| 7 | Docker & Kubernetes Deployment | 95 | 62 |
| 8 | Observability, Tracing & Telemetry | 93 | 53 |
| 8 | Model Context Protocol (MCP) | 93 | 55 |
| 10 | Agent Memory | 91 | 63 |

Four of the top six are software engineering practices: code review, releases, documentation and testing. This is relevant to our research on software quality and maintenance, because it shows that most agentic repositories document how they review, test and ship code.

### Finding 3: Repositories cover many subjects

- A typical repository has files in **17 of the 40 topics** (median).
- The broadest repositories are `PostHog/posthog` (40 topics), `NousResearch/hermes-agent` (39) and `openclaw/openclaw` (38).
- The least common general topics are Email & Workspace Agents (36 repositories), Agent Personas & Roles (40) and Video Production & Animation (44).

### Finding 4: Files written for AI agents follow the same pattern

Many repositories contain files meant to be read by AI coding agents rather than people. Their topics show what these agents are asked to do:

| File kind | Files with a topic | Most common topics |
|---|---:|---|
| Agent skills (`SKILL.md`, `skills/`) | 7,535 | Cybersecurity (17%), Video Production (11%), Code Review (8%), Design Systems (7%) |
| Agent definitions and commands (`.claude/agents/`, `.opencode/command/`, ...) | 887 | **Code Review (27%)**, Agent Frameworks (16%), Implementation Plans (10%) |
| Agent instructions (`AGENTS.md`, `CLAUDE.md`, ...) | 1,018 | Plugins & Extensions (16%), Agent Frameworks (12%), JS/TS Build Configuration (7%), React (6%), Testing (6%) |

Code review is the most common job given to custom agents and commands. Skills are mostly about specific domains, such as security and video.

### Finding 5: About one in five modeled files has no clear topic

11,809 modeled files (22%) were not similar enough to any topic. Most are READMEs (1,893), tool or integration pages (1,757), general docs-site pages (1,714) and agent skills (1,552). They are usually short or about a narrow subject. Use the *Doc type* column to describe these files.

## 4. How reliable are the topics?

- **Stable across runs:** we refit the model with three different random seeds, and the results agreed well (adjusted Rand index 0.64–0.71, normalized mutual information 0.78–0.80). 35 of the 44 original topics reappeared in each other run.
- **Less stable topics:** Implementation Plans & Specs; Evaluation, Benchmarks & Performance; Deep Research Agents; REST & OpenAPI APIs. Treat their boundaries as less certain.
- **Borderline assignments:** a file joins its nearest topic when cosine similarity is at least 0.5. In a manual check of 20 files just above that cutoff (0.5–0.6), 14 fit their topic, 1 was borderline and 5 did not. About 44% of assigned unique texts fall in that band.
- **Manual review:** all 40 topics were named by hand. 37 describe one clear subject, 1 is mixed and 2 are specific to a single repository.

## 5. Limitations

- **English only.** 32% of all files were not modeled, mostly translations. Non-English documentation is not represented.
- **One topic per file.** Documents that cover several subjects are counted under only one topic.
- **Beginning of the document only.** Topics reflect each file's headings and first ~1,000 characters.
- **Path-based rules.** Filters and doc types come from file paths, so a small number of files are misclassified. For example, some heading-heavy English files fail the English check.
- **Tied to this model.** Topic ids and names apply only to this fit (seed 42, minimum topic size 100). Refitting requires reviewing the names again.

## 6. How to use the results

- To compare topics across repositories, count **repositories**, not files, and leave out the three mixed or single-repository topics (ids 20, 30, 40).
- Use the **Topic** column for what a file is about and the **Doc type** column for what kind of file it is (for example README, changelog or skill).
- To study documentation of software quality practices, start with Code Review (id 3), Testing (17), Release & Version Management (25) and Evaluation, Benchmarks & Performance (34).
