#!/usr/bin/env python3
"""
Fetch issue/PR timing metrics for the repositories in repos_with_docs.csv.

Purpose:
- RQ2: Maintenance efficiency
- Metrics:
    * Issue / PR resolution time
    * Time to first comment
    * PR merge rate
    * Activity ratio using Issues and PRs

This script reads a repo CSV, extracts GitHub repo URLs, and fetches the
relevant issue and pull request metadata from the GitHub REST API.

Example:
    python fetch_rq2_issue_pr_metrics.py --input repos_with_docs.csv
    python fetch_rq2_issue_pr_metrics.py --input repos_with_docs.csv --max-issues 50 --max-prs 50
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from statistics import mean, median
from typing import Any, Dict, List, Optional

GITHUB_API_ROOT = "https://api.github.com"
GITHUB_GRAPHQL_URL = f"{GITHUB_API_ROOT}/graphql"


class GitHubAPIError(RuntimeError):
    pass


def load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass


def parse_iso8601(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            return None


def days_between(start: Optional[str], end: Optional[str]) -> Optional[float]:
    start_dt = parse_iso8601(start)
    end_dt = parse_iso8601(end)
    if start_dt is None or end_dt is None:
        return None
    return (end_dt - start_dt).total_seconds() / 86400.0


def github_get(url: str, token: Optional[str], retries: int = 3) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "rq2-github-metrics-fetcher",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url=url, headers=headers, method="GET")
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read().decode("utf-8")
                return json.loads(data)
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            message = details
            try:
                parsed = json.loads(details)
                message = parsed.get("message", details)
            except json.JSONDecodeError:
                pass
            lower = str(message).lower()
            if exc.code in (403, 429) and ("rate limit" in lower or "secondary rate limit" in lower or "abuse" in lower):
                remaining = exc.headers.get("X-RateLimit-Remaining") if exc.headers else None
                if remaining == "0":
                    reset = exc.headers.get("X-RateLimit-Reset") if exc.headers else None
                    reset_text = f" Retry after Unix time {reset}." if reset else ""
                    raise GitHubAPIError(
                        "GitHub API quota is exhausted for the authenticated token."
                        f" Replace/revoke the token or wait for the quota reset.{reset_text}"
                    ) from exc
                if attempt < retries:
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    delay = float(retry_after) if retry_after and retry_after.isdigit() else (2 ** attempt)
                    time.sleep(delay)
                    continue
                raise GitHubAPIError(
                    "GitHub API rate limit exceeded. Set GITHUB_TOKEN in your environment or .env file."
                ) from exc
            raise GitHubAPIError(f"HTTP {exc.code}: {message}") from exc
        except urllib.error.URLError as exc:
            if attempt < retries and isinstance(exc.reason, TimeoutError):
                time.sleep(2 ** attempt)
                continue
            raise GitHubAPIError(f"Network error: {exc}") from exc
    raise GitHubAPIError("GitHub request failed after retries.")


def check_github_authentication(token: Optional[str]) -> None:
    """Fail early with the account and quota state before collecting data."""
    if not token:
        raise GitHubAPIError("No GitHub token found. Add GITHUB_TOKEN to .env or the environment.")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "rq2-github-metrics-fetcher",
    }
    request = urllib.request.Request(url=f"{GITHUB_API_ROOT}/user", headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            user = json.loads(response.read().decode("utf-8"))
            login = user.get("login", "unknown")
            remaining = response.headers.get("X-RateLimit-Remaining", "unknown")
            print(f"Authenticated to GitHub as {login}; API requests remaining: {remaining}")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        message = details
        try:
            message = json.loads(details).get("message", details)
        except json.JSONDecodeError:
            pass
        if exc.code in (401, 403) and "rate limit" in str(message).lower():
            reset = exc.headers.get("X-RateLimit-Reset") if exc.headers else None
            raise GitHubAPIError(
                "The token is recognized, but its GitHub API quota is exhausted."
                f" Wait for reset Unix time {reset} or replace the token."
            ) from exc
        if exc.code == 401:
            raise GitHubAPIError("GitHub rejected the token. Revoke it and create a new token with repository read access.") from exc
        raise GitHubAPIError(f"GitHub authentication check failed (HTTP {exc.code}): {message}") from exc


def parse_repo_url(repo_url: str) -> str:
    cleaned = repo_url.strip().rstrip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    if cleaned.lower().startswith("https://github.com/"):
        cleaned = cleaned[len("https://github.com/") :]
    elif cleaned.lower().startswith("http://github.com/"):
        cleaned = cleaned[len("http://github.com/") :]
    if cleaned.startswith("github.com/"):
        cleaned = cleaned[len("github.com/") :]
    return cleaned.strip("/")


def github_graphql(query: str, token: Optional[str], variables: Optional[Dict[str, Any]] = None, retries: int = 3) -> Any:
    if not token:
        raise GitHubAPIError("GitHub token is required for GraphQL queries.")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "rq2-github-metrics-fetcher",
        "Accept": "application/vnd.github+json",
    }
    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    request = urllib.request.Request(url=GITHUB_GRAPHQL_URL, headers=headers, data=payload, method="POST")
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read().decode("utf-8")
                return json.loads(data)
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            message = details
            try:
                parsed = json.loads(details)
                errors = parsed.get("errors") or [{"message": details}]
                message = errors[0].get("message", details)
            except Exception:
                pass
            lower = str(message).lower()
            if exc.code in (403, 429) and ("rate limit" in lower or "secondary rate limit" in lower or "abuse" in lower):
                if attempt < retries:
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    delay = float(retry_after) if retry_after and retry_after.replace(".", "", 1).isdigit() else (2 ** attempt)
                    time.sleep(delay)
                    continue
                raise GitHubAPIError("GitHub API rate limit exceeded. Set GITHUB_TOKEN in your environment or .env file.") from exc
            raise GitHubAPIError(f"GraphQL error: {message}") from exc
        except urllib.error.URLError as exc:
            if attempt < retries and isinstance(exc.reason, TimeoutError):
                time.sleep(2 ** attempt)
                continue
            raise GitHubAPIError(f"Network error: {exc}") from exc
    raise GitHubAPIError("GitHub GraphQL request failed after retries.")


def fetch_all_repository_issues(owner: str, repo: str, token: Optional[str]) -> List[Dict[str, Any]]:
    """Fetch every issue in a repository without hitting the search API 1,000 result cap."""
    items: List[Dict[str, Any]] = []
    cursor = None
    while True:
        query = """
        query($owner: String!, $repo: String!, $after: String) {
          repository(owner: $owner, name: $repo) {
            issues(first: 100, after: $after, orderBy: {field: CREATED_AT, direction: ASC}, states: [OPEN, CLOSED]) {
              nodes {
                number
                title
                state
                                created_at: createdAt
                                closed_at: closedAt
              }
              pageInfo {
                hasNextPage
                endCursor
              }
            }
          }
        }
        """
        result = github_graphql(query, token, {"owner": owner, "repo": repo, "after": cursor})
        repository = (result.get("data") or {}).get("repository")
        if not repository:
            break
        issues_page = repository.get("issues") or {}
        nodes = issues_page.get("nodes") or []
        items.extend(nodes)
        page_info = issues_page.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
        if not cursor:
            break
    return items


def fetch_all_repository_prs(owner: str, repo: str, token: Optional[str]) -> List[Dict[str, Any]]:
    """Fetch every pull request in a repository without hitting search API limits."""
    items: List[Dict[str, Any]] = []
    cursor = None
    while True:
        query = """
        query($owner: String!, $repo: String!, $after: String) {
          repository(owner: $owner, name: $repo) {
            pullRequests(first: 100, after: $after, orderBy: {field: CREATED_AT, direction: ASC}, states: [OPEN, CLOSED]) {
              nodes {
                number
                title
                state
                                created_at: createdAt
                                merged_at: mergedAt
                                closed_at: closedAt
              }
              pageInfo {
                hasNextPage
                endCursor
              }
            }
          }
        }
        """
        result = github_graphql(query, token, {"owner": owner, "repo": repo, "after": cursor})
        repository = (result.get("data") or {}).get("repository")
        if not repository:
            break
        prs_page = repository.get("pullRequests") or {}
        nodes = prs_page.get("nodes") or []
        items.extend(nodes)
        page_info = prs_page.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
        if not cursor:
            break
    return items


def get_issue_comments(owner: str, repo: str, issue_number: int, token: Optional[str]) -> List[Dict[str, Any]]:
    url = f"{GITHUB_API_ROOT}/repos/{owner}/{repo}/issues/{issue_number}/comments?per_page=100"
    items: List[Dict[str, Any]] = []
    page = 1
    while True:
        paged_url = f"{url}&page={page}" if "?" in url else f"{url}?page={page}"
        payload = github_get(paged_url, token)
        if not isinstance(payload, list):
            break
        if not payload:
            break
        items.extend(payload)
        if len(payload) < 100:
            break
        page += 1
    return items


def get_pr_comments(owner: str, repo: str, pr_number: int, token: Optional[str]) -> List[Dict[str, Any]]:
    url = f"{GITHUB_API_ROOT}/repos/{owner}/{repo}/pulls/{pr_number}/comments?per_page=100"
    items: List[Dict[str, Any]] = []
    page = 1
    while True:
        paged_url = f"{url}&page={page}" if "?" in url else f"{url}?page={page}"
        payload = github_get(paged_url, token)
        if not isinstance(payload, list):
            break
        if not payload:
            break
        items.extend(payload)
        if len(payload) < 100:
            break
        page += 1
    return items


def summarize_issue_times(issues: List[Dict[str, Any]], token: Optional[str], owner: str, repo: str, sleep_seconds: float = 0.0) -> Dict[str, Any]:
    resolution_days: List[float] = []
    first_comment_days: List[float] = []

    for issue in issues:
        created_at = issue.get("created_at")
        closed_at = issue.get("closed_at")
        if created_at and closed_at:
            delta = days_between(created_at, closed_at)
            if delta is not None:
                resolution_days.append(delta)

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
        comments = get_issue_comments(owner, repo, int(issue["number"]), token)
        if comments:
            first_comment = min((c.get("created_at") for c in comments if c.get("created_at")), default=None)
            if first_comment:
                delta = days_between(created_at, first_comment)
                if delta is not None:
                    first_comment_days.append(delta)

    return {
        "issue_resolution_days": resolution_days,
        "time_to_first_comment_days": first_comment_days,
        "resolved_issue_count": len(resolution_days),
        "issues_with_first_comment_count": len(first_comment_days),
    }


def summarize_pr_times(prs: List[Dict[str, Any]], token: Optional[str], owner: str, repo: str, sleep_seconds: float = 0.0) -> Dict[str, Any]:
    resolution_days: List[float] = []
    first_comment_days: List[float] = []
    merged_prs = 0

    for pr in prs:
        created_at = pr.get("created_at")
        merged_at = pr.get("merged_at")
        closed_at = pr.get("closed_at")

        if created_at and (merged_at or closed_at):
            target = merged_at or closed_at
            delta = days_between(created_at, target)
            if delta is not None:
                resolution_days.append(delta)

        if merged_at:
            merged_prs += 1

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
        comments = get_pr_comments(owner, repo, int(pr["number"]), token)
        if comments:
            first_comment = min((c.get("created_at") for c in comments if c.get("created_at")), default=None)
            if first_comment and created_at:
                delta = days_between(created_at, first_comment)
                if delta is not None:
                    first_comment_days.append(delta)

    total_prs = len(prs)
    merge_rate = (merged_prs / total_prs) if total_prs else 0.0

    return {
        "pr_resolution_days": resolution_days,
        "time_to_first_comment_days": first_comment_days,
        "merged_pr_count": merged_prs,
        "pr_merge_rate": merge_rate,
    }


def summarize_repo(owner: str, repo: str, token: Optional[str], max_issues: int, max_prs: int, sleep_seconds: float) -> Dict[str, Any]:
    all_issues = fetch_all_repository_issues(owner, repo, token)
    all_prs = fetch_all_repository_prs(owner, repo, token)

    issues_only = all_issues if max_issues <= 0 else all_issues[:max_issues]
    prs_only = all_prs if max_prs <= 0 else all_prs[:max_prs]

    issue_summary = summarize_issue_times(issues_only, token, owner, repo, sleep_seconds=sleep_seconds)
    pr_summary = summarize_pr_times(prs_only, token, owner, repo, sleep_seconds=sleep_seconds)

    issue_resolution_values = issue_summary["issue_resolution_days"]
    pr_resolution_values = pr_summary["pr_resolution_days"]
    issue_first_comment_values = issue_summary["time_to_first_comment_days"]
    pr_first_comment_values = pr_summary["time_to_first_comment_days"]

    def safe_stat(values: List[float]) -> Optional[float]:
        if not values:
            return None
        return float(mean(values))

    def safe_median(values: List[float]) -> Optional[float]:
        if not values:
            return None
        return float(median(values))

    issue_activity_ratio = (len(issues_only) / len(prs_only)) if prs_only else 0.0

    return {
        "repo": f"{owner}/{repo}",
        "issue_count": len(issues_only),
        "pr_count": len(prs_only),
        "issue_activity_ratio": issue_activity_ratio,
        "median_issue_resolution_days": safe_median(issue_resolution_values),
        "mean_issue_resolution_days": safe_stat(issue_resolution_values),
        "median_pr_resolution_days": safe_median(pr_resolution_values),
        "mean_pr_resolution_days": safe_stat(pr_resolution_values),
        "median_issue_first_comment_days": safe_median(issue_first_comment_values),
        "mean_issue_first_comment_days": safe_stat(issue_first_comment_values),
        "median_pr_first_comment_days": safe_median(pr_first_comment_values),
        "mean_pr_first_comment_days": safe_stat(pr_first_comment_values),
        "issue_resolved_count": issue_summary["resolved_issue_count"],
        "pr_merge_rate": pr_summary["pr_merge_rate"],
    }


def read_repo_rows(csv_path: str) -> List[Dict[str, str]]:
    with open(csv_path, "r", encoding="utf-8", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        return list(reader)


def write_summary_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    fieldnames = [
        "repo",
        "issue_count",
        "pr_count",
        "issue_activity_ratio",
        "median_issue_resolution_days",
        "mean_issue_resolution_days",
        "median_pr_resolution_days",
        "mean_pr_resolution_days",
        "median_issue_first_comment_days",
        "mean_issue_first_comment_days",
        "median_pr_first_comment_days",
        "mean_pr_first_comment_days",
        "issue_resolved_count",
        "pr_merge_rate",
    ]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch issue and PR timing metrics for each repo in a dataset.")
    parser.add_argument("--input", required=True, help="CSV file with repo metadata, including Repo_URL")
    parser.add_argument("--output", default="rq2_repo_metrics.csv", help="Output summary CSV")
    parser.add_argument("--max-issues", type=int, default=0, help="Optional cap on issue items inspected per repo; 0 means all issues")
    parser.add_argument("--max-prs", type=int, default=0, help="Optional cap on PR items inspected per repo; 0 means all PRs")
    parser.add_argument("--sleep", type=float, default=2.0, help="Delay in seconds between GitHub API calls to avoid rate limiting")
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")

    check_github_authentication(token)

    rows = read_repo_rows(args.input)
    summary: List[Dict[str, Any]] = []

    for idx, row in enumerate(rows, start=1):
        repo_url = row.get("Repo_URL", "").strip()
        if not repo_url:
            continue
        try:
            repo_path = parse_repo_url(repo_url)
            owner, repo = repo_path.split("/", 1)
            print(f"[{idx}/{len(rows)}] Processing {owner}/{repo}")
            summary_row = summarize_repo(owner, repo, token, args.max_issues, args.max_prs, args.sleep)
            summary.append(summary_row)
        except Exception as exc:
            print(f"Warning: could not process {repo_url}: {exc}", file=sys.stderr)
        if args.sleep > 0:
            time.sleep(args.sleep)

    write_summary_csv(args.output, summary)
    print(f"Saved {len(summary)} repo summaries to {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GitHubAPIError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print("Tip: create a GitHub token and export it as GITHUB_TOKEN or GH_TOKEN.", file=sys.stderr)
        raise SystemExit(1)
