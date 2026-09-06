#!/usr/bin/env python3
"""Export documentation files from GitHub repositories marked Suggested=Y to JSONL.

The input CSV is expected to contain a ``Suggested`` column and a GitHub URL in
``Repo_URL`` (the column names can be changed with command-line options).  The
script walks each repository's *entire* ``main`` Git tree (or ``master`` when
``main`` is absent), so files in
documentation folders and other nested directories are included.

Examples:
    python pull_documentation_files.py
    python pull_documentation_files.py --input manual_review.csv
    python pull_documentation_files.py --extensions .md,.rst,.adoc
    python pull_documentation_files.py --dry-run

Set GITHUB_TOKEN in the environment or a local .env file to receive GitHub's
higher API rate limit for repository-tree scans. File contents are retrieved
from GitHub's raw-file host, avoiding one API request per documentation file.
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
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, TypeVar


API_ROOT = "https://api.github.com"
DEFAULT_EXTENSIONS = (
    ".md",
    ".mdx",
    ".markdown",
    ".rst",
    ".adoc",
    ".asciidoc",
    ".txt",
)
T = TypeVar("T")


class GitHubApiError(RuntimeError):
    """An error response returned by the GitHub API."""

    def __init__(self, status: int, details: str) -> None:
        super().__init__(f"GitHub API HTTP {status}: {details}")
        self.status = status


@dataclass(frozen=True)
class Repository:
    full_name: str
    url: str


def load_dotenv(path: Path) -> None:
    """Load simple KEY=value entries without replacing existing environment values."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


def github_json(url: str, token: str | None) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "suggested-repository-documentation-collector",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise GitHubApiError(exc.code, details) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GitHub network error: {exc}") from exc


def retry_without_invalid_token(
    request: Callable[[str | None], T], token: str | None
) -> tuple[T, str | None, bool]:
    """Retry once anonymously when GitHub rejects the configured token."""
    try:
        return request(token), token, False
    except GitHubApiError as exc:
        if exc.status != 401 or not token:
            raise
        return request(None), None, True


def parse_extensions(raw: str | tuple[str, ...]) -> set[str]:
    values = raw.split(",") if isinstance(raw, str) else raw
    extensions = {
        extension.strip().lower() if extension.strip().startswith(".") else f".{extension.strip().lower()}"
        for extension in values
        if extension.strip()
    }
    if not extensions:
        raise ValueError("--extensions must contain at least one extension")
    return extensions


def github_full_name(url: str) -> str | None:
    """Return owner/repository for a standard github.com repository URL."""
    parsed = urllib.parse.urlparse(url.strip())
    if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        return None
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 2:
        return None
    return f"{parts[0]}/{parts[1].removesuffix('.git')}"


def selected_repositories(
    input_path: Path, suggested_column: str, url_column: str
) -> list[Repository]:
    with input_path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames:
            raise ValueError("input CSV has no header row")
        missing = {suggested_column, url_column}.difference(reader.fieldnames)
        if missing:
            raise ValueError(f"input CSV is missing column(s): {', '.join(sorted(missing))}")

        repos: dict[str, Repository] = {}
        for row_number, row in enumerate(reader, start=2):
            if row.get(suggested_column, "").strip().upper() != "Y":
                continue
            repo_url = row.get(url_column, "").strip()
            full_name = github_full_name(repo_url)
            if not full_name:
                print(
                    f"Warning: skipping row {row_number}; {url_column} is not a GitHub repository URL: {repo_url!r}",
                    file=sys.stderr,
                )
                continue
            repos.setdefault(full_name.lower(), Repository(full_name=full_name, url=repo_url))
    return list(repos.values())


def repository_tree(full_name: str, token: str | None) -> tuple[str, list[dict[str, Any]], bool]:
    """Return the full tree from main, falling back to master when necessary."""
    encoded_name = urllib.parse.quote(full_name, safe="/")
    for branch_name in ("main", "master"):
        branch = urllib.parse.quote(branch_name, safe="")
        try:
            tree = github_json(
                f"{API_ROOT}/repos/{encoded_name}/git/trees/{branch}?recursive=1", token
            )
        except GitHubApiError as exc:
            if exc.status == 404:
                continue
            raise
        return branch_name, tree.get("tree", []), bool(tree.get("truncated", False))
    raise RuntimeError("repository has neither a main nor a master branch")


def is_safe_repository_path(path: str) -> bool:
    """Reject invalid Git tree paths before including them in output records."""
    pure_path = PurePosixPath(path)
    return bool(path) and not pure_path.is_absolute() and ".." not in pure_path.parts


def documentation_blobs(tree: list[dict[str, Any]], extensions: set[str]) -> list[dict[str, Any]]:
    return [
        item
        for item in tree
        if item.get("type") == "blob"
        and not str(item.get("mode", "")).startswith("120000")  # Git symlink
        and is_safe_repository_path(str(item.get("path", "")))
        and PurePosixPath(str(item["path"])).suffix.lower() in extensions
    ]


