# Documentation Collection Summary

## Dataset at a glance

This summary describes `documentation_files.jsonl`, inspected on 12 September 2026. The collection uses one depth-1 Git clone at a time, scans the checked-out default branch recursively (excluding `.git`), and retains files matching `.adoc`, `.asciidoc`, `.markdown`, `.md`, `.mdx`, `.rst`, and `.txt`.

| Measure | Result |
|---|---:|
| Repositories in the input sample | 175 |
| Repositories represented by one or more records | 163 (93.1%) |
| Documentation-file records | 96,231 |
| JSONL file size | 1,021,305,352 bytes (about 974 MiB) |
| Extracted text | 873,735,740 characters across 19,522,120 lines |
| Invalid JSONL records | 0 |
| Duplicate repository/branch/path/SHA records | 0 |
| Empty-content records | 151 |

The JSONL contains the repository, source URL, checked-out branch, repository-relative path, commit SHA, and UTF-8-decoded content for every matched file. Each represented repository is recorded at one checked-out commit, so the data is a point-in-time snapshot rather than a history.

## File types and locations

Markdown is the dominant format, followed closely by MDX. No `.adoc` or `.asciidoc` files were recorded, despite both extensions being included in the collector configuration.

| Extension | Files | Share |
|---|---:|---:|
| `.md` | 50,150 | 52.11% |
| `.mdx` | 39,084 | 40.61% |
| `.txt` | 5,009 | 5.21% |
| `.rst` | 1,969 | 2.05% |
| `.markdown` | 19 | 0.02% |

### Findings by extension

The table below was measured on 13 September 2026. "Excluded path" and "English prose" use the filters of `topic_modelling/bertopic_documentation_topics.py` (preprocessing version 4):

- **Excluded path** covers vendored code (`third_party/`, `vendor/`, `node_modules/`), test fixtures and snapshots, agent run logs (`.omo/evidence/`), and non-English translation trees (`translations/`, `i18n/` or `locales/` followed by a non-`en` folder). It also covers every `.txt` file except `readme.txt`, `llms.txt` and `llms-full.txt`.
- **English prose** means the file is non-empty after removing code blocks and markup, and passes the English-language check.

| Extension | Files | Repositories | Extracted text | Median file size | Empty | Excluded path | Non-English or no prose | English prose |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `.md` | 50,150 | 163 | 466.70M chars (53.4%) | 4,068 chars | 88 | 5,473 (10.9%) | 9,292 (18.5%) | 35,297 (70.4%) |
| `.mdx` | 39,084 | 46 | 300.79M chars (34.4%) | 4,460 chars | 1 | 547 (1.4%) | 21,150 (54.1%) | 17,386 (44.5%) |
| `.txt` | 5,009 | 128 | 93.72M chars (10.7%) | 696 chars | 69 | 4,914 (98.1%) | 3 | 23 (0.5%) |
| `.rst` | 1,969 | 8 | 12.37M chars (1.4%) | 2,468 chars | 0 | 42 (2.1%) | 110 (5.6%) | 1,817 (92.3%) |
| `.markdown` | 19 | 1 | 0.16M chars (0.02%) | 979 chars | 0 | 0 | 0 | 19 (100%) |
| `.adoc` | 0 | 0 | none | none | none | none | none | none |
| `.asciidoc` | 0 | 0 | none | none | none | none | none | none |

Here "Empty" means empty or whitespace-only, which is why the total (158) is slightly higher than the 151 empty-content records counted in the overview.

#### `.md`: the broadest format, found in almost every repository

- **Coverage:** 163 of the 163 represented repositories.
- **Most common file names:** `README.md` (8,530), `SKILL.md` (5,601), `AGENTS.md` (1,007), `api-reference.md` (826), `CHANGELOG.md` (505) and `CLAUDE.md` (405).
  - The number of `SKILL.md`, `AGENTS.md` and `CLAUDE.md` files shows how common agent-facing instruction files are in these repositories.
