# AI Authorship & Bot Contribution Analysis

**Date:** 21 September 2026
**Input sample:** [`../Repos_Final_Sample.csv`](../Repos_Final_Sample.csv) (170 repositories)
**Scope:** Detects *detectable* AI-tool involvement and bot-account contributions in each repo's commit history, at scale, without enumerating individual commits.

---

## 1. Why this exists

The original goal was to differentiate "AI-managed" vs. "human-managed" commits in these agentic-AI repositories. That's not achievable in general — git has no field for "was AI involved," and a human using an AI coding assistant and committing under their own account leaves zero trace. This is a known, unsolved problem industry-wide, not a gap specific to this project.

Instead, this analysis measures a **narrower, answerable proxy**: what fraction of commits carry a *detectable fingerprint* of AI-tool usage (a signature phrase certain tools auto-append) or come from a *bot account* (including projects using their own agent to maintain themselves — "self-dogfooding"). This is always a **lower bound** on real AI involvement, never a true measurement of the full AI-vs-human split.

---

## 2. Methodology — two independent, scalable signals

Neither signal requires downloading a repo's full commit history (infeasible for repos with 10,000+ commits). Both use aggregate/index-based GitHub API endpoints that return one number per query, regardless of repo size.

### Signal 1: AI-tool commit signatures (text search, not a metadata field)
Several AI coding tools automatically append a recognizable line to commit messages, e.g. Claude Code adds `🤖 Generated with Claude Code` + `Co-Authored-By: Claude <noreply@anthropic.com>`. We query GitHub's **Search API** (`GET /search/commits?q=repo:{owner}/{name} "<signature>"`) for 5 known signatures (Claude Code, Cursor, GitHub Copilot, Codex, a generic `🤖 Generated` marker) and take the `total_count` GitHub's search index returns — one HTTP request per signature per repo, no pagination through history.

### Signal 2: Bot-account contributions (account metadata, not commit content)
Independent of what a commit's message says, GitHub itself marks certain accounts with `type: "Bot"`. We call the **Contributors API** (`GET /repos/{owner}/{repo}/contributors`) once per repo and filter for bot-type accounts, along with their aggregate contribution counts. This catches generic bots (`dependabot[bot]`, `renovate[bot]`) as well as **project-specific agent bots** (e.g. `openclaw-mantis[bot]`, `n8n-assistant[bot]`) — the latter being a genuinely interesting "does this agentic-AI project use its own agent to maintain itself?" signal.

### Coverage denominator: total commit count
To express both signals as a percentage, we also fetch each repo's total commit count via the `Link: rel="last"` header trick on `GET /repos/{owner}/{repo}/commits?per_page=1` — again, one lightweight request, no enumeration.

### Scaling to 170 repos
- Search API has a strict 30 requests/minute limit (much stricter than the 5,000/hour core API limit used for the other two calls). Two personal access tokens were rotated to roughly double effective throughput.
- A subset of Search API queries came back rate-limited (`None`, meaning "couldn't check," not "zero matches" — see Limitations). Two targeted retry passes brought unresolved queries down from 184/850 to 10/850 (1.2%).

---

## 3. Key results (170 repos)

- **153/170 (90%)** repos have at least one commit with a detectable AI-tool signature.
- **123/170 (72.4%)** have at least one bot contributor account.
- Coverage varies enormously by repo: `openclaw` (97,707 total commits, an older/larger project) shows only ~3% combined AI+bot coverage, while smaller/newer AI-native projects show far higher rates — `claude-code-best-practice` (78.1%), `ruflo` (72.3%), `claude-mem` (65.7%), `pentagi` (62.6%), `PraisonAI` (54.6%).
- Some contributor accounts are named directly after the tool rather than `[bot]`-suffixed (e.g. `Copilot`, `Claude` as literal contributor logins in `ECC`/`mlflow`), suggesting direct agent-authored contributions distinct from CI-bot noise like `dependabot`.

---

## 4. Known limitations

1. **This is a lower bound, not a true AI-vs-human measurement.** AI-assisted commits with no tool-added signature (e.g. copy-pasted from a chat UI, or a tool that doesn't add a footer) are invisible to this method, for any repo, by any research approach currently available.
2. **`Combined_AI_Plus_Bot_Pct_Of_Commits` can double-count.** We only have aggregate counts, not per-commit identity, so a commit that is both bot-authored *and* carries an AI signature phrase would be counted in both categories. Treat this column as "at most X%," an upper-bound estimate, not an exact figure.
3. **10/850 signature queries (1.2%) remain unresolved** after two retry passes — a `None` value on rare rows means "we couldn't check," not "zero matches." Not accumulated into the `_Any_Signature` totals as zero (they're skipped), so this slightly *undercounts* rather than overcounts.
4. **Only 5 known signature patterns are checked.** Other AI tools (Devin, Aider, Sweep, Amazon Q, etc.) with different or no signature conventions won't be caught. Adding more is a small extension (edit `AI_SIGNATURES` in `detect_ai_commits.py`), but a residual invisible category will always remain.
5. **A human can disable or never trigger these signatures**, and a bot account's individual commits aren't inspected for content — so neither signal says anything about *what* was actually changed, only *that* an account/tool pattern was involved.

---

## 5. How to re-run

```bash
python ai_authorship_analysis/detect_ai_commits.py               # full run, resumes from cache
python ai_authorship_analysis/detect_ai_commits.py --retry-gaps  # retry only None (rate-limited) results
python ai_authorship_analysis/detect_ai_commits.py --limit 5     # quick test on first 5 repos
```

Requires `GITHUB_TOKEN` in `.env` at the repo root; optionally `GITHUB_SPARETOKEN` for a second token rotated into Search API calls to roughly double throughput. Resolves shared inputs (`Repos_Final_Sample.csv`, `.env`) from the repo root automatically regardless of which directory the script is run from.

---

## 6. File reference

| File | Description |
|---|---|
| `detect_ai_commits.py` | The detection script |
| `ai_commit_signals.csv` | 170 rows: per-signature commit counts, bot contributor list, total commit count, combined percentage |
| `ai_commit_cache.json` | Cached API responses (search counts, bot lists, total commit counts) so re-runs don't re-fetch unchanged data |

### `ai_commit_signals.csv` columns

| Column | Meaning |
|---|---|
| `Commits_With_{Tool}_Signature` | Count of commits matching that tool's known signature phrase (one column per signature in `AI_SIGNATURES`) |
| `Total_AI_Signed_Commits_Any_Signature` | Sum across all 5 signature columns |
| `Bot_Contributor_Accounts` | Comma-separated list of bot-type contributor logins |
| `Bot_Contributor_Count` | Count of distinct bot accounts |
| `Bot_Total_Contributions` | Sum of their aggregate contribution counts |
| `Total_Commits_In_Repo` | Total commits on the default branch |
| `Combined_AI_Plus_Bot_Pct_Of_Commits` | `(Total_AI_Signed_Commits_Any_Signature + Bot_Total_Contributions) / Total_Commits_In_Repo × 100` — an upper-bound estimate (see Limitation 2) |
