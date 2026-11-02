#!/usr/bin/env python3
"""Find security advisories for repos in the sample from multiple sources.

Different projects publish (or don't publish) vulnerability information in
different places, so this script checks three independent sources and
reports them separately rather than merging them into one number:

  1. GitHub Security Advisories (GHSA) -- the formal per-repo mechanism,
     via GET /repos/{owner}/{repo}/security-advisories. Only works for repos
     that have actually used this GitHub feature.
  2. GitHub Releases -- scans release names/bodies for CVE-YYYY-NNNN and
     GHSA-xxxx-xxxx-xxxx identifiers, plus generic "security fix" language.
  3. Self-documented mentions in the already-collected documentation corpus
     (documentation_files.jsonl) -- scans CHANGELOG/HISTORY/SECURITY files
     for the same identifier patterns, for repos that mention past
     vulnerabilities informally instead of using GHSA.

Output: security_advisory_signals.csv, one row per repo, with columns
indicating what each source found and which source(s) triggered.

Usage:
    python fetch_security_advisories.py
    python fetch_security_advisories.py --refresh   # ignore cache, re-fetch
"""

from __future__ import annotations

import argparse
import csv
import http.client
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

CVE_PATTERN = re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE)
GHSA_PATTERN = re.compile(r"GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}", re.IGNORECASE)
SECURITY_MENTION_PATTERN = re.compile(
    r"security (fix|patch|advisory|vulnerability|release)|"
    r"fixes? a (security|vulnerability)|vulnerability (fixed|patched|disclosed)",
    re.IGNORECASE,
)


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
        "User-Agent": "security-advisory-finder",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            # Some releases have multi-megabyte bodies (changelogs dumped in
            # full); cap how much we read to avoid hangs/incomplete reads.
            raw = response.read(20_000_000)
            return json.loads(raw.decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise GitHubApiError(exc.code, details) from exc
    except (urllib.error.URLError, OSError, TimeoutError, http.client.HTTPException,
             json.JSONDecodeError) as exc:
        raise RuntimeError(f"GitHub network error: {exc}") from exc


def fetch_ghsa_advisories(full_name: str, token: str | None) -> list[dict[str, Any]]:
    """List GitHub Security Advisories published by this repository."""
    url = f"{API_ROOT}/repos/{urllib.parse.quote(full_name, safe='/')}/security-advisories?per_page=100"
    try:
        data = github_json(url, token)
        return data if isinstance(data, list) else []
    except GitHubApiError as exc:
        # 403/404 typically means no permission to view (private-by-default
        # feature) or advisories disabled -- treat as "unknown", not "zero".
        if exc.status in (403, 404):
            return []
        raise


def fetch_releases(full_name: str, token: str | None, max_pages: int = 3) -> list[dict[str, Any]]:
    releases: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        url = (
            f"{API_ROOT}/repos/{urllib.parse.quote(full_name, safe='/')}/releases"
            f"?per_page=100&page={page}"
        )
        try:
            data = github_json(url, token)
        except GitHubApiError as exc:
            if exc.status == 404:
                return releases
            raise
        if not data:
            break
        releases.extend(data)
        if len(data) < 100:
            break
    return releases


def scan_text_for_ids(text: str) -> tuple[set[str], set[str], int]:
    cves = set(m.upper() for m in CVE_PATTERN.findall(text))
    ghsas = set(m.upper() for m in GHSA_PATTERN.findall(text))
    mentions = len(SECURITY_MENTION_PATTERN.findall(text))
    return cves, ghsas, mentions


# --- Cache -------------------------------------------------------------


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


# --- Step 1: scan local documentation corpus --------------------------


def scan_docs_corpus(jsonl_path: Path, full_names: set[str]) -> dict[str, dict[str, Any]]:
    """Scan CHANGELOG/HISTORY/SECURITY/RELEASE files for CVE/GHSA mentions."""
    relevant_name_re = re.compile(r"^(CHANGELOG|HISTORY|SECURITY|RELEASES?)", re.IGNORECASE)
    results: dict[str, dict[str, Any]] = {}

    if not jsonl_path.exists():
        print(f"Warning: {jsonl_path} not found; skipping docs corpus scan.", file=sys.stderr)
        return results

    print(f"Scanning {jsonl_path} for self-documented CVE/GHSA mentions...")
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            repo = record.get("repository", "")
            if repo not in full_names:
                continue
            path = record.get("path", "")
            if not relevant_name_re.match(Path(path).name):
                continue
            content = record.get("content", "") or ""
            cves, ghsas, mentions = scan_text_for_ids(content)
            entry = results.setdefault(repo, {"cves": set(), "ghsas": set(), "mentions": 0})
            entry["cves"] |= cves
            entry["ghsas"] |= ghsas
            entry["mentions"] += mentions

    return results


# --- Main ----------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", default=str(ROOT_DIR / "Repos_Final_Sample.csv"))
    parser.add_argument("--jsonl", default=str(ROOT_DIR / "documentation_files.jsonl"))
    parser.add_argument("--output", default=str(BASE_DIR / "security_advisory_signals.csv"))
    parser.add_argument("--cache", default=str(BASE_DIR / "security_advisory_cache.json"))
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--refresh", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(ROOT_DIR / ".env")
    token = os.getenv("GITHUB_TOKEN")

    with open(args.sample, encoding="utf-8-sig") as f:
        sample_rows = list(csv.DictReader(f))

    def full_name_from_url(url: str) -> str:
        return "/".join(url.rstrip("/").split("/")[-2:])

    for row in sample_rows:
        row["_full_name"] = full_name_from_url(row["Repo_URL"])

    full_names = {row["_full_name"] for row in sample_rows}

    # Step 1: local docs corpus scan (fast, no network).
    docs_hits = scan_docs_corpus(Path(args.jsonl), full_names)

    # Step 2 & 3: GHSA API + Releases API (network, cached).
    cache_path = Path(args.cache)
    cache = {} if args.refresh else load_cache(cache_path)

    total = len(sample_rows)
    rows_out = []
    for index, row in enumerate(sample_rows, start=1):
        full_name = row["_full_name"]
        cached = cache.get(full_name)

        if cached is not None:
            print(f"[{index}/{total}] Cached: {full_name}")
            ghsa_count = cached["ghsa_count"]
            ghsa_ids = cached["ghsa_ids"]
            release_cves = cached["release_cves"]
            release_ghsas = cached["release_ghsas"]
            release_mentions = cached["release_mentions"]
        else:
            print(f"[{index}/{total}] Fetching: {full_name}")
            ghsa_count, ghsa_ids = 0, []
            release_cves, release_ghsas, release_mentions = [], [], 0
            try:
                advisories = fetch_ghsa_advisories(full_name, token)
                ghsa_count = len(advisories)
                ghsa_ids = [a.get("ghsa_id", "") for a in advisories]
                time.sleep(args.delay)

                releases = fetch_releases(full_name, token)
                cve_set: set[str] = set()
                ghsa_set: set[str] = set()
                mention_count = 0
                for rel in releases:
                    text = f"{rel.get('name', '')} {rel.get('body', '') or ''}"
                    c, g, m = scan_text_for_ids(text)
                    cve_set |= c
                    ghsa_set |= g
                    mention_count += m
                release_cves = sorted(cve_set)
                release_ghsas = sorted(ghsa_set)
                release_mentions = mention_count
                time.sleep(args.delay)
            except GitHubApiError as exc:
                if exc.status == 401 and token:
                    print("Warning: GITHUB_TOKEN invalid; continuing without token.", file=sys.stderr)
                    token = None
                else:
                    print(f"Warning: failed for {full_name}: {exc}", file=sys.stderr)
            except RuntimeError as exc:
                print(f"Warning: failed for {full_name}: {exc}", file=sys.stderr)
            except Exception as exc:  # never let one repo crash the whole batch
                print(f"Warning: unexpected error for {full_name}: {exc}", file=sys.stderr)

            cache[full_name] = {
                "ghsa_count": ghsa_count,
                "ghsa_ids": ghsa_ids,
                "release_cves": release_cves,
                "release_ghsas": release_ghsas,
                "release_mentions": release_mentions,
            }
            save_cache(cache_path, cache)

        docs_entry = docs_hits.get(full_name, {"cves": set(), "ghsas": set(), "mentions": 0})
        docs_cves = sorted(docs_entry["cves"])
        docs_ghsas = sorted(docs_entry["ghsas"])
        docs_mentions = docs_entry["mentions"]

        all_cves = sorted(set(release_cves) | set(docs_cves))
        all_ghsas = sorted(set(ghsa_ids) | set(release_ghsas) | set(docs_ghsas))

        sources_triggered = []
        if ghsa_count > 0:
            sources_triggered.append("GHSA_API")
        if release_cves or release_ghsas or release_mentions:
            sources_triggered.append("Releases")
        if docs_cves or docs_ghsas or docs_mentions:
            sources_triggered.append("Docs_Corpus")

        rows_out.append({
            "Repo_Name": row["Repo_Name"],
            "Repo_URL": row["Repo_URL"],
            "GHSA_API_Advisory_Count": ghsa_count,
            "GHSA_API_Ids": ", ".join(ghsa_ids),
            "Release_CVE_Mentions": ", ".join(release_cves),
            "Release_GHSA_Mentions": ", ".join(release_ghsas),
            "Release_Security_Keyword_Count": release_mentions,
            "Docs_CVE_Mentions": ", ".join(docs_cves),
            "Docs_GHSA_Mentions": ", ".join(docs_ghsas),
            "Docs_Security_Keyword_Count": docs_mentions,
            "Distinct_CVE_Count": len(all_cves),
            "Distinct_GHSA_Count": len(all_ghsas),
            "Any_Advisory_Signal": bool(sources_triggered),
            "Advisory_Sources_Used": ", ".join(sources_triggered) if sources_triggered else "None found",
        })

    fieldnames = list(rows_out[0].keys()) if rows_out else []
    rows_out.sort(key=lambda r: (-r["Distinct_CVE_Count"] - r["Distinct_GHSA_Count"], r["Repo_Name"]))

    with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    with_signal = sum(1 for r in rows_out if r["Any_Advisory_Signal"])
    print(f"\nWrote {len(rows_out)} rows to {args.output}")
    print(f"Repos with at least one advisory signal from any source: {with_signal} / {len(rows_out)}")

    source_counts: dict[str, int] = {}
    for r in rows_out:
        for s in r["Advisory_Sources_Used"].split(", "):
            source_counts[s] = source_counts.get(s, 0) + 1
    print("Breakdown by source:", source_counts)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