- **Largest contributors:** `microsoft/ai-agents-for-beginners` (3,510), `mukul975/Anthropic-Cybersecurity-Skills` (2,587), `xbtlin/ai-berkshire` (2,560), `affaan-m/ECC` (2,527) and `nexu-io/open-design` (2,239).
- **Excluded paths (10.9%):**
  - non-English folders under the `translations/` tree of `microsoft/ai-agents-for-beginners` (3,379 files);
  - vendored `third_party/` code (705);
  - non-English `i18n/` folders (543);
  - agent run logs under `.omo/evidence/` (473);
  - test fixtures and `vendor/` folders (about 380).
- **Non-English (18.5%):** includes Chinese research reports (for example `xbtlin/ai-berkshire`) and localized READMEs outside translation folders.

#### `.mdx`: documentation-site pages, concentrated in a few repositories

- **Coverage:** 46 repositories.
- **Concentration:** `crewAIInc/crewAI` alone holds 27,875 of the 39,084 files (71.3%). The next largest are `langflow-ai/langflow` (1,391), `CopilotKit/CopilotKit` (1,073), `mastra-ai/mastra` (923) and `anomalyco/opencode` (627).
- **Location:** 34,881 files (89.2%) are under a top-level `docs/` folder. Common names are site pages such as `overview.mdx` (2,116), `index.mdx`, `introduction.mdx`, `quickstart.mdx`, `skills.mdx`, `tools.mdx`, `human-in-the-loop.mdx` and `memory.mdx`.
- **Non-English (54.1%):** the highest share of any extension. crewAI publishes its documentation site in several languages and keeps versioned snapshots, so many `.mdx` files are translations or copies of the same page. Version copies of a page are also modeled once by the topic pipeline.
- MDX pages contain JSX components (`<Card>`, `<Tabs>`), `import` statements and front matter, which the pipeline strips before modeling.

#### `.txt`: mostly technical artifacts rather than documentation

- **Coverage:** 128 repositories, but only 23 files (0.5%) are English documentation by the rules above.
- **Most common file names:** dependency lists (`requirements.txt`, 468), terminal animation frames (`frame_N.txt`, 360), build scripts (`CMakeLists.txt`, 353), docs-build markers (`.latest-doc-only-change.txt`, 101), database migration markers (`max_migration.txt`, 73), license texts (`LICENSE.txt`, 63), test logs (`red.txt`, `green.txt`) and .NET public API lists (`PublicAPI.*.txt`).
- **Sources:** `code-yeongyu/oh-my-openagent` (1,302, mostly `.omo/` agent run evidence), `TEN-framework/ten-framework` (573, largely `third_party/`), `openai/codex` (455) and `apache/airflow` (303).
- **Size:** the median file is small (696 characters), but the extension still accounts for 10.7% of all extracted text because of a few very large logs and datasets (up to 8.84M characters).
- **Exclusion from topic modeling:** only `readme.txt`, `llms.txt` and `llms-full.txt` are kept. The remaining files formed junk topics (CMake, logs) in earlier topic-model runs.

#### `.rst`: reStructuredText, almost entirely from Apache Airflow

- **Coverage:** 8 repositories, but `apache/airflow` contributes 1,750 of the 1,969 files (88.9%). The others are `mlflow/mlflow` (79), `camel-ai/camel` (59), `TEN-framework/ten-framework` (42, all under `third_party/`) and `microsoft/qlib` (35).
- **Location:** most files are under `providers/` (1,290), Airflow's per-integration documentation. Common names are `index.rst`, `README.rst`, `security.rst`, `changelog.rst`, `installing-providers-from-sources.rst`, `commits.rst`, and release-note fragments (`N.significant.rst`, `N.bugfix.rst`, `N.feature.rst`).
- **Boilerplate:** at least 1,365 distinct `.rst` texts begin with the Apache Software Foundation license header, which the pipeline removes before modeling.
- **English share:** the highest of any extension (92.3%).

#### `.markdown`: test data, not documentation

