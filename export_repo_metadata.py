#!/usr/bin/env python3
"""Export GitHub repository search results to a metadata CSV report.

Besides fields already present in the JSON, this script can inspect each
repository's Git tree to count Markdown files and detect standard repository
guidance files.  Set GITHUB_TOKEN (or place it in .env) to avoid GitHub's low
unauthenticated API rate limit.

Examples:
    python export_repo_metadata.py
    python export_repo_metadata.py --output repositories.csv
    python export_repo_metadata.py --skip-file-metadata
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


COLUMNS = [
    "Repo_Name",
    "Repo_URL",
    "Stars",
    "Forks",
    "contributors_count",
    "create_date",
    "repo_age_days",
    "PRs",
    "Issues",
    "Total_MD_Files",
    "Has_SECURITY",
    "Has_CONTRIBUTING",
    "Has_SKILL",
    "Has_AGENTS",
]

API_ROOT = "https://api.github.com"
GUIDANCE_FILES = {
    "SECURITY.md": "Has_SECURITY",
    "CONTRIBUTING.md": "Has_CONTRIBUTING",
    "SKILL.md": "Has_SKILL",
    "AGENTS.md": "Has_AGENTS",
}


class GitHubApiError(RuntimeError):
    """A GitHub API error with its HTTP status code."""

    def __init__(self, status: int, details: str) -> None:
        super().__init__(f"GitHub API HTTP {status}: {details}")
        self.status = status


def load_dotenv(path: Path) -> None:
    """Read GITHUB_TOKEN from a simple local .env file if necessary."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def github_json(url: str, token: str | None) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "github-repos-csv-exporter",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise GitHubApiError(exc.code, details) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GitHub network error: {exc}") from exc


def load_cache(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(path: Path, cache: dict[str, dict[str, Any]]) -> None:
    path.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def inspect_repository_files(
    full_name: str, token: str | None
) -> dict[str, Any]:
    """Return Markdown and guidance-file metrics for the default branch."""
    repo_url = f"{API_ROOT}/repos/{urllib.parse.quote(full_name, safe='/')}"
    repo_details = github_json(repo_url, token)
    default_branch = repo_details.get("default_branch")
    if not default_branch:
        raise RuntimeError("repository has no default branch")

    branch = urllib.parse.quote(default_branch, safe="")
    tree_url = (
        f"{repo_url}/git/trees/{branch}?"
        + urllib.parse.urlencode({"recursive": "1"})
    )
    tree_data = github_json(tree_url, token)
    paths = [
        item.get("path", "")
        for item in tree_data.get("tree", [])
        if item.get("type") == "blob"
    ]
    names = {Path(path).name.upper() for path in paths}

    result: dict[str, Any] = {
        "Total_MD_Files": sum(path.lower().endswith(".md") for path in paths),
        "tree_truncated": bool(tree_data.get("truncated", False)),
    }
    result.update(
        {column: filename.upper() in names for filename, column in GUIDANCE_FILES.items()}
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default="repo_search_results.json",
        help="Input repository-search JSON file.",
    )
    parser.add_argument(
        "--output",
        default="repo_metadata.csv",
        help="Output repository-metadata CSV file.",
    )
    parser.add_argument(
        "--cache",
        default="repo_file_metadata_cache.json",
        help="Cache for GitHub file-metadata requests.",
    )
    parser.add_argument(
        "--skip-file-metadata",
        action="store_true",
        help="Do not call GitHub; leave Markdown and guidance-file fields empty.",
    )
    parser.add_argument(
        "--refresh-file-metadata",
        action="store_true",
        help="Ignore cached file metadata and query GitHub again.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.1,
        help="Seconds to wait after each repository inspection (default: 0.1).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.delay < 0:
        print("--delay must be non-negative", file=sys.stderr)
        return 2

    input_path = Path(args.input)
    output_path = Path(args.output)
    cache_path = Path(args.cache)
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        repositories = payload["repositories"]
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"Could not read repositories from {input_path}: {exc}", file=sys.stderr)
        return 2

    load_dotenv(Path(".env"))
    token = os.getenv("GITHUB_TOKEN")
    cache = load_cache(cache_path)
    rows: list[dict[str, Any]] = []
    failed_inspections = 0

    for index, repo in enumerate(repositories, start=1):
        full_name = repo.get("full_name") or repo.get("name", "")
        file_metrics: dict[str, Any] = {}
        if not args.skip_file_metadata and full_name:
            if not args.refresh_file_metadata and full_name in cache:
                file_metrics = cache[full_name]
                print(f"[{index}/{len(repositories)}] Cached: {full_name}")
            else:
                print(f"[{index}/{len(repositories)}] Inspecting: {full_name}")
                try:
                    file_metrics = inspect_repository_files(full_name, token)
                    cache[full_name] = file_metrics
                    save_cache(cache_path, cache)
                    if file_metrics["tree_truncated"]:
                        print(
                            f"Warning: {full_name}'s Git tree was truncated; "
                            "its Markdown count may be incomplete.",
                            file=sys.stderr,
                        )
                except GitHubApiError as exc:
                    if exc.status == 401 and token:
                        print(
                            "Warning: GITHUB_TOKEN is invalid; retrying without "
                            "a token (GitHub's anonymous rate limit is much lower).",
                            file=sys.stderr,
                        )
                        token = None
                        try:
                            file_metrics = inspect_repository_files(full_name, token)
                            cache[full_name] = file_metrics
                            save_cache(cache_path, cache)
                        except RuntimeError as retry_exc:
                            failed_inspections += 1
                            print(
                                f"Warning: could not inspect {full_name}: {retry_exc}",
                                file=sys.stderr,
                            )
                    else:
                        failed_inspections += 1
                        print(f"Warning: could not inspect {full_name}: {exc}", file=sys.stderr)
                except RuntimeError as exc:
                    failed_inspections += 1
                    print(f"Warning: could not inspect {full_name}: {exc}", file=sys.stderr)
                if args.delay:
                    time.sleep(args.delay)

        rows.append(
            {
                "Repo_Name": repo.get("name", ""),
                "Repo_URL": repo.get("html_url", ""),
                "Stars": repo.get("stargazers_count", ""),
                "Forks": repo.get("forks_count", ""),
                "contributors_count": repo.get("contributors_count", ""),
                "create_date": repo.get("created_at", ""),
                "repo_age_days": repo.get("repo_age_days", ""),
                "PRs": repo.get("pull_requests_count", ""),
                "Issues": repo.get("issues_count", ""),
                "Total_MD_Files": file_metrics.get("Total_MD_Files", ""),
                "Has_SECURITY": file_metrics.get("Has_SECURITY", ""),
                "Has_CONTRIBUTING": file_metrics.get("Has_CONTRIBUTING", ""),
                "Has_SKILL": file_metrics.get("Has_SKILL", ""),
                "Has_AGENTS": file_metrics.get("Has_AGENTS", ""),
            }
        )

    with output_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} repositories to {output_path}")
    if failed_inspections:
        print(f"File metadata could not be fetched for {failed_inspections} repositories.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
