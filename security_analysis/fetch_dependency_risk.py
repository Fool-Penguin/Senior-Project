#!/usr/bin/env python3
"""Assess supply-chain / dependency vulnerability risk for the repo sample.

For each repo:
  1. Fetch its dependency graph SBOM from GitHub
     (GET /repos/{owner}/{repo}/dependency-graph/sbom), which GitHub
     generates automatically for public repos with the Dependency Graph
     enabled -- no per-repo config needed on the maintainer's side.
  2. Parse each package's purl (package URL) into (ecosystem, name, version).
  3. Batch-query OSV.dev (https://osv.dev), which aggregates GHSA, the npm
     advisory DB, PyPA Advisory DB, RustSec, the Go vulnerability DB, and
     more, keyed by package+version rather than by GitHub repo. This is
     what catches "advisories filed against a *dependency*", complementing
     fetch_security_advisories.py which looks for advisories about the
     repo itself.

Output: security_dependency_risk.csv, one row per repo.

Usage:
    python fetch_dependency_risk.py
    python fetch_dependency_risk.py --refresh
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
OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"
OSV_BATCH_SIZE = 500

PURL_RE = re.compile(r"^pkg:([^/]+)/(.+)$")

PURL_TYPE_TO_OSV_ECOSYSTEM = {
    "golang": "Go",
    "npm": "npm",
    "pypi": "PyPI",
    "cargo": "crates.io",
    "gem": "RubyGems",
    "composer": "Packagist",
    "nuget": "NuGet",
    "maven": "Maven",
}


def parse_purl(purl: str) -> tuple[str, str, str] | None:
    """Return (osv_ecosystem, package_name, version) or None if unsupported."""
    m = PURL_RE.match(purl)
    if not m:
        return None
    purl_type, rest = m.group(1), m.group(2)
    ecosystem = PURL_TYPE_TO_OSV_ECOSYSTEM.get(purl_type)
    if not ecosystem:
        return None
    # rest looks like "namespace/name@version" or "name@version"; strip any
    # qualifiers/subpath after '?' or '#'.
    rest = rest.split("?")[0].split("#")[0]
    if "@" not in rest:
        return None
    path_part, version = rest.rsplit("@", 1)
    version = urllib.parse.unquote(version)
    if purl_type == "maven":
        # maven purl: namespace(groupId)/name(artifactId) -> OSV wants "group:artifact"
        parts = path_part.split("/")
        if len(parts) >= 2:
            name = f"{urllib.parse.unquote(parts[0])}:{urllib.parse.unquote(parts[1])}"
        else:
            name = urllib.parse.unquote(path_part)
    else:
        name = urllib.parse.unquote(path_part)
    return ecosystem, name, version


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


def fetch_sbom(full_name: str, token: str | None) -> list[dict[str, Any]]:
    url = f"{API_ROOT}/repos/{urllib.parse.quote(full_name, safe='/')}/dependency-graph/sbom"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "dependency-risk-scanner"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read(30_000_000)
            data = json.loads(raw.decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 404):
            return []
        raise GitHubApiError(exc.code, "") from exc
    return data.get("sbom", {}).get("packages", [])


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


def osv_batch_query(keys: list[tuple[str, str, str]]) -> dict[tuple[str, str, str], list[str]]:
    """keys: list of (ecosystem, name, version). Returns key -> list of vuln IDs."""
    results: dict[tuple[str, str, str], list[str]] = {}
    for i in range(0, len(keys), OSV_BATCH_SIZE):
        chunk = keys[i : i + OSV_BATCH_SIZE]
        queries = [{"package": {"name": name, "ecosystem": eco}, "version": ver} for eco, name, ver in chunk]
        body = json.dumps({"queries": queries}).encode("utf-8")
        req = urllib.request.Request(
            OSV_BATCH_URL, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            print(f"Warning: OSV batch query failed for a chunk: {exc}", file=sys.stderr)
            continue
        for key, result in zip(chunk, data.get("results", [])):
            vulns = result.get("vulns", [])
            if vulns:
                results[key] = [v.get("id", "") for v in vulns]
        print(f"  OSV batch {i // OSV_BATCH_SIZE + 1}/{(len(keys) + OSV_BATCH_SIZE - 1) // OSV_BATCH_SIZE}: "
              f"{sum(1 for r in data.get('results', []) if r.get('vulns'))} of {len(chunk)} flagged")
        time.sleep(1.0)  # be polite to the public OSV API
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", default=str(ROOT_DIR / "Repos_Final_Sample.csv"))
    parser.add_argument("--output", default=str(BASE_DIR / "security_dependency_risk.csv"))
    parser.add_argument("--sbom-cache", default=str(BASE_DIR / "sbom_cache.json"))
    parser.add_argument("--osv-cache", default=str(BASE_DIR / "osv_vuln_cache.json"))
    parser.add_argument("--delay", type=float, default=0.3)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N repos (for testing).")
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

    if args.limit:
        sample_rows = sample_rows[: args.limit]

    # --- Step 1: fetch SBOMs (cached) --------------------------------------
    sbom_cache_path = Path(args.sbom_cache)
    sbom_cache = {} if args.refresh else load_cache(sbom_cache_path)

    total = len(sample_rows)
    repo_packages: dict[str, list[tuple[str, str, str]]] = {}
    for index, row in enumerate(sample_rows, start=1):
        full_name = row["_full_name"]
        if full_name in sbom_cache:
            print(f"[{index}/{total}] Cached SBOM: {full_name}")
            packages = sbom_cache[full_name]
        else:
            print(f"[{index}/{total}] Fetching SBOM: {full_name}")
            packages = []
            try:
                raw_packages = fetch_sbom(full_name, token)
                for pkg in raw_packages:
                    for ref in pkg.get("externalRefs", []):
                        if ref.get("referenceType") == "purl":
                            parsed = parse_purl(ref.get("referenceLocator", ""))
                            if parsed:
                                packages.append(list(parsed))
                            break
            except GitHubApiError as exc:
                if exc.status == 401 and token:
                    print("Warning: GITHUB_TOKEN invalid; continuing without token.", file=sys.stderr)
                    token = None
                else:
                    print(f"Warning: SBOM fetch failed for {full_name}: {exc}", file=sys.stderr)
            except Exception as exc:
                print(f"Warning: unexpected SBOM error for {full_name}: {exc}", file=sys.stderr)

            sbom_cache[full_name] = packages
            save_cache(sbom_cache_path, sbom_cache)
            time.sleep(args.delay)

        repo_packages[full_name] = [tuple(p) for p in packages]

    total_pkg_refs = sum(len(v) for v in repo_packages.values())
    print(f"\nTotal package references across all repos: {total_pkg_refs}")

    # --- Step 2: dedupe and batch-query OSV --------------------------------
    unique_keys: set[tuple[str, str, str]] = set()
    for pkgs in repo_packages.values():
        unique_keys.update(pkgs)
    print(f"Unique (ecosystem, name, version) triples to check: {len(unique_keys)}")

    osv_cache_path = Path(args.osv_cache)
    osv_cache_raw = {} if args.refresh else load_cache(osv_cache_path)
    osv_cache: dict[tuple[str, str, str], list[str]] = {
        tuple(json.loads(k)): v for k, v in osv_cache_raw.items()
    }

    keys_to_query = [k for k in unique_keys if k not in osv_cache]
    print(f"Already cached: {len(unique_keys) - len(keys_to_query)}; querying OSV for {len(keys_to_query)} new keys...")

    if keys_to_query:
        new_results = osv_batch_query(keys_to_query)
        for key in keys_to_query:
            osv_cache[key] = new_results.get(key, [])
        osv_cache_raw = {json.dumps(list(k)): v for k, v in osv_cache.items()}
        save_cache(osv_cache_path, osv_cache_raw)

    # --- Step 3: aggregate per repo -----------------------------------------
    rows_out = []
    for row in sample_rows:
        full_name = row["_full_name"]
        pkgs = repo_packages.get(full_name, [])
        vulnerable = [(pkg, osv_cache.get(pkg, [])) for pkg in pkgs]
        vulnerable = [(pkg, vids) for pkg, vids in vulnerable if vids]
        all_vuln_ids = sorted({vid for _, vids in vulnerable for vid in vids})

        sample_str = "; ".join(
            f"{name}@{version} ({eco}): {','.join(vids[:3])}"
            for (eco, name, version), vids in sorted(vulnerable, key=lambda x: -len(x[1]))[:5]
        )

        total_deps = len(pkgs)
        rows_out.append({
            "Repo_Name": row["Repo_Name"],
            "Repo_URL": row["Repo_URL"],
            "Total_Dependencies_In_SBOM": total_deps,
            "Vulnerable_Dependency_Count": len(vulnerable),
            "Distinct_Vulnerability_Count": len(all_vuln_ids),
            "Vulnerable_Dependency_Ratio": round(len(vulnerable) / total_deps, 4) if total_deps else 0.0,
            "Sample_Vulnerable_Dependencies": sample_str,
        })

    rows_out.sort(key=lambda r: -r["Distinct_Vulnerability_Count"])

    fieldnames = list(rows_out[0].keys()) if rows_out else []
    with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    no_sbom = sum(1 for r in rows_out if r["Total_Dependencies_In_SBOM"] == 0)
    with_vulns = sum(1 for r in rows_out if r["Vulnerable_Dependency_Count"] > 0)
    print(f"\nWrote {len(rows_out)} rows to {args.output}")
    print(f"Repos with no SBOM data at all: {no_sbom}")
    print(f"Repos with >=1 known-vulnerable dependency: {with_vulns}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