- All 19 files come from `khoj-ai/khoj` under `tests/`.
- They are sample personal notes used as test data (for example "birthday gift", "file taxes", "submit resignation letter"), not project documentation.
- They pass the English filter but are too few to affect topic modeling.

#### `.adoc` and `.asciidoc`: not used

No repository in the sample contains AsciiDoc files, although both extensions were included in the collector configuration.

The recursive scan found 95,117 files in nested directories (98.84%) and 1,114 at repository root (1.16%). The top-level `docs` directory alone contains 44,037 records. Path-based indicators show 51,258 files under a `docs`, `doc`, or `documentation` directory; 9,384 README files; 2,392 changelog or release files; 483 contributing files; and 403 license/notice files. These categories can overlap.

## Default branches captured

Most records came from `main` (83,732 files; 87.0%). Other observed branches were `master` (5,962), `dev` (3,840), `develop` (1,242), `canary` (833), `dev-v2` (335), `3.6.x` (138), `feat/server_team` (70), `development` (51), `v2` (14), and `5.x` (14). This confirms the collector used the repositories' configured checked-out default branches rather than assuming `main` or `master`.

## Distribution across repositories

The corpus is concentrated in a small number of large repositories: the ten repositories with the most matched files account for 50,693 records (52.68% of the dataset), while the ten largest by extracted text account for 469,431,576 characters (53.73%).

| Repository | Matched files | Extracted text |
|---|---:|---:|
| `crewAIInc/crewAI` | 27,983 | 211.35M characters |
| `microsoft/ai-agents-for-beginners` | 3,514 | 39.48M characters |
| `xbtlin/ai-berkshire` | 2,676 | 26.85M characters |
| `mukul975/Anthropic-Cybersecurity-Skills` | 2,587 | 13.65M characters |
| `affaan-m/ECC` | 2,557 | 13.66M characters |
| `code-yeongyu/oh-my-openagent` | 2,417 | 29.23M characters |
| `CopilotKit/CopilotKit` | 2,325 | 13.31M characters |
| `nexu-io/open-design` | 2,250 | 19.37M characters |
| `apache/airflow` | 2,246 | 10.03M characters |
| `openclaw/openclaw` | 2,138 | 27.27M characters |

## Repositories without output records

The following 12 input repositories have no records in `documentation_files.jsonl`:

- `CoplayDev/unity-mcp`
- `Significant-Gravitas/AutoGPT`
- `ToolJet/ToolJet`
- `alibaba/nacos`
- `alibaba/spring-ai-alibaba`
- `ansible/ansible`
- `bojieli/ai-agent-book`
- `google-gemini/gemini-cli`
- `jeecgboot/JeecgBoot`
- `langchain4j/langchain4j`
- `medusajs/medusa`
- `n8n-io/n8n`

No JSONL record can mean either that the repository had no files matching the selected extensions or that collection did not complete for that repository. The collector's terminal output is needed to distinguish those cases.

## Interpretation and data-quality notes

The corpus is a broad documentation-oriented collection, not a semantic documentation-only corpus. The `.txt` rule also captures technical artifacts such as `CMakeLists.txt`, test fixtures, generated chunks, evaluation logs, and phonemizer examples. Several individual files are very large, including a 10.10M-character evaluation result in `Skyvern-AI/skyvern`, an 8.84M-character phonemizer example in `leon-ai/leon`, and a 6.04M-character evaluation log in `assafelovic/gpt-researcher`.

Consequently, downstream analysis should either:

1. retain all records when broad repository text coverage is desired; or
2. exclude `.txt` files and optionally apply path/content rules to remove fixtures, logs, generated files, and release archives when building a documentation-focused corpus.

The recursive workflow successfully preserves nested documentation, skills, examples, package documentation, and localized content; filtering should therefore happen after collection rather than by limiting the clone scan to a small set of directories.

## Topic modeling

`topic_modelling/bertopic_documentation_topics.py` assigns each documentation file to one topic, discovered without predefined labels. It writes the result to `topic_modelling/documentation_topics.csv` and the fitted model to `topic_modelling/bertopic_documentation_model/`. All topic modelling files live in `topic_modelling/`.

