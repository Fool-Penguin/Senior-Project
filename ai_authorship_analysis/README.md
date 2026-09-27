# AI Authorship & Bot Contribution Analysis

**Dates:** 21 September 2026 (Method 1, API-based) · 27 September 2026 (Method 2, exact git-based)
**Input sample:** [`../Repos_Final_Sample.csv`](../Repos_Final_Sample.csv) (170 repositories)
**Scope:** Detects *detectable* AI-tool involvement and bot-account contributions in each repo's commit history, using two independent methods that cross-validate each other.

---

## 1. Why this exists

The original goal was to differentiate "AI-managed" vs. "human-managed" commits in these agentic-AI repositories. That's not achievable in general — git has no field for "was AI involved," and a human using an AI coding assistant and committing under their own account leaves zero trace. This is a known, unsolved problem industry-wide, not a gap specific to this project (confirmed by Liu et al., *"Debt Behind the AI Boom"* [2026] — see Section 6 below — who explicitly hit the same wall at a much larger scale).

Instead, this analysis measures a **narrower, answerable proxy**: what fraction of commits carry a *detectable fingerprint* of AI-tool usage (account metadata, or a signature phrase certain tools auto-append) or come from a *bot account* (including projects using their own agent to maintain themselves — "self-dogfooding"). This is always a **lower bound** on real AI involvement, never a true measurement of the full AI-vs-human split.

Two methods were built, in order:
- **Method 1** (`detect_ai_commits.py`) — fast, API-based, aggregate counts only.
- **Method 2** (`attribute_ai_commits_git.py`) — exact, per-commit, local-clone-based, built specifically to replicate the methodology of Liu et al. (2026) so that paper can be cited as a direct methodological reference.

Both are kept in this repo. They independently converge on very similar numbers for cross-checked repos (see Section 5), which is itself evidence the results are trustworthy rather than an artifact of either method's specific quirks.

---

## 2. Method 1: API-based aggregate signals (`detect_ai_commits.py`)

Two independent, scalable signals, neither requiring a repo clone or commit enumeration:

### Signal 1: AI-tool commit signatures (text search, not a metadata field)
Several AI coding tools automatically append a recognizable line to commit messages, e.g. Claude Code adds `🤖 Generated with Claude Code` + `Co-Authored-By: Claude <noreply@anthropic.com>`. We query GitHub's **Search API** (`GET /search/commits?q=repo:{owner}/{name} "<signature>"`) for 5 known signatures (Claude Code, Cursor, GitHub Copilot, Codex, a generic `🤖 Generated` marker) and take the `total_count` GitHub's search index returns — one HTTP request per signature per repo, no pagination through history.

### Signal 2: Bot-account contributions (account metadata, not commit content)
Independent of what a commit's message says, GitHub itself marks certain accounts with `type: "Bot"`. We call the **Contributors API** (`GET /repos/{owner}/{repo}/contributors`) once per repo and filter for bot-type accounts, along with their aggregate contribution counts. This catches generic bots (`dependabot[bot]`, `renovate[bot]`) as well as **project-specific agent bots** (e.g. `openclaw-mantis[bot]`, `n8n-assistant[bot]`) — the latter being a genuinely interesting "does this agentic-AI project use its own agent to maintain itself?" signal.

### Coverage denominator: total commit count
To express both signals as a percentage, we also fetch each repo's total commit count via the `Link: rel="last"` header trick on `GET /repos/{owner}/{repo}/commits?per_page=1` (default branch only) — again, one lightweight request, no enumeration.

### Scaling to 170 repos
- Search API has a strict 30 requests/minute limit (much stricter than the 5,000/hour core API limit used for the other two calls). Two personal access tokens were rotated to roughly double effective throughput.
- A subset of Search API queries came back rate-limited (`None`, meaning "couldn't check," not "zero matches"). Two targeted retry passes brought unresolved queries down from 184/850 to 10/850 (1.2%).

