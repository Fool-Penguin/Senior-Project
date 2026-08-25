#!/usr/bin/env python3
"""
Single-stage GitHub repository fetcher for AI/agent keywords.

This version removes primary/secondary filtering and uses one optional
post-filter list of terms.

Output file default:
  github_repos.json

Optional:
  Set GITHUB_TOKEN in environment or .env for higher GitHub API rate limits.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Dict, List


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


class GitHubSearchError(Exception):
    pass


class GitHubAuthError(GitHubSearchError):
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
            return json.loads(payload)
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        if exc.code == 401:
            raise GitHubAuthError(f"GitHub API HTTP 401: {details}") from exc
        raise GitHubSearchError(f"GitHub API HTTP {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise GitHubSearchError(f"Network error: {exc}") from exc


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
    parser.add_argument("--output", default="github_repos.json")
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
    return parser.parse_args()


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