The CSV has one row per JSONL record, with these columns:

- repository URL and name;
- file path and name;
- **doc type**: what kind of file it is, from its path;
- topic id, topic name, topic description, and topic keywords.

Rows without a topic have topic id −1. Their topic name gives the reason: `Not modeled: empty file`, `Not modeled: excluded path or file type`, `Not modeled: non-English or no prose`, or `No clear topic`.

The published output was produced on 13 September 2026 with:

```
python topic_modelling/bertopic_documentation_topics.py --merge-topics 26,41 --drop-topics 35,36,41 --topic-names topic_modelling/documentation_topic_names.json
```

### Method

1. **Filtering.** Records are excluded before modeling when they are empty or their path matches a non-documentation rule (see *Findings by extension*).
   - Each remaining file is cleaned by removing code blocks, HTML/JSX markup, links, tables, front-matter fields other than title, name, description and summary, and Apache license headers.
   - Files whose cleaned text fails a stdlib English-language heuristic are not modeled. The embedding model and keyword vectorizer are English-only.
   - Each repository's own owner and repository name are removed from its files. Otherwise product names such as "CopilotKit" pulled a repository's documents together regardless of subject.
2. **Modeling text.** A heading outline of the whole file (up to 500 characters) comes first, followed by the cleaned prose, cut to 4,000 characters. The embedding model reads roughly the first 1,000 characters, so the outline represents pages whose introduction is generic.
3. **Deduplication.** Version snapshots of the same page (for example `docs/v1.15.2/x.mdx` and `docs/x.mdx`) and exact duplicate texts are modeled once. Every copy receives the same topic.
4. **Embeddings.** Texts are embedded with `all-MiniLM-L6-v2` (384 dimensions, normalized).
5. **Fitting.** BERTopic is fitted on a balanced sample of texts:
   - capped at 300 per repository, 50 per folder, and 50 per file name across sibling folders (for example `skills/*/SKILL.md`);
   - so that large repositories and templated folders cannot form topics by volume alone.
6. **Model settings.**
   - UMAP: 30 neighbors, 5 components, minimum distance 0.05, cosine metric, random state 42.
   - HDBSCAN: minimum cluster size 100, minimum samples 5, `leaf` cluster selection.
   - Keywords: c-TF-IDF candidates re-ranked with `KeyBERTInspired` and `MaximalMarginalRelevance` (diversity 0.3).
7. **Assignment.**
   - The remaining texts are assigned with the fitted model's `transform`.
   - A text that HDBSCAN places in no cluster is reassigned to the nearest topic when cosine similarity to that topic's embedding is at least 0.5. Otherwise it gets `No clear topic`.
8. **Review.**
   - Two topics that did not separate reliably across random seeds (animation and video production) were merged.
   - Three topics described a kind of file rather than a subject: Contributing Guides, Changelogs & Release Notes, and Pull Request & Issue Templates. They were dropped in favor of the *Doc type* column, and their files were reassigned to the nearest remaining topic under the same 0.5 threshold.
   - The remaining 40 topics were named and described by hand in `topic_modelling/documentation_topic_names.json`, based on each topic's keywords, top repositories, and sample file paths.
9. **Doc type.** Every record, modeled or not, gets one of 33 doc types from ordered file-name and folder rules (see *Doc types*). Topics describe what a file is about; the doc type describes what kind of file it is. A changelog about build fixes is still a changelog.

### Corpus flow

| Stage | Files |
|---|---:|
| JSONL records | 96,231 |
| Not modeled: non-English, or no prose after cleaning | 30,717 |
| Not modeled: excluded path or file type | 10,976 |
| Not modeled: empty | 158 |
| English documentation modeled | 54,380 (42,402 unique texts + 11,978 duplicates and version copies) |
| Fit sample | 21,557 unique texts |
| **Assigned to one of 40 topics** | **42,571 (78% of modeled files; 44.2% of all records)** |
| No clear topic (modeled, not close enough to any topic) | 11,809 |

