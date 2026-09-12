#!/usr/bin/env python3
"""Collect current documentation files from GitHub repositories into JSONL.

The collector reads GitHub repository URLs from a CSV, shallow-clones one
repository at a time, scans the entire checked-out default branch for
documentation files, writes their content to JSONL, then deletes the clone
before moving on to the next repository.

Examples:
    python pull_documentation_files.py --overwrite
    python pull_documentation_files.py --resume
    python pull_documentation_files.py --extensions .md,.rst,.adoc
    python pull_documentation_files.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


DEFAULT_EXTENSIONS = (
    ".md",
    ".mdx",
    ".markdown",
    ".rst",
    ".adoc",
    ".asciidoc",
    ".txt",
)


class GitCommandError(RuntimeError):
    """A local Git command failed."""


@dataclass(frozen=True)
class Repository:
    full_name: str
    url: str


class ProgressReporter:
    """Render live terminal progress without requiring a third-party package."""

    def __init__(self, total: int) -> None:
        self.total = total
        self.interactive = sys.stdout.isatty()
        self.active = False

    def update(self, current: int, status: str, *, log_when_not_interactive: bool = True) -> None:
        """Show the current repository and activity; avoid noisy redirected output."""
        completed = max(0, min(current - 1, self.total))
        fraction = completed / self.total if self.total else 1.0
        width = 24
        filled = round(width * fraction)
        bar = f"{'#' * filled}{'-' * (width - filled)}"
        status = status.replace("\n", " ")[:100]
        message = f"[{bar}] {completed}/{self.total} repositories ({fraction:.0%}) | {status}"
        if self.interactive:
            print(f"\r{message:<160}", end="", flush=True)
            self.active = True
        elif log_when_not_interactive:
            print(message, flush=True)

    def line_break(self) -> None:
        """End a live progress line before a normal log message is printed."""
        if self.active:
            print(flush=True)
            self.active = False


def parse_extensions(raw: str | tuple[str, ...]) -> set[str]:
    values = raw.split(",") if isinstance(raw, str) else raw
    extensions = {
        extension.strip().lower()
        if extension.strip().startswith(".")
        else f".{extension.strip().lower()}"
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


def selected_repositories(input_path: Path, url_column: str) -> list[Repository]:
    """Load every unique GitHub repository from the input CSV."""
    with input_path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames:
            raise ValueError("input CSV has no header row")
        if url_column not in reader.fieldnames:
            raise ValueError(f"input CSV is missing column: {url_column}")

        repos: dict[str, Repository] = {}
        for row_number, row in enumerate(reader, start=2):
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


def git_output(arguments: list[str], *, timeout: float) -> str:
    """Run Git and return stdout, with useful failures for clone diagnostics."""
    try:
        result = subprocess.run(
            ["git", *arguments],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise GitCommandError("Git is not installed or is not available on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitCommandError(f"Git command timed out after {timeout:g} seconds") from exc

    if result.returncode:
        details = result.stderr.strip() or result.stdout.strip() or "no error details returned"
        raise GitCommandError(details)
    return result.stdout.strip()


def clone_default_branch(repository: Repository, clone_path: Path, timeout: float) -> tuple[str, str]:
    """Shallow-clone Git's configured default branch and return branch and commit SHA."""
    git_output(
        [
            "clone",
            "--depth",
            "1",
            "--single-branch",
            "--no-tags",
            "--quiet",
            repository.url,
            os.fspath(clone_path),
        ],
        timeout=timeout,
    )
    branch = git_output(["-C", os.fspath(clone_path), "branch", "--show-current"], timeout=timeout)
    if not branch:
        raise GitCommandError("clone did not check out a named default branch")
    sha = git_output(["-C", os.fspath(clone_path), "rev-parse", "HEAD"], timeout=timeout)
    return branch, sha


def is_safe_repository_path(path: str) -> bool:
    """Reject invalid local relative paths before including them in output records."""
    pure_path = PurePosixPath(path)
    return bool(path) and not pure_path.is_absolute() and ".." not in pure_path.parts


