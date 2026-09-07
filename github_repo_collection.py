#!/usr/bin/env python3
"""
Standalone GitHub repository collector for the senior project.

This file intentionally does not modify or replace the existing fetch_repo.py.
It is designed to collect candidate repositories related to open-source agentic
software and export a structured dataset for exploratory maintainability analysis.

What this script collects:
- repository metadata for matching GitHub repositories
- basic documentation presence checks (README, SECURITY, CONTRIBUTING, SKILL, AGENTS)
- repository age, issue/PR counts, contributor counts, release counts
- optional GitHub issue metadata if a user decides to expand the study later

Usage:
    python github_repo_collection.py --output repo_dataset.csv
    python github_repo_collection.py --output repo_dataset.json --format json

Notes:
- Requires a GitHub token for higher rate limits; otherwise unauthenticated API
  requests will still work but with stricter limits.
- This script is intentionally conservative and avoids modifying existing project files.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Sequence, Tuple

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
GITHUB_REPO_URL = "https://api.github.com/repos"

SEARCH_KEYWORDS = [
    "AI agent",
    "LLM agent",
    "AI assistant",
    "assistant",
    "ai",
    "personal",
    "personal ai",
    "personal assistant",
    "autonomous agent",
    "agentic",
    "agentic AI",
    "AI automation",
    "AI agent framework",
    "agent platform",
    "LLM application",
]

FILTER_TERMS = [
    "agent",
    "assistant",
    "ai",
    "llm",
    "autonomous",
    "agentic",
    "automation",
    "personal",
]

OUTPUT_COLUMNS = [
    "repo_name",
    "full_name",
    "repo_url",
    "description",
    "language",
    "stars",
    "forks",
    "contributors_count",
    "created_at",
    "repo_age_days",
    "pull_requests_count",
    "issues_count",
    "open_issues_count",
    "releases_count",
    "commits_count",
    "total_md_files",
    "has_readme",
    "has_security",
    "has_contributing",
    "has_skill",
    "has_agents",
    "last_updated_at",
    "search_keyword",
]


class GitHubRequestError(RuntimeError):
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


def load_token() -> str | None:
    load_dotenv()
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token:
        return token.strip()
    return None


def github_get(url: str, token: str | None = None) -> Any:
    payload, _ = github_get_with_headers(url, token)
    return payload


def github_get_with_headers(url: str, token: str | None = None) -> tuple[Any, Dict[str, str]]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "senior-project-collector",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url=url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8")
            response_headers = {k: v for k, v in response.headers.items()}
            try:
                return json.loads(payload), response_headers
            except json.JSONDecodeError:
                return payload, response_headers
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        message = json.loads(details)["message"] if details.startswith("{") else details
        if exc.code == 403 and "rate limit" in str(message).lower():
            raise GitHubRequestError(
                "GitHub API rate limit exceeded. Please set a valid GITHUB_TOKEN or GH_TOKEN "
                "in your environment or .env file, then rerun the script."
            ) from exc
        raise GitHubRequestError(f"GitHub API error for {url}: {exc.code} - {message}") from exc
    except urllib.error.URLError as exc:
        raise GitHubRequestError(f"Network error while requesting {url}: {exc}") from exc


def compute_repo_age_days(created_at: str | None) -> int | None:
    if not created_at:
        return None
    try:
        created_dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - created_dt).days


def repo_matches_filter(repo_name: str, description: str | None, language: str | None, terms: Sequence[str]) -> bool:
    text = " ".join([
        repo_name or "",
        description or "",
        language or "",
    ]).lower()
    matched = [term for term in terms if term.lower() in text]
    return len(matched) >= 1


def search_repositories(keyword: str, token: str | None, page_size: int = 30, max_pages: int = 1, sleep: float = 0.2) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        params = {
            "q": keyword,
            "sort": "stars",
            "order": "desc",
            "per_page": page_size,
            "page": page,
        }
        url = f"{GITHUB_SEARCH_URL}?{urllib.parse.urlencode(params)}"
        payload = github_get(url, token)
        items = payload.get("items", [])
        if not items:
            break
        for item in items:
            results.append({
                "search_keyword": keyword,
                "full_name": item.get("full_name"),
                "repo_name": item.get("name"),
                "repo_url": item.get("html_url"),
                "description": item.get("description"),
                "language": item.get("language"),
                "stars": item.get("stargazers_count", 0),
                "forks": item.get("forks_count", 0),
                "last_updated_at": item.get("updated_at"),
            })
        if sleep > 0:
            time.sleep(sleep)
    return results


def count_total_via_pagination(endpoint: str, token: str | None) -> int | None:
    """Get total count for paginated endpoints without loading all pages."""
    try:
        payload, headers = github_get_with_headers(f"{endpoint}?per_page=1", token)
    except GitHubRequestError:
        return None

    link_header = headers.get("Link") or headers.get("link")
    if link_header:
        match = re.search(r'[?&]page=(\d+)[^>]*>;\s*rel="last"', link_header)
        if match:
            return int(match.group(1))

    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        total = payload.get("total_count")
        if total is not None:
            return int(total)
    return None


def fetch_search_total_count(query: str, token: str | None) -> int | None:
    url = f"https://api.github.com/search/issues?{urllib.parse.urlencode({'q': query, 'per_page': 1})}"
    try:
        payload = github_get(url, token)
    except GitHubRequestError:
        return None
    if isinstance(payload, dict):
        total = payload.get("total_count")
        if total is not None:
            return int(total)
    return None


def get_repo_metadata(full_name: str, token: str | None) -> Dict[str, Any]:
    repo = github_get(f"{GITHUB_REPO_URL}/{full_name}", token)
    if not isinstance(repo, dict):
        return {}

    created_at = repo.get("created_at")
    return {
        "full_name": full_name,
        "repo_name": repo.get("name"),
        "repo_url": repo.get("html_url"),
        "description": repo.get("description"),
        "language": repo.get("language"),
        "stars": repo.get("stargazers_count", 0),
        "forks": repo.get("forks_count", 0),
        "created_at": created_at,
        "repo_age_days": compute_repo_age_days(created_at),
        "open_issues_count": repo.get("open_issues_count", 0),
        "contributors_count": count_total_via_pagination(f"{GITHUB_REPO_URL}/{full_name}/contributors?anon=true", token),
        "releases_count": count_total_via_pagination(f"{GITHUB_REPO_URL}/{full_name}/releases", token),
        "commits_count": count_total_via_pagination(f"{GITHUB_REPO_URL}/{full_name}/commits", token),
        "pull_requests_count": fetch_search_total_count(f"repo:{full_name} is:pr", token),
        "issues_count": fetch_search_total_count(f"repo:{full_name} is:issue", token),
        "last_updated_at": repo.get("updated_at"),
    }


def list_repo_contents(full_name: str, token: str | None) -> List[str]:
    """List top-level repository files and docs names for documentation checks."""
    try:
        entries = github_get(f"{GITHUB_REPO_URL}/{full_name}/contents", token)
    except GitHubRequestError:
        return []
    if not isinstance(entries, list):
        return []
    return [str(item.get("name", "")) for item in entries if isinstance(item, dict)]


def build_documentation_flags(full_name: str, token: str | None) -> Dict[str, Any]:
    file_names = list_repo_contents(full_name, token)
    lower_names = {name.lower() for name in file_names}

    md_files = [name for name in file_names if name.lower().endswith(".md")]
    docs = {
        "total_md_files": len(md_files),
        "has_readme": "readme.md" in lower_names or "readme" in lower_names,
        "has_security": "security.md" in lower_names,
        "has_contributing": "contributing.md" in lower_names,
        "has_skill": "skill.md" in lower_names,
        "has_agents": "agents.md" in lower_names or "agents" in lower_names,
    }
    return docs


def deduplicate_repos(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: Dict[str, Dict[str, Any]] = {}
    for item in items:
        full_name = item.get("full_name")
        if not full_name:
            continue
        existing = seen.get(full_name)
        if existing is None or (item.get("stars", 0) or 0) > (existing.get("stars", 0) or 0):
            seen[full_name] = item
    return sorted(seen.values(), key=lambda x: (x.get("stars") or 0, x.get("full_name") or ""), reverse=True)


def write_csv(rows: List[Dict[str, Any]], path: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in OUTPUT_COLUMNS})


def write_json(rows: List[Dict[str, Any]], path: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=2, ensure_ascii=False)


def collect_candidate_repos(token: str | None, max_pages: int = 1, per_keyword: int = 30, sleep: float = 0.2) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for keyword in SEARCH_KEYWORDS:
        for item in search_repositories(keyword, token, page_size=per_keyword, max_pages=max_pages, sleep=sleep):
            if repo_matches_filter(item.get("repo_name") or "", item.get("description"), item.get("language"), FILTER_TERMS):
                results.append(item)
    return deduplicate_repos(results)


def enrich_repositories(rows: List[Dict[str, Any]], token: str | None, sleep: float = 0.2) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        full_name = row.get("full_name")
        print(f"[{idx}/{len(rows)}] Enriching: {full_name}")
        meta = get_repo_metadata(full_name, token)
        docs = build_documentation_flags(full_name, token)
        merged = {
            "repo_name": meta.get("repo_name") or row.get("repo_name"),
            "full_name": meta.get("full_name") or full_name,
            "repo_url": meta.get("repo_url") or row.get("repo_url"),
            "description": meta.get("description") or row.get("description"),
            "language": meta.get("language") or row.get("language"),
            "stars": meta.get("stars", row.get("stars", 0)),
            "forks": meta.get("forks", row.get("forks", 0)),
            "contributors_count": meta.get("contributors_count"),
            "created_at": meta.get("created_at"),
            "repo_age_days": meta.get("repo_age_days"),
            "pull_requests_count": meta.get("pull_requests_count"),
            "issues_count": meta.get("issues_count"),
            "open_issues_count": meta.get("open_issues_count"),
            "releases_count": meta.get("releases_count"),
            "commits_count": meta.get("commits_count"),
            "total_md_files": docs.get("total_md_files", 0),
            "has_readme": docs.get("has_readme", False),
            "has_security": docs.get("has_security", False),
            "has_contributing": docs.get("has_contributing", False),
            "has_skill": docs.get("has_skill", False),
            "has_agents": docs.get("has_agents", False),
            "last_updated_at": meta.get("last_updated_at") or row.get("last_updated_at"),
            "search_keyword": row.get("search_keyword"),
        }
        out.append(merged)
        if sleep > 0:
            time.sleep(sleep)
    return out


def to_output_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        out.append({
            "repo_name": row.get("repo_name", ""),
            "full_name": row.get("full_name", ""),
            "repo_url": row.get("repo_url", ""),
            "description": row.get("description", ""),
            "language": row.get("language", ""),
            "stars": row.get("stars", 0),
            "forks": row.get("forks", 0),
            "contributors_count": row.get("contributors_count", 0),
            "created_at": row.get("created_at", ""),
            "repo_age_days": row.get("repo_age_days", 0),
            "pull_requests_count": row.get("pull_requests_count", 0),
            "issues_count": row.get("issues_count", 0),
            "open_issues_count": row.get("open_issues_count", 0),
            "releases_count": row.get("releases_count", 0),
            "commits_count": row.get("commits_count", 0),
            "total_md_files": row.get("total_md_files", 0),
            "has_readme": 1 if row.get("has_readme") else 0,
            "has_security": 1 if row.get("has_security") else 0,
            "has_contributing": 1 if row.get("has_contributing") else 0,
            "has_skill": 1 if row.get("has_skill") else 0,
            "has_agents": 1 if row.get("has_agents") else 0,
            "last_updated_at": row.get("last_updated_at", ""),
            "search_keyword": row.get("search_keyword", ""),
        })
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect GitHub repos for agentic software maintainability exploration.")
    parser.add_argument("--output", type=str, default="agentic_repo_dataset.csv", help="Output path for CSV or JSON")
    parser.add_argument("--format", type=str, choices=["csv", "json"], default="csv", help="Output format")
    parser.add_argument("--per-keyword", type=int, default=30, help="Repositories per keyword to request from GitHub")
    parser.add_argument("--max-pages", type=int, default=1, help="Search result pages per keyword")
    parser.add_argument("--sleep", type=float, default=0.2, help="Delay between API calls")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = load_token()

    try:
        candidate_rows = collect_candidate_repos(
            token=token,
            max_pages=args.max_pages,
            per_keyword=args.per_keyword,
            sleep=args.sleep,
        )
    except GitHubRequestError as exc:
        print(f"Error: {exc}", file=os.sys.stderr)
        print("Tip: create a GitHub token at https://github.com/settings/tokens and export it as GITHUB_TOKEN or GH_TOKEN.", file=os.sys.stderr)
        return 1

    enriched_rows = enrich_repositories(candidate_rows, token=token, sleep=args.sleep)
    output_rows = to_output_rows(enriched_rows)

    if args.format == "csv":
        write_csv(output_rows, args.output)
        print(f"Saved {len(output_rows)} repositories to {args.output}")
    else:
        write_json(output_rows, args.output)
        print(f"Saved {len(output_rows)} repositories to {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