Assigned documents come from 162 repositories.

### Topics

File counts include duplicates and version copies. Repositories with many documentation versions, especially crewAI, therefore weigh more in file counts than in unique content.

Topic ids are the fitted model's ids. Gaps (35, 36, 41) are the dropped topics.

| Id | Topic | Files | Repositories | Largest repository (share) |
|---:|---|---:|---:|---|
| 1 | Agent Frameworks & Runtimes | 4,459 | 132 | crewAI (43%) |
| 0 | LLM Providers & Model APIs | 2,481 | 110 | crewAI (16%) |
| 29 | Web Search & Scraping Tools | 2,418 | 65 | crewAI (87%) |
| 13 | Cybersecurity | 2,071 | 73 | Anthropic-Cybersecurity-Skills (75%) |
| 7 | Observability, Tracing & Telemetry | 1,687 | 93 | crewAI (44%) |
| 26 | Agent Chat UI & Agent-User Interaction | 1,625 | 71 | CopilotKit (72%) |
| 3 | Code Review | 1,525 | 129 | posthog (9%) |
| 6 | Design Systems & Typography | 1,492 | 58 | open-design (55%) |
| 19 | Scheduling & Task Queues | 1,413 | 88 | crewAI (22%) |
| 4 | Authentication & Credentials | 1,345 | 84 | Anthropic-Cybersecurity-Skills (12%) |
| 5 | Model Context Protocol (MCP) | 1,246 | 93 | crewAI (22%) |
| 16 | Video Production & Animation | 1,226 | 44 | OpenMontage (39%) |
| 2 | Agent Memory | 1,203 | 91 | mem0 (16%) |
| 20 | Mixed: Runtime Internals | 1,200 | 86 | worldmonitor (10%) |
| 38 | Implementation Plans & Specs | 1,136 | 90 | crewAI (26%) |
| 21 | Vector Stores & Embeddings | 1,076 | 58 | crewAI (38%) |
| 12 | Messaging Channels & Chat Bots | 1,010 | 83 | openclaw (25%) |
| 14 | React & Frontend Components | 924 | 66 | OpenMontage (12%) |
| 15 | Docker & Kubernetes Deployment | 894 | 95 | crewAI (13%) |
| 9 | Voice Agents & Speech | 862 | 57 | ten-framework (14%) |
| 18 | Agent Skills | 841 | 90 | hermes-agent (22%) |
| 11 | Browser Automation | 819 | 73 | crewAI (29%) |
| 25 | Release & Version Management | 818 | 117 | airflow (16%) |
| 24 | Sandboxes & Isolated Execution | 790 | 73 | crewAI (22%) |
| 10 | JavaScript/TypeScript Build Configuration | 785 | 81 | nx (45%) |
| 17 | Testing | 784 | 100 | ECC (11%) |
| 23 | Plugins & Extensions | 777 | 79 | eliza (19%) |
| 42 | REST & OpenAPI APIs | 643 | 90 | langflow (11%) |
| 8 | Market & Geopolitical Data | 637 | 59 | worldmonitor (24%) |
| 37 | Documentation Writing | 606 | 102 | crewAI (13%) |
| 34 | Evaluation, Benchmarks & Performance | 601 | 79 | ruflo (19%) |
| 30 | Repo-specific: agno Cookbook Test Logs | 595 | 51 | agno (72%) |
| 27 | Model Training & Distributed Inference | 510 | 48 | ruflo (19%) |
| 22 | Agent Personas & Roles | 385 | 40 | agency-agents (59%) |
| 33 | Building from Source & Native Builds | 334 | 69 | oh-my-openagent (7%) |
| 31 | Deep Research Agents | 329 | 59 | gpt-researcher (13%) |
| 28 | Email & Workspace Agents | 313 | 36 | cli (30%) |
| 40 | Repo-specific: agent-zero Module Docs | 312 | 18 | agent-zero (87%) |
| 39 | Translation & i18n | 233 | 56 | crewAI (17%) |
| 32 | Microservices (go-micro) | 166 | 17 | go-micro (81%) |

