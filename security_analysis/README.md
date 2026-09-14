# Security Analysis of the Agentic Software Sample

**Date:** 14 September 2026
**Input sample:** [`Repos_Final_Sample.csv`](../Repos_Final_Sample.csv) (170 repositories)
**Scope:** Extends the project's software-quality/maintenance research with a security-posture analysis, covering both traditional software security and agent-specific execution risks (sandboxing, tool permissions, credential handling, prompt-injection awareness).

---

## 1. Why this exists

The project's existing methodology (see [`../Sample_selection_criteria_report.md`](../Sample_selection_criteria_report.md)) defines agentic software around 5 pillars: **Agent + Tools + Memory + Orchestration Loop + Environment & Guardrails**. This analysis focuses on that last pillar — how these 170 repositories actually handle security, both as a governance practice (do they document a disclosure process?) and as a technical reality (do they ship known-vulnerable dependencies, do they document safeguards against an autonomously-acting agent doing something harmful?).

Rather than one blended "security score," results are kept as **several independent signals**, because different repos report/handle security in inconsistent ways (some use GitHub's formal advisory feature, some just mention fixes in a changelog, some never disclose anything at all). Merging these into one number would hide that inconsistency instead of measuring it.

---

## 2. Pipeline overview

| Stage | Script | Output | Data source(s) |
|---|---|---|---|
| 1 | `analyze_security_docs.py` | `security_docs_analysis.csv` | Local documentation corpus (`../documentation_files.jsonl`) |
| 2 | `fetch_security_advisories.py` | `security_advisory_signals.csv` | GitHub GHSA API + GitHub Releases API + local doc corpus |
| 3 | `fetch_dependency_risk.py` | `security_dependency_risk.csv` | GitHub Dependency Graph (SBOM) API + OSV.dev |
| 4 | `diagnose_no_signal_repos.py` | `no_signal_diagnosis.csv` | Re-checks stage-2's "no signal" repos with extra sources |
| 5 | `merge_security_analysis.py` | `Security_Analysis_Combined.csv` | Merges 1–4 + sample metadata, keyed by repo |

All scripts are safe to re-run: each caches its network calls to a local JSON file (`*_cache.json`) so repeated runs only fetch new/changed data. Scripts resolve shared inputs (`Repos_Final_Sample.csv`, `.env`, `documentation_files.jsonl`) from the repo root automatically and write outputs into this folder, regardless of which directory you run them from.

```bash
# from repo root, or from inside security_analysis/ -- both work
python security_analysis/analyze_security_docs.py
python security_analysis/fetch_security_advisories.py
python security_analysis/fetch_dependency_risk.py
python security_analysis/diagnose_no_signal_repos.py
python security_analysis/merge_security_analysis.py
```

Requires a `GITHUB_TOKEN` in a `.env` file at the repo root (for higher API rate limits). `documentation_files.jsonl` must be present at the repo root (unzip `../documentation_files.zip`, which is tracked via Git LFS).

---

## 3. What each stage measures

### Stage 1 — Documentation-based security signals (`analyze_security_docs.py`)
Scans every collected doc file per repo for two categories of keyword/regex signal:
- **SECURITY.md quality**: does it name a contact channel, a response SLA, supported versions, a PGP key.
- **Agent-specific guardrails** (7 signals): Sandboxing, Human_Approval_Gate, Tool_Allow_Deny_List, Rate_Limiting, Credential_Handling, Prompt_Injection_Awareness, Audit_Logging — these map to the "Environment & Guardrails" pillar of the agentic-software definition.

### Stage 2 — Historical vulnerability signals (`fetch_security_advisories.py`)
Checks three independent, non-overlapping sources for evidence a repo has ever had a disclosed vulnerability:
1. **GHSA API** — formal GitHub Security Advisories the maintainers published.
2. **GitHub Releases** — CVE/GHSA IDs or "security fix" language in release notes.
3. **Doc corpus** — CVE/GHSA IDs in `CHANGELOG`/`HISTORY`/`SECURITY`/`RELEASE*` files.

Kept separate per source (`Advisory_Sources_Used` column) rather than merged, since overlap between the three is low (only ~14% of repos with any signal use all three).

### Stage 3 — Supply-chain / dependency risk (`fetch_dependency_risk.py`)
1. Pulls each repo's **SBOM** (Software Bill of Materials) from GitHub's Dependency Graph API — the exact list of packages+versions that repo depends on, read from its own lockfile.
2. Batch-queries **OSV.dev** (Google-operated aggregator of GHSA, npm advisory DB, PyPA Advisory DB, RustSec, Go vuln DB, etc.) for every unique package+version across the whole sample (~56,000 unique triples).
3. Reports, per repo: how many dependencies are individually flagged vulnerable, and how many distinct vulnerability IDs that adds up to (one package can carry multiple advisories).

This answers a different question than Stage 2: not "is this repo's own code vulnerable" but "does it depend on something that is."

### Stage 4 — No-signal diagnosis (`diagnose_no_signal_repos.py`)
For the repos with zero result from Stage 2, checks whether that's a **real absence** or a **detection gap**:
- Rechecks the GHSA API with explicit HTTP status tracking (distinguishes "confirmed zero" from "denied/no permission," which Stage 2 could not tell apart).
- Confirms whether the repo had any doc-corpus records at all (a repo with zero docs collected cannot produce a doc-corpus signal regardless of content).
- Lists root-level files to catch changelog/security filenames Stage 2's regex didn't anticipate.
- Runs a heuristic OSV.dev lookup using the repo's own name as a package name, to catch vulnerabilities reported against the project's *own* published package rather than found via GHSA/Releases/docs.

---

## 4. Key results (170 repos)

- **Guardrail documentation**: coverage varies widely across the 7 agent-specific signals; `openclaw` scores 7/7, but many repos document few or none.
- **Advisory signals**: 125/170 (73.5%) show at least one vulnerability-disclosure signal from any of the 3 sources; only 23/170 (13.5%) use all three consistently; 34 repos are only visible via informal doc-corpus mentions (would be invisible to a GHSA-API-only approach).
- **Dependency risk**: 117/170 (69%) have ≥1 dependency with a known OSV.dev vulnerability; 46/170 had no SBOM data at all. Risk is better judged by `Vulnerable_Dependency_Ratio` (normalizes for dependency-tree size) than by raw counts, which are skewed toward repos with huge dependency trees.
- **No-signal diagnosis**: of the 45 "no advisory signal" repos, 30 appear to be a real absence, 15 are detection gaps — including 3 repos (`MetaGPT`, `ansible`, `letta`) with real advisories against their own published package that none of the 3 original sources caught.
- **Supply-chain example**: 25 repos have zero advisories against their own code but ≥1 known-vulnerable dependency — e.g. `SuperAGI` has no advisories of its own, but 59 of its 567 dependencies are individually flagged, totaling 627 distinct known vulnerabilities in its dependency tree.

---

## 5. Known limitations

These should be addressed (or at least acknowledged) before citing these numbers as final findings:

1. **No manual validation pass.** All signals come from automated keyword/regex/API heuristics; none have been checked against a human-labeled ground truth (unlike `manual_review.csv` elsewhere in this repo, which was deliberately human-corrected).
2. **GHSA "zero" is ambiguous in Stage 2.** A 403/404 (denied/no permission) and a genuine empty result both show as `GHSA_API_Advisory_Count = 0`. Only Stage 4 disambiguates this, and only for the 45 no-signal repos — not the full 170.
3. **OSV version matching is exact-match only.** Non-standard version strings (Go pseudo-versions, npm pre-release tags) can silently fail to match even when a real vulnerability applies — a false-negative risk with no way to detect it from the output alone.
4. **The Stage 4 OSV self-package heuristic is weak.** It guesses package name = lowercased repo name, which fails for scoped npm packages (`@org/name`) or any project whose published package name differs from its repo name. The "3 real gaps found" is likely an undercount.
5. **Changelog-filename regex is incomplete.** Confirmed 10 repos use naming conventions not covered by the current regex (`RELEASE_NOTES_v0.1.8.md`, `.changelogrc`, `release-plz.toml`, `CHANGELOG_zh.md`).
6. **Doc corpus only covers each repo's default branch** (inherited from the original collection methodology, not introduced here).
7. **Guardrail signals are binary and unweighted** — a passing mention of "sandbox" scores identically to a dedicated sandboxing architecture; no severity/context weighting.
8. **Dependency-risk counts aren't severity-weighted** — a critical RCE and a low-severity DoS both count as "1 vulnerability."
9. **46 no-SBOM repos are ambiguous** — unclear whether that means "few/no dependencies" or "GitHub's dependency graph failed silently" for that repo's manifest format.
10. **Sample-size discrepancy**: the methodology report describes a 175-repo final sample, but the actual `Repos_Final_Sample.csv` in this repo has 170 rows. This analysis used the real 170; the discrepancy itself hasn't been investigated.

**Recommended next step:** manually spot-check ~15–20 repos across the guardrail signals and advisory counts to estimate real precision/recall, and re-run the Stage 4 GHSA status recheck across all 170 repos (not just the 45 no-signal ones) to close limitation #2.

---

## 6. File reference

| File | Rows | Description |
|---|---|---|
| `security_docs_analysis.csv` | 170 | SECURITY.md quality + 7 guardrail signals per repo |
| `security_advisory_signals.csv` | 170 | GHSA/Releases/docs-corpus advisory signals per repo |
| `security_dependency_risk.csv` | 170 | SBOM size, vulnerable dependency count, distinct vulnerabilities |
| `no_signal_diagnosis.csv` | 45 | Diagnosis for repos with zero advisory signal |
| `Security_Analysis_Combined.csv` | 170 | All of the above merged, one row per repo, 45 columns |
| `*_cache.json` | — | Cached API responses so scripts can be safely re-run without re-fetching everything |
