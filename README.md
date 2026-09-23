# Senior Project: Empirical Analysis of AI-Assisted and Autonomous Agent Software Engineering

This repository contains the complete empirical research pipeline, benchmark datasets, evaluation scripts, and advisor reports for our Senior Project studying **AI-assisted and autonomous agent development in agentic software systems**.

---

## 📁 Repository Structure & Organization

The codebase is organized into four sequential research stages following the thesis methodology, plus shared utilities:

```text
Senior-Project/
├── .env                                       # Local environment configuration & GitHub token
├── .gitignore                                 # Git ignore patterns (bytecode, large raw JSONL)
├── .gitattributes                             # Git repository attributes
├── README.md                                  # Repository overview and directory guide
│
├── 01_project_proposals/                      # Strategic Direction, Proposals & RQs
│   ├── Project_Ideas_Overview_For_Advisor.md  # Pivot analysis & comparative evaluation of 3 project ideas
│   └── Simplified_Project_Ideas_and_RQs.md    # Streamlined research questions & hypotheses
│
├── 02_repo_sampling/                          # Stage 1: Repository Corpus Mining & Selection
│   ├── scripts/
│   │   ├── collect_repos.py                   # GitHub Search API miner with 15 agentic keywords
│   │   ├── export_repo_metadata.py            # Git tree inspector for Markdown & guidance files
│   │   └── generate_manual_review.py          # Enriches candidate repos with GitHub topic tags
│   ├── notebooks/
│   │   └── filter_repos_by_docs.ipynb         # Filtering candidates by documentation & guidance rules
│   ├── data/
│   │   ├── Repos_275.csv                      # Raw keyword search candidate pool (275 repositories)
│   │   ├── Repos_66.csv                       # Intermediate filtered candidate subset (66 repositories)
│   │   ├── Repos_69.csv                       # Candidate repositories with required guidance files (69)
│   │   ├── Repos_Final_Sample.csv             # Final master benchmark sample (175 repositories)
│   │   ├── manual_review.csv                  # Manual qualification decisions dataset
│   │   ├── repo_search_results.json           # Cached raw search API responses
│   │   ├── repo_metadata_cache.json           # Cached Git tree file counts
│   │   └── manual_review_cache.json           # Cached repository topic queries
│   └── reports/
│       └── Sample_selection_criteria_report.md # Comprehensive sample selection methodology & audit
│
├── 03_documentation_analysis/                 # Stage 2: Documentation Extraction & Topic Modeling
│   ├── scripts/
│   │   └── pull_documentation_files.py        # Shallow clone harvester for documentation files (.md, .rst, etc.)
│   ├── notebooks/
│   │   └── summarize_documentation_findings.ipynb # Analysis of 96,231 harvested documentation files
│   ├── data/
│   │   └── documentation_files.zip            # Compressed archive of harvested documentation JSONL
│   ├── reports/
│   │   └── Documentation_Collection_Summary.md # Summary report on doc types, branch distributions & quality
│   └── topic_modelling/                       # BERTopic modeling subpackage
│       ├── bertopic_documentation_topics.py   # BERTopic model pipeline with embedding reuse
│       ├── test_bertopic_documentation_topics.py # Unit tests for text cleaning and topic assignment
│       ├── Topic_Modelling_Summary.md         # Summary of 40 discovered documentation topics
│       ├── documentation_topic_names.json     # Semantic topic labels
│       ├── documentation_topics.csv           # Final topic assignments
│       └── bertopic_documentation_model/      # Serialized BERTopic model weights & embeddings
│
├── 04_commit_classification/                  # Stage 3: Multi-Modal Commit Pipeline & 5,000 Dataset
│   ├── scripts/
│   │   ├── build_5000_commit_dataset.py       # Primary multi-modal 5,000 commits builder (50 repos)
│   │   ├── validate_commit_criteria.py        # Baseline 4 Git criteria validator
│   │   ├── validate_multimodal_criteria.py    # Multi-modal criteria comparative evaluator
│   │   ├── deep_multimodal_analysis.py        # Refined taxonomy analysis runner
│   │   ├── enhanced_multimodal_reanalysis.py  # Enhanced taxonomy v2 runner
│   │   └── strict_scientific_reanalysis.py    # Strict scientific taxonomy v3 runner
│   ├── data/
│   │   ├── dataset_5000_commits.csv           # Master 5,000 commits dataset (30 features)
│   │   ├── dataset_5000_commits.json          # Master 5,000 commits JSON with metadata & breakdown
│   │   ├── multi_repo_commit_validation.json  # Multi-repo validation results
│   │   ├── multimodal_commit_comparison.json  # Comparative criteria results
│   │   ├── refined_taxonomy_analysis.json     # Refined taxonomy analysis output
│   │   ├── enhanced_taxonomy_v2.json          # Enhanced taxonomy v2 output
│   │   └── scientific_taxonomy_v3.json        # Strict scientific taxonomy v3 output
│   └── reports/
│       ├── DATASET_5000_COMMITS_README.md     # Full dataset schema, column definitions & statistics
│       ├── Data fields.txt                    # Raw field definitions
│       ├── New_Criteria_And_Statistics_Summary.md # Executive summary of multi-modal criteria & stats
│       ├── Comparative_Criteria_Report_For_Advisor.md # Baseline vs Multi-Modal comparative report
│       └── ai_commit_classification_validation_report.md # Formal classifier validation report
│
└── utils/                                     # Shared Diagnostics & Helper Tools
    ├── check_pr.py                            # PR inspection tool for debugging API payloads
    └── check_rl.py                            # GitHub API rate limit checker
```