Of the 40 topics:

- **37 describe one coherent subject.**
- **One is mixed** (20, Runtime Internals).
- **Two are specific to one repository** (30 agno test logs, 40 agent-zero module docs).

The mixed and repository-specific topics should be left out of cross-repository thematic comparisons.

The files of the three dropped topics (1,076 rows) moved as follows:

- 375 to `No clear topic`;
- 144 to Code Review (mostly contributing guides and pull request templates);
- 124 to Release & Version Management (mostly changelogs);
- the rest to Documentation Writing and other topics.

### Doc types

Doc types are assigned by ordered path rules; the first match wins.

1. **File-name conventions come first,** so a file keeps its conventional type wherever it sits. A `README.md` is a README even inside `examples/` or a translation folder. The conventions are `README`, `CHANGELOG`, `CONTRIBUTING`, `LICENSE`, `SKILL.md`, `AGENTS.md`/`CLAUDE.md`, `overview`/`introduction`, `quickstart`/`installation`, `plan.md`/`spec.md`, `TEST_LOG`, `api-reference`, and similar.
   - `index.md` is not treated as a convention, because documentation sites store each page as `<page>/index.mdx`.
2. **Otherwise, the folder decides:** non-documentation locations (vendored code, logs, fixtures, translations), agent folders (`skills/`, `.claude/agents/`, `prompts/`), and documentation-site sections (`tools/`, `guides/`, `concepts/`, `reference/`, ...).
3. **Otherwise, a fallback:**
   - *Docs site page (general)* when the file sits in a documentation folder (`docs/`, `website/`, `content/`, ...);
   - *Other (unclassified)* when it doesn't.
   - Together these two cover 18.6% of files.

| Doc type | All files | Files with a topic |
|---|---:|---:|
| Tool / integration page (in `tools/`, `integrations/`, `providers/`, `plugins/`, `channels/`, ...) | 15,761 | 6,261 |
| Docs site page (general) | 13,491 | 6,591 |
| Agent skill (`SKILL.md` or a file in a `skills/` folder) | 10,856 | 7,535 |
| README | 9,380 | 4,556 |
| Guide / how-to (in `guides/`, `learn/`, `how-to/`, `recipes/`, ...) | 6,839 | 2,242 |
| Reference (API, CLI, configuration) | 4,920 | 2,609 |
| Other (unclassified) | 4,406 | 2,255 |
| Concept / explanation (in `concepts/`, `architecture/`, ...) | 3,542 | 1,073 |
| Report / analysis (in `reports/`, `research/`, `evals/`, ...) | 2,628 | 180 |
| Overview / introduction page (`overview`, `introduction`, `intro`, `home`, `welcome`) | 2,575 | 818 |
| Translated page (non-English translation folder) | 2,502 | 0 |
| Changelog / release notes | 2,295 | 932 |
| Agent run log / test output | 2,098 | 467 |
| Getting started / installation | 1,532 | 732 |
| Agent instructions (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `copilot-instructions.md`) | 1,406 | 1,018 |
| Plan / spec / design record | 1,282 | 933 |
| Prompt / rule file (in `prompts/` or `rules/`) | 1,220 | 422 |
| Example / tutorial | 1,188 | 640 |
| Migration / upgrade guide | 1,144 | 380 |
| Agent definition / command (for example `.claude/agents/`, `.opencode/command/`) | 1,116 | 887 |
| Design system / style guide | 1,060 | 546 |
| Build / dependency file (`requirements*.txt`, `CMakeLists.txt`) | 853 | 0 |
| Test file / fixture | 823 | 134 |
| Vendored third-party file | 638 | 0 |
| Deployment / self-hosting | 628 | 383 |
| Snippet / partial | 482 | 231 |
| FAQ / troubleshooting | 363 | 149 |
| Contributing guide | 295 | 161 |
| Blog post / announcement | 270 | 211 |
| Issue / PR template | 242 | 135 |
| License / notice | 150 | 7 |
| Code of conduct | 142 | 3 |
| Security policy | 104 | 80 |

