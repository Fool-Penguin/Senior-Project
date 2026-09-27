#!/usr/bin/env python3
"""Exact, per-commit AI-authorship attribution via local git history scanning.

Replicates the methodology of Liu et al., "Debt Behind the AI Boom" (2026),
which attributes AI-authored commits using four sources of Git metadata
evidence: (1) actor/author logins, (2) author emails, (3) author names, and
(4) Co-authored-by trailers in commit messages -- rather than our earlier
API-based approach (detect_ai_commits.py), which only checked commit-message
text (via Search API) and bot account type (via Contributors API, capped at
the first 100 contributors).

Why a local clone instead of the GitHub API:
  - Exact, not an estimate: every single commit is inspected, so there is
    no rate-limiting-induced gap, and no ambiguity about double-counting
    (each commit gets ONE unique classification, not overlapping counts).
  - The paper's 6,699-repo scale required this; our 170-repo scale makes
    it cheap enough to do properly too.
  - A "blobless" clone (`--filter=blob:none`) fetches full commit/tree
    metadata (author, committer, message, timestamp) but skips file
    contents, keeping clone size small even for large histories.

Usage:
    python attribute_ai_commits_git.py
    python attribute_ai_commits_git.py --limit 5
    python attribute_ai_commits_git.py --refresh
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

# Field separators unlikely to appear in real commit data.
_US = "\x1f"  # unit separator (between fields)
_RS = "\x1e"  # record separator (between commits)

LOG_FORMAT = _US.join(["%H", "%an", "%ae", "%cn", "%ce", "%s", "%b"]) + _RS

# --- Attribution rules: mirrors the paper's 4 evidence sources -------------
# Each known AI coding tool is matched against author name, author email,
# committer name, committer email, and the commit message (subject+body),
# using a keyword/pattern set per tool. A commit matches a tool if ANY of
# these fields contains that tool's pattern -- this covers all 4 of the
# paper's signal sources (actor login and author email both surface via the
# email/name fields; Co-authored-by trailers surface via the message field).
TOOL_PATTERNS: dict[str, re.Pattern] = {
    "Claude": re.compile(r"claude|anthropic", re.IGNORECASE),
    "Cursor": re.compile(r"\bcursor\b", re.IGNORECASE),
    "GitHub_Copilot": re.compile(r"copilot", re.IGNORECASE),
    "Codex": re.compile(r"\bcodex\b", re.IGNORECASE),
    "Devin": re.compile(r"\bdevin\b|cognition[- ]?ai", re.IGNORECASE),
    "Gemini": re.compile(r"gemini[- ]?(code[- ]?assist)?", re.IGNORECASE),
}

# Generic GitHub bot-account signal: GitHub's noreply email format embeds
# the account login verbatim, e.g. "41898282+github-actions[bot]@users.
# noreply.github.com" -- this recovers the "actor login is a bot" signal
# from plain git metadata, with no GitHub API call needed at all.
BOT_EMAIL_PATTERN = re.compile(r"\[bot\]@users\.noreply\.github\.com", re.IGNORECASE)
# Only match Co-authored-by TRAILER LINES specifically, not the whole
# message body/subject -- matching the paper's precision. Free-text mentions
# of a tool name (e.g. "fix cursor pagination bug", "cursor" as in a text/DB
# cursor) must NOT be treated as evidence; only structured trailer lines are.
CO_AUTHOR_TRAILER_LINE_PATTERN = re.compile(r"^Co-authored-by:.*$", re.IGNORECASE | re.MULTILINE)
GENERATED_WITH_LINE_PATTERN = re.compile(r"^.*Generated with.*$", re.IGNORECASE | re.MULTILINE)


def classify_commit(author_name: str, author_email: str, committer_name: str,
                     committer_email: str, message: str) -> tuple[set[str], bool, bool]:
    """Returns (matched_tools, is_bot_account, has_ai_specific_trailer).

    Tool patterns are checked ONLY against structured, high-confidence
    fields: author/committer name+email (account identity), and the
    content of Co-authored-by / "Generated with" trailer lines specifically
    -- never against arbitrary commit subject/body text, which produces
    false positives (e.g. "cursor" as a database/UI cursor, unrelated to
    the Cursor AI tool).

    IMPORTANT: `Co-authored-by:` trailers are also used for entirely mundane
    human pair-programming / squash-merge attribution, unrelated to AI.
    `has_ai_specific_trailer` is only True if a trailer line specifically
    names a known AI tool -- NOT simply "a trailer line exists".
    """
    identity_haystack = " ".join([author_name, author_email, committer_name, committer_email])
    trailer_lines = CO_AUTHOR_TRAILER_LINE_PATTERN.findall(message) + GENERATED_WITH_LINE_PATTERN.findall(message)
    trailer_haystack = " ".join(trailer_lines)

    matched_identity = {tool for tool, pattern in TOOL_PATTERNS.items() if pattern.search(identity_haystack)}
    matched_trailer = {tool for tool, pattern in TOOL_PATTERNS.items() if pattern.search(trailer_haystack)}
    matched = matched_identity | matched_trailer

    is_bot = bool(BOT_EMAIL_PATTERN.search(author_email) or BOT_EMAIL_PATTERN.search(committer_email))
    has_ai_specific_trailer = bool(matched_trailer)
    return matched, is_bot, has_ai_specific_trailer


# --- Git operations ------------------------------------------------------


class GitError(RuntimeError):
    pass


def run_git(args: list[str], cwd: Path | None = None, timeout: int = 300) -> str:
    try:
        result = subprocess.run(
            ["git"] + args, cwd=cwd, capture_output=True, text=True,
            timeout=timeout, encoding="utf-8", errors="replace",
        )
    except subprocess.TimeoutExpired as exc:
        raise GitError(f"git {' '.join(args)} timed out after {timeout}s") from exc
    if result.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {result.stderr.strip()[:500]}")
    return result.stdout


def clone_blobless(repo_url: str, dest: Path) -> None:
    run_git([
        "clone", "--bare", "--filter=blob:none", "--no-tags", "--quiet",
        repo_url, str(dest),
    ], timeout=600)


def scan_commits(repo_dir: Path) -> list[dict[str, str]]:
    """Returns every commit across all refs, parsed into fields."""
    raw = run_git(["log", "--all", f"--pretty=format:{LOG_FORMAT}"], cwd=repo_dir, timeout=300)
    commits = []
    for record in raw.split(_RS):
        record = record.strip("\n")
        if not record:
            continue
        parts = record.split(_US)
        if len(parts) < 7:
            continue
        sha, an, ae, cn, ce, subject, body = parts[:7]
        commits.append({
            "sha": sha, "author_name": an, "author_email": ae,
            "committer_name": cn, "committer_email": ce,
            "message": f"{subject}\n{body}",
        })
    return commits


# --- Cache / progress ----------------------------------------------------


def load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(path: Path, cache: dict[str, Any]) -> None:
    path.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", default=str(ROOT_DIR / "Repos_Final_Sample.csv"))
    parser.add_argument("--output", default=str(BASE_DIR / "ai_commit_signals_git.csv"))
    parser.add_argument("--cache", default=str(BASE_DIR / "ai_commit_git_cache.json"))
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    with open(args.sample, encoding="utf-8-sig") as f:
        sample_rows = list(csv.DictReader(f))
    if args.limit:
        sample_rows = sample_rows[: args.limit]

    cache_path = Path(args.cache)
    cache = {} if args.refresh else load_cache(cache_path)

    total = len(sample_rows)
    rows_out = []
    for index, row in enumerate(sample_rows, start=1):
        repo_url = row["Repo_URL"]
        name = row["Repo_Name"]

        if repo_url in cache:
            print(f"[{index}/{total}] Cached: {name}")
            stats = cache[repo_url]
        else:
            print(f"[{index}/{total}] Cloning + scanning: {name}")
            with tempfile.TemporaryDirectory(prefix="ai_attr_") as tmp:
                repo_dir = Path(tmp) / "repo.git"
                try:
                    clone_blobless(repo_url, repo_dir)
                    commits = scan_commits(repo_dir)
                except GitError as exc:
                    print(f"  Warning: failed for {name}: {exc}", file=sys.stderr)
                    stats = {"error": str(exc)}
                    cache[repo_url] = stats
                    save_cache(cache_path, cache)
                    rows_out.append({"Repo_Name": name, "Repo_URL": repo_url, "Error": str(exc)})
                    continue

            tool_counts = {tool: 0 for tool in TOOL_PATTERNS}
            bot_count = 0
            trailer_count = 0
            any_ai_signal_count = 0  # unique commits: matched a tool OR is a bot OR has a trailer

            for c in commits:
                matched, is_bot, has_trailer = classify_commit(
                    c["author_name"], c["author_email"], c["committer_name"],
                    c["committer_email"], c["message"],
                )
                for tool in matched:
                    tool_counts[tool] += 1
                if is_bot:
                    bot_count += 1
                if has_trailer:
                    trailer_count += 1
                if matched or is_bot or has_trailer:
                    any_ai_signal_count += 1

            stats = {
                "total_commits": len(commits),
                "tool_counts": tool_counts,
                "bot_account_commits": bot_count,
                "co_author_trailer_commits": trailer_count,
                "any_ai_signal_commits": any_ai_signal_count,
            }
            cache[repo_url] = stats
            save_cache(cache_path, cache)

        if "error" in stats:
            rows_out.append({"Repo_Name": name, "Repo_URL": repo_url, "Error": stats["error"]})
            continue

        out_row = {
            "Repo_Name": name,
            "Repo_URL": repo_url,
            "Total_Commits": stats["total_commits"],
        }
        for tool in TOOL_PATTERNS:
            out_row[f"Commits_Matching_{tool}"] = stats["tool_counts"].get(tool, 0)
        out_row["Bot_Account_Commits"] = stats["bot_account_commits"]
        out_row["AI_Specific_Trailer_Commits"] = stats["co_author_trailer_commits"]
        out_row["Any_AI_Signal_Commits_Unique"] = stats["any_ai_signal_commits"]
        out_row["Pct_Commits_With_AI_Signal"] = (
            round(stats["any_ai_signal_commits"] / stats["total_commits"] * 100, 2)
            if stats["total_commits"] else 0.0
        )
        rows_out.append(out_row)

    fieldnames: list[str] = []
    for r in rows_out:
        for k in r.keys():
            if k not in fieldnames:
                fieldnames.append(k)
    for r in rows_out:
        for k in fieldnames:
            r.setdefault(k, "")

    with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    ok_rows = [r for r in rows_out if not r.get("Error")]
    with_signal = sum(1 for r in ok_rows if r["Any_AI_Signal_Commits_Unique"] > 0)
    errored = len(rows_out) - len(ok_rows)
    print(f"\nWrote {len(rows_out)} rows to {args.output}")
    print(f"Repos with >=1 exact AI-signal commit: {with_signal} / {len(ok_rows)}")
    if errored:
        print(f"Repos that failed to clone/scan: {errored}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