### Method 1 limitations
1. **Bot Contributors API only returns the first 100 contributors** — bots ranked below that on a large repo are invisible.
2. **`Combined_AI_Plus_Bot_Pct_Of_Commits` can double-count** — only aggregate counts are available, not per-commit identity, so a commit that is both bot-authored *and* carries a signature phrase would be counted in both categories. Treat as an upper-bound estimate.
3. **Only 5 signature patterns checked**, and only the commit-message + bot-account-type signal sources (missing author-email and author-name signals, unlike Method 2 / the reference paper).
4. **Default-branch-only** commit count denominator (Method 2 uses `--all` branches, matching the reference paper's actual scope).

---

## 3. Method 2: exact, per-commit git-based attribution (`attribute_ai_commits_git.py`)

Built to replicate the methodology of **Liu et al., "Debt Behind the AI Boom: A Large-Scale Empirical Study of AI-Generated Code in the Wild"** (arXiv:2603.28592, 2026), which attributes AI-authored commits using four sources of Git metadata evidence: (1) actor/bot login, (2) author email, (3) author name, (4) `Co-authored-by` trailers in commit messages — inspecting every commit exactly, not sampling or estimating.

### Why a local clone instead of the API
Method 1's biggest weakness is that it only ever sees **aggregate counts** — never the actual commits — so it can't de-duplicate overlaps, can't check more than 100 contributors, and is capped at whatever 5 signature patterns were hand-picked. Since the reference paper needed this rigor for **6,699 repos**, and our sample is only **170** (40x smaller), a full local scan is entirely feasible here.

We use a **blobless clone** (`git clone --bare --filter=blob:none`) — this fetches the complete commit graph and metadata (author, committer, message, timestamp) but skips file *contents*, keeping clone size small even for repos with 100K+ commits. `git log --all` then reads every commit across every branch, and each repo's clone is deleted immediately after scanning (no accumulating disk usage across 170 repos).

### The 4 signals, matched exactly like the paper (with one important precision fix)
- **Actor/bot login** → recovered from GitHub's noreply email format, e.g. `41898282+github-actions[bot]@users.noreply.github.com` literally embeds the account login and `[bot]` suffix — no GitHub API call needed at all.
- **Author email** and **author name** → checked directly against `git log`'s author/committer fields.
- **`Co-authored-by` trailers** → checked, but **only within the trailer line itself**, not the whole commit message.

**Important fix made during development:** the first version matched tool keywords against the *entire* commit message body, which produced real false positives — e.g. `"cursor"` matched hundreds of commits about database/UI pagination cursors, completely unrelated to the Cursor AI tool (verified directly: `perf(sessions): batch watcher cursor reads`, `fix(tasks): preserve cursors during unrelated database cleanup`, etc.). The second version also over-counted `Co-authored-by` trailers generically, since that trailer is also used for ordinary human pair-programming attribution, not just AI tools. Both are fixed in the current version: tool patterns are only matched against (a) author/committer name+email fields, and (b) the specific *content* of trailer lines — never free commit-message text.

### Cross-validation with Method 1
After the fix, `openclaw` converged to **3.22%** via Method 2 (all-branches scope) vs. **~3%** via Method 1 (default-branch scope, from the combined-percentage estimate) — close agreement between two independently-built methods gives real confidence in the corrected numbers, despite the different branch scope.

---

## 4. Key results

### Method 1 (API-based, 170 repos)
- **153/170 (90%)** repos have at least one commit with a detectable AI-tool signature.
- **123/170 (72.4%)** have at least one bot contributor account (top-100 only).

### Method 2 (exact git-based, 170 repos, 0 errors)
- **1,963,028 total commits scanned** across all 170 repos (every single one individually classified, no sampling) — median 4,293 commits/repo, largest single repo 146,204 commits.
- **164/170 (96.5%)** repos have at least one exact AI-signal commit.
- **Mean 11.77% / median 6.23%** of commits show an AI signal, range 0%–87.15%.
- Tool totals across the whole sample: **Claude 100,230** commits, GitHub Copilot 16,122, Cursor 6,619, Devin 3,918, Codex 3,634, Gemini 2,182 — Claude dominates by a wide margin, unlike the reference paper's own general-software dataset where Copilot led by repo count and Claude/Copilot were closer in commit count. This makes sense given our sample is specifically *agentic AI tooling*, a population naturally over-represented by Claude-based/Anthropic-adjacent projects.
- Highest AI-signal repos: `claude-code-best-practice` (87.2%), `cc-connect` (66.6%), `pentagi` (65.7%), `tradingview-mcp` (59.2%), `OpenJarvis` (57.5%), `claude-mem` (57.4%), `PraisonAI` (53.8%).
- Coverage varies enormously by repo age/size: large, older projects like `openclaw` (131,495 total commits across all branches) show only ~3% AI-signal coverage, while smaller/newer AI-native projects show far higher rates — consistent with the intuitive story that older commit history predates widespread AI-tool adoption.

---

## 5. Known limitations (both methods)

1. **This is a lower bound, not a true AI-vs-human measurement.** AI-assisted commits with no tool-added signature (e.g. copy-pasted from a chat UI, or a tool that doesn't add a footer) are invisible to *any* git-metadata-based method, for any repo — this is the same limitation the reference paper explicitly acknowledges (framed there as analogous to Self-Admitted Technical Debt research: measuring the *visible, attributable subset*, not the full universe).
2. **Method 1 specific:** capped at 100 contributors per repo; can double-count between AI-signature and bot-account categories; only 5 signature patterns; default-branch-only denominator; 1.2% of queries unresolved due to rate limiting.
3. **Method 2 specific:** tool-keyword regexes (`claude`, `cursor`, `copilot`, `codex`, `devin`, `gemini`) are broad substring matches against name/email/trailer fields — while much safer than matching free text, a name/email coincidentally containing one of these words would still false-positive (unverified how often this occurs at our scale; the reference paper mitigated this with manual review of every candidate pattern before finalizing their 29-tool rule list).
4. **Neither method has been manually validated** against a human-labeled sample, unlike the reference paper (100 sampled commits, 99.0% attribution precision confirmed by two independent reviewers). This remains a recommended next step before treating these numbers as final.
5. **A human can disable or never trigger these signatures**, and neither method inspects *what* a flagged commit actually changed — only *that* an account/tool pattern was involved.

---

## 6. Reference

Y. Liu, R. Widyasari, Y. Zhao, I. C. Irsan, J. Chen, D. Lo. *"Debt Behind the AI Boom: A Large-Scale Empirical Study of AI-Generated Code in the Wild."* arXiv:2603.28592, 2026. — Studied 302.6K AI-authored commits across 6,299 repos using the same 4-signal Git-metadata attribution approach Method 2 replicates here; found 22.7% of AI-introduced code-quality/security issues still survive at HEAD, and that AI tools introduce more security issues than they fix.

---

## 7. How to re-run

```bash
# Method 1: API-based, fast, aggregate counts
python ai_authorship_analysis/detect_ai_commits.py               # full run, resumes from cache
python ai_authorship_analysis/detect_ai_commits.py --retry-gaps  # retry only None (rate-limited) results
python ai_authorship_analysis/detect_ai_commits.py --limit 5     # quick test on first 5 repos

# Method 2: exact, per-commit, local clone + scan
python ai_authorship_analysis/attribute_ai_commits_git.py         # full run, resumes from cache
python ai_authorship_analysis/attribute_ai_commits_git.py --limit 5 --refresh  # quick test
```

Method 1 requires `GITHUB_TOKEN` in `.env` at the repo root; optionally `GITHUB_SPARETOKEN` for a second token rotated into Search API calls. Method 2 requires only `git` and network access to clone (no GitHub token needed at all — it clones public repos directly). Both resolve shared inputs (`Repos_Final_Sample.csv`, `.env`) from the repo root automatically regardless of which directory they're run from.

---

## 8. File reference

| File | Method | Description |
|---|---|---|
| `detect_ai_commits.py` | 1 | API-based detection script |
| `ai_commit_signals.csv` | 1 | 170 rows: per-signature commit counts, bot contributor list, total commit count, combined percentage |
| `ai_commit_cache.json` | 1 | Cached API responses so re-runs don't re-fetch unchanged data |
| `attribute_ai_commits_git.py` | 2 | Git-clone-based exact attribution script |
| `ai_commit_signals_git.csv` | 2 | 170 rows: exact per-tool commit counts, bot-account commits, AI-specific trailer commits, total commits (all branches), % with AI signal |
| `ai_commit_git_cache.json` | 2 | Cached per-repo scan results so re-runs don't re-clone unchanged repos |

### `ai_commit_signals.csv` columns (Method 1)

| Column | Meaning |
|---|---|
| `Commits_With_{Tool}_Signature` | Count of commits matching that tool's known signature phrase (one column per signature in `AI_SIGNATURES`) |
| `Total_AI_Signed_Commits_Any_Signature` | Sum across all 5 signature columns |
| `Bot_Contributor_Accounts` | Comma-separated list of bot-type contributor logins (top 100 only) |
| `Bot_Contributor_Count` | Count of distinct bot accounts |
| `Bot_Total_Contributions` | Sum of their aggregate contribution counts |
| `Total_Commits_In_Repo` | Total commits on the default branch |
| `Combined_AI_Plus_Bot_Pct_Of_Commits` | `(Total_AI_Signed_Commits_Any_Signature + Bot_Total_Contributions) / Total_Commits_In_Repo × 100` — an upper-bound estimate |

### `ai_commit_signals_git.csv` columns (Method 2)

| Column | Meaning |
|---|---|
| `Total_Commits` | Total commits across **all branches** (`git log --all`), matching the reference paper's scope |
| `Commits_Matching_{Tool}` | Exact count of commits where author/committer name+email or a trailer line matches that tool (one commit is counted once per matching tool, but can match >1 tool) |
| `Bot_Account_Commits` | Exact count of commits authored/committed by a `[bot]@users.noreply.github.com`-pattern account |
| `AI_Specific_Trailer_Commits` | Exact count of commits with a `Co-authored-by:`/`Generated with` trailer line that specifically names a known AI tool (NOT any trailer — ordinary human co-authorship is excluded) |
| `Any_AI_Signal_Commits_Unique` | Count of commits matching at least one of the above, counted once per commit (no double-counting, unlike Method 1) |
| `Pct_Commits_With_AI_Signal` | `Any_AI_Signal_Commits_Unique / Total_Commits × 100` |
