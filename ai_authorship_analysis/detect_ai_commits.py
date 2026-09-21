#!/usr/bin/env python3
"""Detect AI-tool-authored commits and bot contributors, at scale.

This does NOT enumerate commit history (which would be infeasible for repos
with tens of thousands of commits). Instead it uses two cheap, constant-cost
GitHub API calls per repo, regardless of repo size:

  1. GitHub Search API (`/search/commits`) -- for each known AI-tool commit
     signature (Claude Code, Cursor, GitHub Copilot, Codex, a generic
     "🤖 Generated" marker), asks GitHub's own search index for a
     `total_count` of matching commits. One request per signature per repo,
     no pagination through history needed.
  2. Contributors API (`/repos/{owner}/{repo}/contributors`) -- a single
     paginated-but-small call that lists top contributors including their
     `type` (User vs Bot). Bot accounts opening PRs/commits against a repo
     (including a project's own agent bot, i.e. "self-dogfooding") are a
     second, independent AI-involvement signal.

Output: ai_commit_signals.csv, one row per repo.

Usage:
    python detect_ai_commits.py
    python detect_ai_commits.py --refresh
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

API_ROOT = "https://api.github.com"

# Known commit-message signatures that AI coding tools append automatically.
# Kept as separate queries (GitHub search doesn't support OR of phrases).
AI_SIGNATURES: dict[str, str] = {
    "Claude_Code": '"Co-Authored-By: Claude"',
    "Cursor": '"Cursor Agent" OR "Co-Authored-By: Cursor"',
    "GitHub_Copilot": '"Co-authored-by: Copilot" OR "GitHub Copilot"',
    "Codex": '"Co-authored-by: Codex" OR "Generated with Codex"',
    "Generic_AI_Marker": '"🤖 Generated with"',
}


class GitHubApiError(RuntimeError):
    def __init__(self, status: int, details: str) -> None:
        super().__init__(f"GitHub API HTTP {status}: {details}")
        self.status = status


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def github_json(url: str, token: str | None, accept: str | None = None) -> Any:
    headers = {
        "Accept": accept or "application/vnd.github+json",
        "User-Agent": "ai-commit-detector",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read(5_000_000)
            return json.loads(raw.decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise GitHubApiError(exc.code, details) from exc
    except Exception as exc:
        raise RuntimeError(f"GitHub network error: {exc}") from exc


def search_commit_count(full_name: str, query: str, token: str | None) -> int | None:
    """Returns total_count of commits matching query, or None on failure."""
    q = f"repo:{full_name} {query}"
    url = f"{API_ROOT}/search/commits?{urllib.parse.urlencode({'q': q, 'per_page': 1})}"
    try:
        data = github_json(url, token, accept="application/vnd.github.cloak-preview+json")
        return data.get("total_count")
    except GitHubApiError as exc:
        if exc.status in (403, 422):  # rate limited or invalid query syntax
            return None
        raise
    except RuntimeError:
        return None


_LAST_PAGE_RE = re.compile(r'[?&]page=(\d+)[^>]*>;\s*rel="last"')


def fetch_total_commit_count(full_name: str, token: str | None) -> int | None:
    """Get the total commit count on the default branch via the Link header's
    rel="last" page number (per_page=1), avoiding downloading every commit."""
    url = f"{API_ROOT}/repos/{urllib.parse.quote(full_name, safe='/')}/commits?per_page=1"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ai-commit-detector"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            link_header = response.headers.get("Link") or response.headers.get("link")
            data = json.loads(response.read(200_000).decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 404, 409):  # 409 = empty repo
            return None
        raise GitHubApiError(exc.code, "") from exc
    except Exception:
        return None

    if link_header:
        match = _LAST_PAGE_RE.search(link_header)
        if match:
            return int(match.group(1))
    # No pagination needed: repo has 0 or 1 commits total.
    return len(data) if isinstance(data, list) else None


def fetch_bot_contributors(full_name: str, token: str | None) -> list[dict[str, Any]]:
    url = f"{API_ROOT}/repos/{urllib.parse.quote(full_name, safe='/')}/contributors?per_page=100&anon=false"
    try:
        data = github_json(url, token)
    except GitHubApiError as exc:
        if exc.status in (403, 404):
            return []
        raise
    if not isinstance(data, list):
        return []
    return [c for c in data if c.get("type") == "Bot"]


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
    parser.add_argument("--output", default=str(BASE_DIR / "ai_commit_signals.csv"))
    parser.add_argument("--cache", default=str(BASE_DIR / "ai_commit_cache.json"))
    parser.add_argument("--delay", type=float, default=2.0,
                         help="Seconds between Search API calls (its rate limit is much stricter than core API).")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--retry-gaps", action="store_true",
                         help="Only re-query signatures that came back None (rate-limited/failed) in the cache.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(ROOT_DIR / ".env")
    token = os.getenv("GITHUB_TOKEN")
    spare_token = os.getenv("GITHUB_SPARETOKEN")
    # Alternate between two tokens for Search API calls (each token gets its
    # own independent 30 req/min quota), roughly doubling effective throughput.
    search_tokens = [t for t in (token, spare_token) if t]
    if len(search_tokens) > 1:
        print(f"Using {len(search_tokens)} tokens in rotation for Search API calls.")
    search_token_idx = [0]

    def next_search_token() -> str | None:
        t = search_tokens[search_token_idx[0] % len(search_tokens)] if search_tokens else None
        search_token_idx[0] += 1
        return t

    with open(args.sample, encoding="utf-8-sig") as f:
        sample_rows = list(csv.DictReader(f))

    def full_name_from_url(url: str) -> str:
        return "/".join(url.rstrip("/").split("/")[-2:])

    for row in sample_rows:
        row["_full_name"] = full_name_from_url(row["Repo_URL"])

    if args.limit:
        sample_rows = sample_rows[: args.limit]

    cache_path = Path(args.cache)
    cache = {} if args.refresh else load_cache(cache_path)

    if args.retry_gaps:
        gap_repos = [
            row for row in sample_rows
            if any(v is None for v in cache.get(row["_full_name"], {}).get("signatures", {}).values())
        ]
        print(f"Retry-gaps mode: {len(gap_repos)} repos have at least one None signature result.")
        sample_rows = gap_repos

    total = len(sample_rows)
    rows_out = []
    for index, row in enumerate(sample_rows, start=1):
        full_name = row["_full_name"]

        needs_signature_retry = args.retry_gaps and any(
            v is None for v in cache.get(full_name, {}).get("signatures", {}).values()
        )
        needs_commit_count = full_name in cache and "total_commits" not in cache[full_name]

        if full_name in cache and not needs_signature_retry and not needs_commit_count:
            print(f"[{index}/{total}] Cached: {full_name}")
            result = cache[full_name]
        elif full_name in cache and needs_commit_count and not needs_signature_retry:
            # Backward-compat: cache predates the total_commits field. Only
            # fetch the one missing piece, reuse everything else already cached.
            print(f"[{index}/{total}] Fetching missing commit count: {full_name}")
            result = cache[full_name]
            try:
                result["total_commits"] = fetch_total_commit_count(full_name, token)
            except GitHubApiError as exc:
                print(f"Warning: commit-count fetch failed for {full_name}: {exc}", file=sys.stderr)
                result["total_commits"] = None
            cache[full_name] = result
            save_cache(cache_path, cache)
        else:
            print(f"[{index}/{total}] Fetching: {full_name}")
            result = {"signatures": {}, "bots": [], "total_commits": None}
            for sig_name, query in AI_SIGNATURES.items():
                count = search_commit_count(full_name, query, next_search_token())
                result["signatures"][sig_name] = count
                time.sleep(args.delay)

            try:
                result["total_commits"] = fetch_total_commit_count(full_name, token)
            except GitHubApiError as exc:
                print(f"Warning: commit-count fetch failed for {full_name}: {exc}", file=sys.stderr)

            try:
                bots = fetch_bot_contributors(full_name, token)
            except GitHubApiError as exc:
                if exc.status == 401 and token:
                    print("Warning: GITHUB_TOKEN invalid; continuing without token.", file=sys.stderr)
                    token = None
                    bots = []
                else:
                    print(f"Warning: contributors fetch failed for {full_name}: {exc}", file=sys.stderr)
                    bots = []
            result["bots"] = [{"login": b.get("login"), "contributions": b.get("contributions")} for b in bots]
            time.sleep(args.delay)

            cache[full_name] = result
            save_cache(cache_path, cache)

        sig_counts = result.get("signatures", {})
        total_ai_signed = sum(v for v in sig_counts.values() if isinstance(v, int))
        bots = result.get("bots", [])
        bot_names = ", ".join(b["login"] for b in bots)
        bot_total_contributions = sum(b.get("contributions", 0) or 0 for b in bots)
        total_commits = result.get("total_commits")

        # Combined estimate: AI-signed commits + bot-account commits, as a
        # share of the repo's total commit count. This is an UPPER-BOUND
        # estimate, not exact -- a single commit could in principle count
        # under both categories (e.g. a bot account whose commit also
        # happens to carry an AI signature), and we only have aggregate
        # counts, not per-commit identity, so we cannot de-duplicate that
        # overlap. Treat this as "at most X%", not a precise figure.
        if isinstance(total_commits, int) and total_commits > 0:
            combined_pct = round((total_ai_signed + bot_total_contributions) / total_commits * 100, 2)
        else:
            combined_pct = ""

        out_row = {
            "Repo_Name": row["Repo_Name"],
            "Repo_URL": row["Repo_URL"],
            "PRs_Total": row.get("PRs", ""),
        }
        for sig_name in AI_SIGNATURES:
            out_row[f"Commits_With_{sig_name}_Signature"] = sig_counts.get(sig_name, "")
        out_row["Total_AI_Signed_Commits_Any_Signature"] = total_ai_signed
        out_row["Bot_Contributor_Accounts"] = bot_names
        out_row["Bot_Contributor_Count"] = len(bots)
        out_row["Bot_Total_Contributions"] = bot_total_contributions
        out_row["Total_Commits_In_Repo"] = total_commits if total_commits is not None else ""
        out_row["Combined_AI_Plus_Bot_Pct_Of_Commits"] = combined_pct
        rows_out.append(out_row)

    fieldnames = list(rows_out[0].keys()) if rows_out else []
    rows_out.sort(key=lambda r: -r["Total_AI_Signed_Commits_Any_Signature"])

    with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    with_ai_signal = sum(1 for r in rows_out if r["Total_AI_Signed_Commits_Any_Signature"] > 0)
    with_bots = sum(1 for r in rows_out if r["Bot_Contributor_Count"] > 0)
    print(f"\nWrote {len(rows_out)} rows to {args.output}")
    print(f"Repos with >=1 AI-signed commit detected: {with_ai_signal} / {len(rows_out)}")
    print(f"Repos with >=1 bot contributor: {with_bots} / {len(rows_out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