- Tool / integration pages are inflated by crewAI's `tools/` pages, which are repeated across documentation versions and languages.
- Because file names win, conventional files keep their type even in non-documentation locations. For example, the README count includes about 2,000 READMEs in translation, vendored, fixture or log folders, whose *Topic name* shows they were not modeled.

### Evaluation

- **Stability across random seeds.**
  - The full pipeline was fitted with seeds 42, 7 and 123 on the same embeddings.
  - Pairwise agreement on documents assigned in both runs: adjusted Rand index 0.64–0.71 and normalized mutual information 0.78–0.80.
  - 35 of the 44 pre-merge topics of the seed-42 run have a counterpart (Jaccard overlap ≥ 0.5) in the seed-7 run, and 35 in the seed-123 run.
  - Topics without a stable counterpart in both other seeds: animation (merged into video production), Implementation Plans & Specs, Evaluation, Benchmarks & Performance, Deep Research Agents, REST & OpenAPI APIs, and the dropped Pull Request & Issue Templates. Treat their boundaries as less certain.
- **Outlier-reassignment threshold.** Three manual spot checks compared possible cutoffs:
  - Of 20 documents assigned with similarity between 0.5 and 0.6, 14 fit, 1 was borderline and 5 did not.
  - Of 30 unassigned documents with similarity between 0.45 and 0.5, 11 fit their nearest topic, 1 was borderline and 18 did not.
  - Of 30 documents that a threshold of 0.4 would have added, 15 fit, 14 did not and 1 was unclear.
  - The threshold was kept at 0.5. About 44% of assigned unique texts fall in the 0.5–0.6 band, so assignments near the cutoff are looser than those of core cluster members.
- **Exclusion rules.** A manual check of sampled excluded files confirmed that they are not documentation, with about 19 likely false exclusions in the corpus (0.03% of modeled files):
  - 4 files under an `i18n/` folder not followed by a language code;
  - 11 README files inside fixture folders;
  - 4 vendored `SKILL.md` files.
- **Comparison with earlier models.**
  - The original model, tested on 5,000 records, formed topics around languages, markup and file artifacts.
  - An intermediate full-corpus run (minimum topic size 400) produced 28 topics: about 14 coherent, 9 mixed and 5 junk (including vendored code, agent logs and license headers). It left 21% of modeled texts unassigned.
  - The current model produces 40 reviewed topics, 37 of them coherent.

### Limitations

- **English filter.** The English check is a heuristic, not a language-identification model. A few translated pages that pass it are excluded only through translation-folder path rules.
- **Path rules.** Exclusion and doc-type rules are path-based and can miss or wrongly catch individual files.
  - Files in a `skills/` folder are typed as agent skills even when they are rendered documentation pages about skills.
  - Section-folder rules assume conventional names: a guide in a folder called `tools/` is typed as a tool page, and `migrat`/`upgrad` in a file or folder name marks a migration guide.
  - See *Evaluation* for exclusion errors.
- **Length.** Embeddings represent roughly the heading outline and first 1,000 characters of each file, not full long documents.
- **Subject over genre.** Topics group files by subject, not by kind of file. A file whose subject matches no topic well, such as a short changelog about package fixes, gets `No clear topic` even when its doc type is obvious.
- **One topic per file.** Each file receives exactly one topic, although many documents cover several subjects.
- **Repository dominance.** Several topics are dominated by one repository (share shown in the table). A topic's size is therefore not a measure of how common the subject is across repositories.
- **Keyword coherence.** NPMI coherence of the keyword lists is low (about −0.3) and not comparable with the first model. `KeyBERTInspired` keywords are meaningful phrases that rarely co-occur verbatim in the reference sample.
- **Reproducibility.** Topic ids, the merge (`26,41`), the dropped topics (`35,36,41`) and the names file belong to this exact fit (seed 42, minimum topic size 100). Refitting with other settings requires reviewing names again.
