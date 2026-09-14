#!/usr/bin/env python3
"""Diagnose whether "no advisory signal" repos are a real absence or a
detection gap in fetch_security_advisories.py.

For each repo with Advisory_Sources_Used == "None found", checks:
  1. GHSA API HTTP status -- distinguishes "confirmed zero" (200, empty
     list) from "denied/unknown" (403/404) which our original script
     silently treated as zero.
  2. Whether the repo had ANY documentation records at all in
     documentation_files.jsonl (a repo with zero doc records can't have
     produced a Docs_Corpus signal no matter what it contains).
  3. Root-level file listing via the GitHub contents API, to check for
     changelog/security filenames our regex might have missed
     (NEWS.md, docs/CHANGELOG.md, .github/SECURITY.md, etc.).
  4. A heuristic OSV.dev lookup using the repo name itself as a package
     name (npm/PyPI/crates.io/Go, based on Primary_Language) to catch
     advisories published against the project's own package rather than
     found via GHSA/Releases/docs.

Output: no_signal_diagnosis.csv
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
OSV_QUERY_URL = "https://api.osv.dev/v1/query"

CHANGELOG_NAME_RE = re.compile(r"(changelog|history|security|release|news)", re.IGNORECASE)


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


def github_request(url: str, token: str | None, method: str = "GET") -> tuple[int, Any]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "no-signal-diagnosis"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read(5_000_000)
            return response.status, json.loads(raw.decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except Exception:
        return -1, None


def osv_query(ecosystem: str, name: str) -> list[str]:
    body = json.dumps({"package": {"name": name, "ecosystem": ecosystem}}).encode()
    req = urllib.request.Request(
        OSV_QUERY_URL, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
            return [v.get("id", "") for v in data.get("vulns", [])]
    except Exception:
        return []


LANGUAGE_TO_OSV_ECOSYSTEM = {
    "JavaScript": "npm", "TypeScript": "npm",
    "Python": "PyPI",
    "Rust": "crates.io",
    "Go": "Go",
    "Ruby": "RubyGems",
    "PHP": "Packagist",
    "Java": "Maven", "Kotlin": "Maven",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", default=str(ROOT_DIR / "Repos_Final_Sample.csv"))
    parser.add_argument("--advisory-signals", default=str(BASE_DIR / "security_advisory_signals.csv"))
    parser.add_argument("--jsonl", default=str(ROOT_DIR / "documentation_files.jsonl"))
    parser.add_argument("--output", default=str(BASE_DIR / "no_signal_diagnosis.csv"))
    parser.add_argument("--delay", type=float, default=0.2)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(ROOT_DIR / ".env")
    token = os.getenv("GITHUB_TOKEN")

    with open(args.sample, encoding="utf-8-sig") as f:
        sample_by_name = {r["Repo_Name"]: r for r in csv.DictReader(f)}

    with open(args.advisory_signals, encoding="utf-8-sig") as f:
        advisory_rows = list(csv.DictReader(f))
    no_signal_names = [r["Repo_Name"] for r in advisory_rows if r["Advisory_Sources_Used"] == "None found"]

    def full_name_from_url(url: str) -> str:
        return "/".join(url.rstrip("/").split("/")[-2:])

    targets = []
    for name in no_signal_names:
        row = sample_by_name.get(name)
        if row:
            targets.append((name, full_name_from_url(row["Repo_URL"]), row.get("Primary_Language", "")))

    # Count doc records per repo from the corpus (fast local pass).
    doc_record_counts: dict[str, int] = {}
    target_full_names = {fn for _, fn, _ in targets}
    jsonl_path = Path(args.jsonl)
    if jsonl_path.exists():
        with jsonl_path.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                repo = record.get("repository", "")
                if repo in target_full_names:
                    doc_record_counts[repo] = doc_record_counts.get(repo, 0) + 1

    rows_out = []
    total = len(targets)
    for index, (name, full_name, language) in enumerate(targets, start=1):
        print(f"[{index}/{total}] Diagnosing: {full_name}")

        # 1. GHSA API status
        ghsa_url = f"{API_ROOT}/repos/{urllib.parse.quote(full_name, safe='/')}/security-advisories?per_page=1"
        status, data = github_request(ghsa_url, token)
        if status == 200:
            ghsa_status = "confirmed_zero" if not data else "found_on_recheck"
        elif status in (403, 404):
            ghsa_status = f"denied_or_disabled (HTTP {status})"
        else:
            ghsa_status = f"error (HTTP {status})"
        time.sleep(args.delay)

        # 2. Doc corpus coverage
        n_docs = doc_record_counts.get(full_name, 0)
        doc_coverage = "no_docs_collected" if n_docs == 0 else f"{n_docs}_docs_collected"

        # 3. Root-level file listing for missed changelog/security filenames
        contents_url = f"{API_ROOT}/repos/{urllib.parse.quote(full_name, safe='/')}/contents/"
        status2, listing = github_request(contents_url, token)
        missed_files = []
        if status2 == 200 and isinstance(listing, list):
            for item in listing:
                fname = item.get("name", "")
                if CHANGELOG_NAME_RE.search(fname) and Path(fname).name.upper() not in (
                    "CHANGELOG.MD", "HISTORY.MD", "SECURITY.MD", "RELEASES.MD", "RELEASE.MD"
                ):
                    missed_files.append(fname)
        time.sleep(args.delay)

        # 4. Heuristic OSV self-package lookup
        ecosystem = LANGUAGE_TO_OSV_ECOSYSTEM.get(language, "")
        osv_hits: list[str] = []
        if ecosystem:
            osv_hits = osv_query(ecosystem, name.lower())
            time.sleep(args.delay)

        rows_out.append({
            "Repo_Name": name,
            "Repo_URL": f"https://github.com/{full_name}",
            "GHSA_Recheck_Status": ghsa_status,
            "Doc_Corpus_Coverage": doc_coverage,
            "Possibly_Missed_Changelog_Files": ", ".join(missed_files) if missed_files else "",
            "OSV_Self_Package_Ecosystem_Tried": ecosystem,
            "OSV_Self_Package_Hits": ", ".join(osv_hits) if osv_hits else "",
            "Likely_Real_Absence": (
                ghsa_status == "confirmed_zero"
                and n_docs > 0
                and not missed_files
                and not osv_hits
            ),
        })

    fieldnames = list(rows_out[0].keys()) if rows_out else []
    with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    likely_real = sum(1 for r in rows_out if r["Likely_Real_Absence"])
    print(f"\nWrote {len(rows_out)} rows to {args.output}")
    print(f"Likely a real absence of advisories: {likely_real} / {len(rows_out)}")
    print(f"Likely a detection gap (worth a second look): {len(rows_out) - likely_real} / {len(rows_out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
