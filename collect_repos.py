#!/usr/bin/env python3
"""
Single-stage GitHub repository fetcher for AI/agent keywords.

This version removes primary/secondary filtering and uses one optional
post-filter list of terms.

Output file default:
  repo_search_results.json

Optional:
  Set GITHUB_TOKEN in environment or .env for higher GitHub API rate limits.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


KEYWORDS = [
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

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
GITHUB_API_ROOT = "https://api.github.com"


@dataclass
class RepoResult:
    keyword: str
    full_name: str
    name: str
    html_url: str
    description: str | None
    stargazers_count: int
    forks_count: int
    language: str | None
    updated_at: str
    # Enriched metadata (populated by a follow-up round of API calls).
    created_at: str | None = None
    repo_age_days: int | None = None
    open_issues_count: int | None = None
    watchers_count: int | None = None
    subscribers_count: int | None = None
    contributors_count: int | None = None
    releases_count: int | None = None
    commits_count: int | None = None
    pull_requests_count: int | None = None
    issues_count: int | None = None


class GitHubSearchError(Exception):
    pass


class GitHubAuthError(GitHubSearchError):
    pass


class GitHubNotFoundError(GitHubSearchError):
    pass


def load_dotenv(dotenv_path: str = ".env") -> None:
    if not os.path.exists(dotenv_path):
        return

    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError as exc:
        print(f"Warning: could not read {dotenv_path}: {exc}", file=sys.stderr)


def github_request(url: str, token: str | None) -> dict:
    data, _headers = github_request_with_headers(url, token)
    return data


def github_request_with_headers(
    url: str, token: str | None
) -> Tuple[dict, Dict[str, str]]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "fetch-repo",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url=url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = resp.read().decode("utf-8")
            resp_headers = dict(resp.headers.items())
            return json.loads(payload), resp_headers
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        if exc.code == 401:
            raise GitHubAuthError(f"GitHub API HTTP 401: {details}") from exc
        if exc.code == 404:
            raise GitHubNotFoundError(f"GitHub API HTTP 404: {details}") from exc
        raise GitHubSearchError(f"GitHub API HTTP {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise GitHubSearchError(f"Network error: {exc}") from exc


_LAST_PAGE_RE = re.compile(r'[?&]page=(\d+)[^>]*>;\s*rel="last"')


def _count_via_last_page(url: str, token: str | None) -> Optional[int]:
    """Get a total count from a paginated list endpoint using per_page=1
    and the `Link: rel="last"` header, which avoids downloading every page.
    """
    paged_url = f"{url}{'&' if '?' in url else '?'}per_page=1"
    try:
        data, headers = github_request_with_headers(paged_url, token)
    except GitHubNotFoundError:
        return None
    except GitHubSearchError:
        return None

    link_header = headers.get("Link") or headers.get("link")
    if link_header:
        match = _LAST_PAGE_RE.search(link_header)
        if match:
            return int(match.group(1))

    # No pagination needed: 0 or 1 items total.
    if isinstance(data, list):
        return len(data)
    return None


def fetch_repo_details(full_name: str, token: str | None) -> Optional[dict]:
    url = f"{GITHUB_API_ROOT}/repos/{full_name}"
    try:
        return github_request(url, token)
    except GitHubNotFoundError:
        return None


def fetch_search_total_count(query: str, token: str | None) -> Optional[int]:
    url = f"{GITHUB_API_ROOT}/search/issues?{urllib.parse.urlencode({'q': query, 'per_page': 1})}"
    try:
        data = github_request(url, token)
    except GitHubSearchError:
        return None
    return data.get("total_count")


def compute_repo_age_days(created_at: str | None) -> Optional[int]:
    if not created_at:
        return None
    try:
        created = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - created).days


def enrich_repo(
    repo: RepoResult,
    token: str | None,
    delay_seconds: float,
) -> RepoResult:
    """Populate contributors/releases/commits/PRs/issues/age metadata for a
    single repository via several follow-up GitHub API calls.
    """
    details = fetch_repo_details(repo.full_name, token)
    if delay_seconds > 0:
        time.sleep(delay_seconds)

    if details:
        repo.created_at = details.get("created_at")
        repo.open_issues_count = details.get("open_issues_count")
        repo.watchers_count = details.get("subscribers_count", details.get("watchers_count"))
        repo.subscribers_count = details.get("subscribers_count")
        repo.stargazers_count = details.get("stargazers_count", repo.stargazers_count)
        repo.forks_count = details.get("forks_count", repo.forks_count)
        repo.repo_age_days = compute_repo_age_days(repo.created_at)

    repo.contributors_count = _count_via_last_page(
        f"{GITHUB_API_ROOT}/repos/{repo.full_name}/contributors?anon=true", token
    )
    if delay_seconds > 0:
        time.sleep(delay_seconds)

    repo.releases_count = _count_via_last_page(
        f"{GITHUB_API_ROOT}/repos/{repo.full_name}/releases", token
    )
    if delay_seconds > 0:
        time.sleep(delay_seconds)

    repo.commits_count = _count_via_last_page(
        f"{GITHUB_API_ROOT}/repos/{repo.full_name}/commits", token
    )
    if delay_seconds > 0:
        time.sleep(delay_seconds)

    repo.pull_requests_count = fetch_search_total_count(
        f"repo:{repo.full_name} is:pr", token
    )
    if delay_seconds > 0:
        time.sleep(delay_seconds)

    repo.issues_count = fetch_search_total_count(
        f"repo:{repo.full_name} is:issue", token
    )
    if delay_seconds > 0:
        time.sleep(delay_seconds)

    return repo


def search_repositories_for_keyword(
    keyword: str,
    token: str | None,
    per_page: int,
    max_pages: int,
    sort: str,
    order: str,
    delay_seconds: float,
) -> List[RepoResult]:
    all_results: List[RepoResult] = []

    for page in range(1, max_pages + 1):
        query_params = {
            "q": keyword,
            "sort": sort,
            "order": order,
            "per_page": per_page,
            "page": page,
        }
        url = f"{GITHUB_SEARCH_URL}?{urllib.parse.urlencode(query_params)}"

        data = github_request(url, token)
        items = data.get("items", [])
        if not items:
            break

        for repo in items:
            all_results.append(
                RepoResult(
                    keyword=keyword,
                    full_name=repo.get("full_name", ""),
                    name=repo.get("name", ""),
                    html_url=repo.get("html_url", ""),
                    description=repo.get("description"),
                    stargazers_count=repo.get("stargazers_count", 0),
                    forks_count=repo.get("forks_count", 0),
                    language=repo.get("language"),
                    updated_at=repo.get("updated_at", ""),
                )
            )

        if delay_seconds > 0:
            time.sleep(delay_seconds)

    return all_results


def deduplicate_by_full_name(results: List[RepoResult]) -> List[RepoResult]:
    deduped: Dict[str, RepoResult] = {}
    for item in results:
        existing = deduped.get(item.full_name)
        if existing is None or item.stargazers_count > existing.stargazers_count:
            deduped[item.full_name] = item

    return sorted(deduped.values(), key=lambda x: x.stargazers_count, reverse=True)


def parse_terms_csv(raw: str) -> List[str]:
    return [term.strip().lower() for term in raw.split(",") if term.strip()]


def repo_search_text(repo: RepoResult) -> str:
    return " ".join([
        repo.name,
        repo.full_name,
        repo.description or "",
        repo.language or "",
    ]).lower()


def matched_terms(text: str, terms: List[str]) -> List[str]:
    return [term for term in terms if term in text]


def single_stage_filter(
    repos: List[RepoResult],
    terms: List[str],
    min_matches: int,
) -> List[RepoResult]:
    if not terms:
        return repos

    passed: List[RepoResult] = []
    for repo in repos:
        text = repo_search_text(repo)
        matches = matched_terms(text, terms)
        if len(matches) >= min_matches:
            passed.append(repo)

    return passed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch GitHub repositories with a single-stage filter pipeline."
    )
    parser.add_argument("--per-keyword", type=int, default=30)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument(
        "--sort",
        default="stars",
        choices=["stars", "forks", "help-wanted-issues", "updated"],
    )
    parser.add_argument("--order", default="desc", choices=["asc", "desc"])
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--output", default="repo_search_results.json")
    parser.add_argument("--print-top", type=int, default=15)
    parser.add_argument(
        "--disable-filter",
        action="store_true",
        help="Skip single-stage post-filter and keep all unique repos.",
    )
    parser.add_argument(
        "--filter-terms",
        default="agent,assistant,ai,llm,autonomous,agentic,automation,personal",
        help="Comma-separated terms for the single-stage filter.",
    )
    parser.add_argument(
        "--min-matches",
        type=int,
        default=1,
        help="Minimum number of matched filter terms to keep a repo.",
    )
    parser.add_argument(
        "--no-enrich",
        action="store_true",
        help="Skip fetching extra metadata (stars/forks are still included).",
    )
    parser.add_argument(
        "--enrich-delay",
        type=float,
        default=0.3,
        help="Seconds to sleep between enrichment API calls (avoids rate limits).",
    )
    parser.add_argument(
        "--force-reenrich",
        action="store_true",
        help="Re-fetch enrichment metadata even for repos already cached in --output.",
    )
    return parser.parse_args()


def load_cached_enrichment(output_path: str) -> Dict[str, dict]:
    """Load previously enriched repo data from an existing output file, keyed
    by full_name, so re-runs don't need to re-fetch unchanged metadata.
    """
    if not os.path.exists(output_path):
        return {}
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

    cache: Dict[str, dict] = {}
    for repo in payload.get("repositories", []):
        full_name = repo.get("full_name")
        if full_name and repo.get("contributors_count") is not None:
            cache[full_name] = repo
    return cache


def main() -> int:
    load_dotenv()
    args = parse_args()

    if args.per_keyword < 1 or args.per_keyword > 100:
        print("--per-keyword must be between 1 and 100", file=sys.stderr)
        return 2
    if args.min_matches < 1:
        print("--min-matches must be >= 1", file=sys.stderr)
        return 2

    token = os.getenv("GITHUB_TOKEN")
    token_disabled = False
    all_results: List[RepoResult] = []

    for idx, keyword in enumerate(KEYWORDS, start=1):
        print(f"[{idx}/{len(KEYWORDS)}] Searching: {keyword}")
        try:
            results = search_repositories_for_keyword(
                keyword=keyword,
                token=token,
                per_page=args.per_keyword,
                max_pages=args.max_pages,
                sort=args.sort,
                order=args.order,
                delay_seconds=args.delay,
            )
            all_results.extend(results)
        except GitHubAuthError as exc:
            if token and not token_disabled:
                print(
                    "Warning: GITHUB_TOKEN is invalid. Retrying without token "
                    "(lower rate limits apply).",
                    file=sys.stderr,
                )
                token = None
                token_disabled = True
                try:
                    results = search_repositories_for_keyword(
                        keyword=keyword,
                        token=token,
                        per_page=args.per_keyword,
                        max_pages=args.max_pages,
                        sort=args.sort,
                        order=args.order,
                        delay_seconds=args.delay,
                    )
                    all_results.extend(results)
                except GitHubSearchError as retry_exc:
                    print(
                        f"Error for keyword '{keyword}' after retry: {retry_exc}",
                        file=sys.stderr,
                    )
            else:
                print(f"Error for keyword '{keyword}': {exc}", file=sys.stderr)
        except GitHubSearchError as exc:
            print(f"Error for keyword '{keyword}': {exc}", file=sys.stderr)

    deduped = deduplicate_by_full_name(all_results)
    filter_terms = parse_terms_csv(args.filter_terms)

    if args.disable_filter:
        final_repos = deduped
    else:
        final_repos = single_stage_filter(
            repos=deduped,
            terms=filter_terms,
            min_matches=args.min_matches,
        )

    if not args.no_enrich:
        cache = {} if args.force_reenrich else load_cached_enrichment(args.output)
        total = len(final_repos)
        for idx, repo in enumerate(final_repos, start=1):
            cached = cache.get(repo.full_name)
            if cached and cached.get("updated_at") == repo.updated_at:
                repo.created_at = cached.get("created_at")
                repo.repo_age_days = cached.get("repo_age_days")
                repo.open_issues_count = cached.get("open_issues_count")
                repo.watchers_count = cached.get("watchers_count")
                repo.subscribers_count = cached.get("subscribers_count")
                repo.contributors_count = cached.get("contributors_count")
                repo.releases_count = cached.get("releases_count")
                repo.commits_count = cached.get("commits_count")
                repo.pull_requests_count = cached.get("pull_requests_count")
                repo.issues_count = cached.get("issues_count")
                print(f"[{idx}/{total}] Cached: {repo.full_name}")
                continue

            print(f"[{idx}/{total}] Enriching: {repo.full_name}")
            try:
                enrich_repo(repo, token, args.enrich_delay)
            except GitHubAuthError as exc:
                print(
                    "Warning: GITHUB_TOKEN became invalid during enrichment; "
                    "continuing without a token (lower rate limits apply).",
                    file=sys.stderr,
                )
                token = None
            except GitHubSearchError as exc:
                print(
                    f"Warning: enrichment failed for '{repo.full_name}': {exc}",
                    file=sys.stderr,
                )

    output_payload = {
        "keywords": KEYWORDS,
        "total_raw_results": len(all_results),
        "total_unique_repositories": len(deduped),
        "total_filtered_repositories": len(final_repos),
        "filter": {
            "enabled": not args.disable_filter,
            "terms": filter_terms,
            "min_matches": args.min_matches,
        },
        "repositories": [asdict(item) for item in final_repos],
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2, ensure_ascii=False)

    print(
        f"Saved {len(final_repos)} repositories to {args.output} "
        f"(unique={len(deduped)})"
    )

    top_n = max(0, args.print_top)
    if top_n:
        print("\nTop repositories:")
        for i, repo in enumerate(final_repos[:top_n], start=1):
            print(
                f"{i:2d}. {repo.full_name} | ⭐ {repo.stargazers_count} | "
                f"{repo.language or 'N/A'} | {repo.html_url}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