def raw_file_bytes(full_name: str, branch: str, path: str) -> bytes:
    """Download public file content without consuming GitHub REST API quota."""
    owner, repository = full_name.split("/", 1)
    raw_url = (
        "https://raw.githubusercontent.com/"
        f"{urllib.parse.quote(owner, safe='')}/"
        f"{urllib.parse.quote(repository, safe='')}/"
        f"{urllib.parse.quote(branch, safe='')}/"
        f"{urllib.parse.quote(path, safe='/')}"
    )
    request = urllib.request.Request(
        raw_url,
        headers={"User-Agent": "suggested-repository-documentation-collector"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"raw GitHub HTTP {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"raw GitHub network error: {exc}") from exc


def existing_record_keys(path: Path) -> set[tuple[str, str, str, str]]:
    """Return source identifiers already present in a valid JSONL output file."""
    keys: set[tuple[str, str, str, str]] = set()
    with path.open(encoding="utf-8") as jsonl_file:
        for line_number, line in enumerate(jsonl_file, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                key = (
                    str(record["repository"]),
                    str(record["branch"]),
                    str(record["path"]),
                    str(record["sha"]),
                )
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                raise ValueError(f"invalid JSONL record on line {line_number}") from exc
            keys.add(key)
    return keys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="manual_review.csv", help="CSV containing the Suggested column.")
    parser.add_argument("--output", default="documentation_files.jsonl", help="JSONL file to create.")
    parser.add_argument("--suggested-column", default="Suggested")
    parser.add_argument("--url-column", default="Repo_URL")
    parser.add_argument("--extensions", default=DEFAULT_EXTENSIONS, help="Comma-separated extensions to download.")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing --output file.")
    parser.add_argument("--resume", action="store_true", help="Append only files not already in an existing --output JSONL file.")
    parser.add_argument("--dry-run", action="store_true", help="List matching files without downloading them.")
    parser.add_argument("--delay", type=float, default=0.05, help="Seconds to wait after each API request (default: 0.05).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.delay < 0:
        print("--delay must be non-negative", file=sys.stderr)
        return 2
    if args.overwrite and args.resume:
        print("--overwrite and --resume cannot be used together", file=sys.stderr)
        return 2
    try:
        extensions = parse_extensions(args.extensions)
        repositories = selected_repositories(Path(args.input), args.suggested_column, args.url_column)
    except (OSError, ValueError, csv.Error) as exc:
        print(f"Error reading input: {exc}", file=sys.stderr)
        return 2

    load_dotenv(Path(".env"))
    token = os.getenv("GITHUB_TOKEN")
    output_path = Path(args.output)
    if not args.dry_run and output_path.exists() and not (args.overwrite or args.resume):
        print(
            f"Error: output file already exists: {output_path}. Use --overwrite to replace it.",
            file=sys.stderr,
        )
        return 2
    if not args.dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        known_record_keys = existing_record_keys(output_path) if args.resume else set()
    except (OSError, ValueError) as exc:
        print(f"Error reading existing output: {exc}", file=sys.stderr)
        return 2

    print(f"Selected {len(repositories)} repository/repositories with {args.suggested_column}=Y.")
    print(f"Documentation extensions: {', '.join(sorted(extensions))}")
    if args.resume:
        print(f"Resuming with {len(known_record_keys)} existing documentation record(s).")
    written = skipped_existing = failed = 0

    output_mode = "a" if args.resume else "w"
    with (output_path.open(output_mode, encoding="utf-8") if not args.dry_run else open(os.devnull, "w", encoding="utf-8")) as jsonl_file:
        for repo_index, repository in enumerate(repositories, start=1):
            print(f"[{repo_index}/{len(repositories)}] Scanning {repository.full_name}")
            try:
                (branch, tree, truncated), token, retried_anonymously = retry_without_invalid_token(
                    lambda current_token: repository_tree(repository.full_name, current_token), token
                )
                if retried_anonymously:
                    print(
                        "Warning: GITHUB_TOKEN was rejected; continuing without it "
                        "(GitHub's anonymous rate limit is lower).",
                        file=sys.stderr,
                    )
                if truncated:
                    print(f"Warning: {repository.full_name}'s Git tree was truncated; results may be incomplete.", file=sys.stderr)
                matches = documentation_blobs(tree, extensions)
            except (GitHubApiError, RuntimeError) as exc:
                failed += 1
                print(f"Warning: could not scan {repository.full_name}: {exc}", file=sys.stderr)
                continue

            print(f"  Found {len(matches)} documentation file(s).")
            for item in matches:
                relative_path = str(item["path"])
                sha = str(item.get("sha", ""))
                record_key = (repository.full_name, branch, relative_path, sha)
                if args.dry_run:
                    print(f"  {relative_path}")
                    continue
                if record_key in known_record_keys:
                    skipped_existing += 1
                    continue
                try:
                    content = raw_file_bytes(repository.full_name, branch, relative_path)
                    record = {
                        "repository": repository.full_name,
                        "repository_url": repository.url,
                        "branch": branch,
                        "path": relative_path,
                        "sha": sha,
                        "content": content.decode("utf-8", errors="replace"),
                    }
                    jsonl_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                    known_record_keys.add(record_key)
                    written += 1
                except (GitHubApiError, RuntimeError, OSError) as exc:
                    failed += 1
                    print(f"Warning: could not download {repository.full_name}/{relative_path}: {exc}", file=sys.stderr)
                if args.delay:
                    time.sleep(args.delay)

    if not args.dry_run:
        print(f"Wrote {written} documentation record(s) to {output_path}")
    print(f"Done: written={written}, skipped_existing={skipped_existing}, failed={failed}.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