def documentation_files(repository_path: Path, extensions: set[str]) -> list[tuple[Path, str]]:
    """Find eligible regular files throughout the checkout, excluding Git metadata."""
    matches: list[tuple[Path, str]] = []
    for directory, child_directories, filenames in os.walk(repository_path, followlinks=False):
        child_directories[:] = [name for name in child_directories if name != ".git"]
        child_directories.sort()
        directory_path = Path(directory)
        for filename in sorted(filenames):
            file_path = directory_path / filename
            if file_path.is_symlink() or file_path.suffix.lower() not in extensions:
                continue
            relative_path = file_path.relative_to(repository_path).as_posix()
            if is_safe_repository_path(relative_path):
                matches.append((file_path, relative_path))
    return matches


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


def _remove_readonly_path(function: object, path: str, _exception_info: object) -> None:
    """Allow ``shutil.rmtree`` to retry read-only files on Windows."""
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        function(path)  # type: ignore[operator]
    except OSError:
        # The outer cleanup loop handles transient locks, such as a Git pack index
        # that Windows has not released yet.
        pass


def remove_temporary_repository(
    clone_path: Path, temporary_root: Path, cleanup_timeout: float
) -> None:
    """Delete exactly the current clone, retrying transient Windows file locks.

    A new clone is never started until this function has either removed the
    current one or raised an error after the configured timeout.
    """
    if not clone_path.exists():
        return
    resolved_root = temporary_root.resolve()
    resolved_clone = clone_path.resolve()
    try:
        resolved_clone.relative_to(resolved_root)
    except ValueError as exc:
        raise RuntimeError(f"refusing to delete clone outside temporary directory: {resolved_clone}") from exc
    if resolved_clone == resolved_root:
        raise RuntimeError("refusing to delete the temporary-directory root")

    deadline = time.monotonic() + cleanup_timeout
    attempt = 0
    last_error: OSError | None = None
    while clone_path.exists():
        try:
            shutil.rmtree(clone_path, onerror=_remove_readonly_path)
        except OSError as exc:
            last_error = exc

        if not clone_path.exists():
            return
        if time.monotonic() >= deadline:
            details = f": {last_error}" if last_error else ""
            raise OSError(
                f"timed out after {cleanup_timeout:g} seconds waiting to remove {clone_path}{details}"
            )

        # Antivirus and Windows file-handle release are normally short-lived.
        # Cap the wait so cleanup remains responsive while avoiding a tight loop.
        wait_seconds = min(0.1 * (2**attempt), 2.0, max(0.0, deadline - time.monotonic()))
        time.sleep(wait_seconds)
        attempt += 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default="Repos_Final_Sample.csv",
        help="CSV containing GitHub repository URLs (default: Repos_Final_Sample.csv).",
    )
    parser.add_argument("--output", default="documentation_files.jsonl", help="JSONL file to create.")
    parser.add_argument("--url-column", default="Repo_URL")
    parser.add_argument("--extensions", default=DEFAULT_EXTENSIONS, help="Comma-separated extensions to collect.")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing --output file.")
    parser.add_argument("--resume", action="store_true", help="Append only files not already in an existing --output JSONL file.")
    parser.add_argument("--dry-run", action="store_true", help="List matching files without writing output.")
    parser.add_argument(
        "--delay",
        type=float,
        default=0.1,
        help="Seconds to wait after cleaning up each repository clone (default: 0.1).",
    )
    parser.add_argument(
        "--clone-timeout",
        type=float,
        default=600.0,
        help="Maximum seconds allowed for each Git command (default: 600).",
    )
    parser.add_argument(
        "--cleanup-timeout",
        type=float,
        default=60.0,
        help="Maximum seconds to retry removal of a temporary clone (default: 60).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.delay < 0:
        print("--delay must be non-negative", file=sys.stderr)
        return 2
    if args.clone_timeout <= 0:
        print("--clone-timeout must be positive", file=sys.stderr)
        return 2
    if args.cleanup_timeout <= 0:
        print("--cleanup-timeout must be positive", file=sys.stderr)
        return 2
    if args.overwrite and args.resume:
        print("--overwrite and --resume cannot be used together", file=sys.stderr)
        return 2

    try:
        extensions = parse_extensions(args.extensions)
        repositories = selected_repositories(Path(args.input), args.url_column)
    except (OSError, ValueError, csv.Error) as exc:
        print(f"Error reading input: {exc}", file=sys.stderr)
        return 2

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

    print(f"Selected {len(repositories)} repository/repositories from the input CSV.")
    print(f"Documentation extensions: {', '.join(sorted(extensions))}")
    if args.resume:
        print(f"Resuming with {len(known_record_keys)} existing documentation record(s).")

    written = skipped_existing = failed = 0
    progress = ProgressReporter(len(repositories))
    output_mode = "a" if args.resume else "w"
    output_handle = output_path.open(output_mode, encoding="utf-8") if not args.dry_run else open(os.devnull, "w", encoding="utf-8")

    with output_handle as jsonl_file, tempfile.TemporaryDirectory(prefix="documentation-collector-") as temporary_root_string:
        temporary_root = Path(temporary_root_string)
        clone_path = temporary_root / "repository"

        for repo_index, repository in enumerate(repositories, start=1):
            cleanup_failed = False
            progress.update(repo_index, f"Cloning {repository.full_name} (shallow default branch)")
            try:
                branch, sha = clone_default_branch(repository, clone_path, args.clone_timeout)
                matches = documentation_files(clone_path, extensions)
                progress.update(
                    repo_index,
                    f"{repository.full_name}: found {len(matches)} documentation file(s) on {branch}",
                )

                for file_index, (file_path, relative_path) in enumerate(matches, start=1):
                    record_key = (repository.full_name, branch, relative_path, sha)
                    if args.dry_run:
                        progress.line_break()
                        print(f"  {relative_path}")
                        continue
                    if record_key in known_record_keys:
                        skipped_existing += 1
                        continue
                    try:
                        progress.update(
                            repo_index,
                            f"{repository.full_name}: reading {file_index}/{len(matches)} ({relative_path})",
                            log_when_not_interactive=False,
                        )
                        content = file_path.read_text(encoding="utf-8", errors="replace")
                        record = {
                            "repository": repository.full_name,
                            "repository_url": repository.url,
                            "branch": branch,
                            "path": relative_path,
                            "sha": sha,
                            "content": content,
                        }
                        jsonl_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                        jsonl_file.flush()
                        known_record_keys.add(record_key)
                        written += 1
                    except OSError as exc:
                        failed += 1
                        progress.line_break()
                        print(
                            f"Warning: could not read {repository.full_name}/{relative_path}: {exc}",
                            file=sys.stderr,
                        )
            except (GitCommandError, OSError, RuntimeError) as exc:
                failed += 1
                progress.line_break()
                print(f"Warning: could not collect {repository.full_name}: {exc}", file=sys.stderr)
            finally:
                try:
                    remove_temporary_repository(clone_path, temporary_root, args.cleanup_timeout)
                except (OSError, RuntimeError) as exc:
                    cleanup_failed = True
                    failed += 1
                    progress.line_break()
                    print(f"Error: could not remove temporary clone for {repository.full_name}: {exc}", file=sys.stderr)

            if cleanup_failed:
                print("Stopping to avoid keeping more than one repository clone locally.", file=sys.stderr)
                break
            if args.delay:
                time.sleep(args.delay)

    progress.update(len(repositories) + 1, "Collection complete")
    progress.line_break()
    if not args.dry_run:
        print(f"Wrote {written} documentation record(s) to {output_path}")
    print(f"Done: written={written}, skipped_existing={skipped_existing}, failed={failed}.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