---

## 🔬 Research Stage Overview

### Stage 1: Repository Corpus Selection (`02_repo_sampling/`)
- Curated a benchmark sample of **175 production-grade agentic software repositories** from an initial candidate pool of 275 repositories.
- Applied systematic multi-tier filtering rules (functional domain, maintenance status, guidance files: `SECURITY.md`, `CONTRIBUTING.md`, `SKILL.md`, `AGENTS.md`).
- Documented complete exclusion and inclusion audits in `Sample_selection_criteria_report.md`.

### Stage 2: Documentation Extraction & Topic Modeling (`03_documentation_analysis/`)
- Harvested **96,231 documentation records** across the selected repositories.
- Applied BERTopic modeling (`all-MiniLM-L6-v2`) with custom preprocessing and deduplication.
- Identified 40 fine-grained documentation topics and 15 functional document types (architecture, skills, ADRs, instructions).

### Stage 3: Multi-Modal Commit Classification (`04_commit_classification/`)
- Constructed a gold-standard benchmark of **5,000 commits** across 50 representative agentic repositories (100 commits/repo).
- Developed a **multi-modal disambiguation pipeline** that overcomes the limitations of traditional Git-only heuristics (which miss up to 88% of AI contributions due to squash-merge trailer erasure and checkbox disclosures).
- Implemented a 4-tier taxonomy isolating deterministic DevOps bots (Dependabot, Renovate) from autonomous AI agents (Sweep, Devin) and interactive AI pair assistants (Claude Code, Cursor, Copilot).

| Category | Commits | Distribution | Primary Attribution Signals |
|---|---|---|---|
| **`PURE_HUMAN`** | 3,923 | 78.46% | Default human developer commits with zero AI/bot signatures |
| **`DETERMINISTIC_DEVOPS_BOT`** | 868 | 17.36% | Dependabot, Renovate, GitHub Actions automated maintenance |
| **`INTERACTIVE_AI_COAUTHORED`** | 129 | 2.58% | Claude Code, Cursor, Copilot trailers, PR checklists & labels |
| **`AUTONOMOUS_AI_AGENT`** | 80 | 1.60% | Sweep AI, Devin autonomous actors, branch prefixes, generator footers |
| **Total** | **5,000** | **100.00%** | **50 Repositories** |

---

## 🚀 Quickstart & Reproduction

### Prerequisites
- Python 3.10+
- Set your GitHub Token in `.env` at the root directory:
  ```env
  GITHUB_TOKEN=ghp_your_personal_access_token_here
  ```

### Check GitHub API Rate Limit
```powershell
python utils/check_rl.py
```

### Run Unit Tests
```powershell
python 03_documentation_analysis/topic_modelling/test_bertopic_documentation_topics.py
```

### Reproduce Commit Dataset Generation
```powershell
python 04_commit_classification/scripts/build_5000_commit_dataset.py
```

### Reproduce Multi-Modal Criteria Evaluation
```powershell
python 04_commit_classification/scripts/validate_multimodal_criteria.py
```