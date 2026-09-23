# Dataset Documentation: 5,000 Commits Classification Dataset

**File Formats**:
- CSV: [`dataset_5000_commits.csv`](file:///d:/4th-year/Senior-Project/dataset_5000_commits.csv) (7.26 MB, 5,000 rows, 30 columns)
- JSON: [`dataset_5000_commits.json`](file:///d:/4th-year/Senior-Project/dataset_5000_commits.json) (11.34 MB, full metadata structure)

**Source**: 50 active agentic and software engineering repositories sampled from `Repos_Final_Sample.csv` (100 recent commits per repository).

---

## 1. Classification Taxonomy

Each commit is classified according to a 4-tier taxonomy designed specifically for empirical software engineering research and code complexity evaluation ($\Delta \text{Complexity}$ before & after bug fixes):

| Category | Description | Examples |
| :--- | :--- | :--- |
| **`INTERACTIVE_AI_COAUTHORED`** | Commits where a human developer was assisted by interactive AI tools (inline suggestions, pair programming, chat). | Claude Code, Cursor IDE, GitHub Copilot, Windsurf |
| **`AUTONOMOUS_AI_AGENT`** | Commits authored by autonomous generative agents that plan, write, and open PRs independently. | Sweep AI, Cognition Devin, ClawSweeper, OpenHands |
| **`DETERMINISTIC_DEVOPS_BOT`** | Rule-based, non-generative automation tools updating dependencies or running CI scripts. | Dependabot, Renovate, GitHub Actions |
| **`PURE_HUMAN`** | Standard human maintainer commits with zero AI or bot indicators. | Verified human developers |

---

## 2. Dataset Schema (30 Columns)

| Column Name | Data Type | Description |
| :--- | :---: | :--- |
| `repo_alias` | string | Repository alias or common name from sample selection |
| `repo_name` | string | Full GitHub repository identifier (`owner/repo`) |
| `repo_url` | string | Full URL to the GitHub repository |
| `commit_sha` | string | Full 40-character Git commit hash |
| `commit_short_sha` | string | 7-character abbreviated commit hash (e.g. `2545695`) |
| `commit_url` | string | Clickable URL to the commit on GitHub |
| `commit_date` | string | ISO 8601 timestamp of the commit author date |
| `author_name` | string | Git author name from commit metadata |
| `author_email` | string | Git author email address from commit metadata |
| `author_login` | string | GitHub actor login of the author (e.g., `steipete`, `dependabot[bot]`) |
| `committer_login` | string | GitHub actor login of the committer (e.g., `web-flow`) |
| `commit_title` | string | First line (subject) of the commit message |
| `commit_message` | string | Full raw commit message including body and trailers |
| `has_pr` | boolean | `True` if the commit is associated with a Pull Request |
| `pr_number` | integer | Associated Pull Request number (if found) |
| `pr_url` | string | Clickable URL to the associated Pull Request on GitHub |
| `pr_title` | string | Pull Request title |
| `pr_author_login` | string | GitHub login of the user/bot who opened the PR |
| `pr_labels` | string | Semicolon-separated list of PR labels |
| `pr_head_ref` | string | Name of the source branch for the PR |
| `pr_body_excerpt` | string | First 200 characters of the Pull Request description |
| `baseline_category` | string | Category assigned using baseline 4 Git criteria only |
| `multimodal_category` | string | Category assigned using enriched Multi-Modal pipeline |
| `is_ai_assisted` | integer | `1` if interactive AI or autonomous agent; `0` otherwise |
| `is_autonomous_agent` | integer | `1` if `AUTONOMOUS_AI_AGENT`; `0` otherwise |
| `is_devops_bot` | integer | `1` if `DETERMINISTIC_DEVOPS_BOT`; `0` otherwise |
| `is_pure_human` | integer | `1` if `PURE_HUMAN`; `0` otherwise |
| `uncovered_by_pr` | integer | `1` if baseline was `PURE_HUMAN` but PR revealed AI; `0` otherwise |
| `detection_clues` | string | Semicolon-separated list of all matching signals |
| `pr_clues` | string | Semicolon-separated list of PR-specific signals |

---

## 3. Quick Start Guide (Python & pandas)

```python
import pandas as pd

# Load dataset
df = pd.read_csv("dataset_5000_commits.csv")

# 1. Distribution of Multi-Modal Categories
print(df["multimodal_category"].value_counts())

# 2. Filter AI-assisted Commits (Interactive + Autonomous)
ai_commits = df[df["is_ai_assisted"] == 1]
print(f"Total AI-Assisted Commits: {len(ai_commits)}")

# 3. Filter Pure Human Commits (Control Group for Complexity Studies)
human_commits = df[df["is_pure_human"] == 1]
print(f"Total Human Commits: {len(human_commits)}")

# 4. Inspect Commits Uncovered Exclusively by PR Signals
uncovered = df[df["uncovered_by_pr"] == 1]
print(f"Commits uncovered by PR signals: {len(uncovered)}")
```
