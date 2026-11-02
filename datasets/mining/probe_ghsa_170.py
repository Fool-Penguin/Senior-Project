#!/usr/bin/env python3
"""Published GitHub security advisories for the 170 sampled repos, and their fix status.

Lists every published repository advisory (all pages), keeps those whose CWE is in
the 27-CWE catalogue, and classifies each one:

  fixed_with_code   a fix commit was found and it changes .py/.js/.ts source
                    (parent commit = vulnerable version, commit = fixed version)
  fixed_no_code     a fix commit was found but it changes no .py/.js/.ts source
  patched_no_commit a patched version is published but no fix commit was found
  not_fixed         no patched version and no fix commit

Fix commits are looked up in order: commit linked from the advisory, merge commit
of a linked pull request, then a commit search for the GHSA/CVE id in the repo.
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "02_repo_sampling" / "data" / "Repos_Final_Sample.csv"
CATALOGUE = ROOT / "data" / "security_vulnerability_catalogue.yaml"
OUT = Path(__file__).resolve().parent / "ghsa_probe_170.json"
OUT_CSV = Path(__file__).resolve().parent / "ghsa_fix_status_170.csv"

COMMIT_RE = re.compile(r"github\.com/([^/]+/[^/]+)/commit/([0-9a-f]{7,40})", re.I)
PULL_RE = re.compile(r"github\.com/([^/]+/[^/]+)/pull/(\d+)", re.I)
SOURCE_EXTS = {"py", "js", "mjs", "cjs", "jsx", "ts", "tsx"}
TEST_RE = re.compile(r"(^|/)(tests?|__tests__|spec)/|\.(test|spec)\.|(^|/)test_[^/]*\.py$|_test\.py$")
SEARCH_GAP_S = 2.2


def catalogue_cwes() -> set[str]:
    head = CATALOGUE.read_text(encoding="utf-8").split("excluded", 1)[0]
    return set(re.findall(r'^\s*cwe_id:\s*"(CWE-\d+)"', head, re.M))


def gh_json(path: str, retries: int = 5, paginate: bool = False) -> object | None:
    cmd = ["gh", "api", "-H", "Accept: application/vnd.github+json"]
    if paginate:
        cmd += ["--paginate", "--slurp"]
    for attempt in range(retries):
        proc = subprocess.run([*cmd, path], capture_output=True, text=True)
        if proc.returncode == 0:
            try:
                return json.loads(proc.stdout)
            except json.JSONDecodeError:
                return None
        err = (proc.stderr + proc.stdout).lower()
        if "rate limit" in err or "secondary" in err or "429" in err:
            wait = 60 * (attempt + 1)
            print(f"RATE LIMIT on {path.split('?')[0]}: waiting {wait}s (attempt {attempt + 1})", flush=True)
            time.sleep(wait)
            continue
        return None
    print(f"RATE LIMIT gave up on {path.split('?')[0]}", flush=True)
    return None


def list_advisories(full: str) -> list[dict] | None:
    """The endpoint uses cursor pagination; `page=` is ignored, so use gh --paginate."""
    pages = gh_json(f"repos/{full}/security-advisories?state=published&per_page=100", paginate=True)
    if not isinstance(pages, list):
        return None
    out: list[dict] = []
    for page in pages:
        if isinstance(page, list):
            out.extend(page)
    return out


def repos() -> list[tuple[str, str]]:
    rows = list(csv.DictReader(SAMPLE.read_text(encoding="utf-8-sig").splitlines()))
    out = []
    for r in rows:
        m = re.search(r"github\.com/([^/]+/[^/#?]+)", r["Repo_URL"])
        if m:
            out.append((m.group(1).removesuffix(".git"), r.get("Primary_Language", "")))
    return out


def patched_versions(repo_adv: dict, glob: dict | None) -> list[str]:
    found = []
    for v in repo_adv.get("vulnerabilities") or []:
        if v.get("patched_versions"):
            found.append(str(v["patched_versions"]))
    for v in (glob or {}).get("vulnerabilities") or []:
        if v.get("first_patched_version"):
            found.append(str(v["first_patched_version"]))
    return sorted(set(found))


def merged_pr_commit(repo: str, number: str) -> str | None:
    pr = gh_json(f"repos/{repo}/pulls/{number}")
    if isinstance(pr, dict) and pr.get("merged_at") and pr.get("merge_commit_sha"):
        return pr["merge_commit_sha"]
    return None


def search_fix_commit(full: str, ids: list[str]) -> str | None:
    for ident in ids:
        time.sleep(SEARCH_GAP_S)
        res = gh_json(f"search/commits?q=repo:{full}+%22{ident}%22&per_page=5")
        if isinstance(res, dict):
            items = res.get("items") or []
            if items:
                return items[0]["sha"]
    return None


def commit_source_files(repo: str, sha: str) -> tuple[bool, list[str], list[str]]:
    data = gh_json(f"repos/{repo}/commits/{sha}")
    if not isinstance(data, dict):
        return False, [], []
    files = [f["filename"] for f in data.get("files") or []]
    src = [f for f in files if f.rsplit(".", 1)[-1].lower() in SOURCE_EXTS]
    non_test = [f for f in src if not TEST_RE.search(f)]
    return bool(data.get("parents")), src, non_test


def classify(full: str, adv: dict, in_scope: set[str]) -> dict:
    ghsa = adv.get("ghsa_id")
    cve = adv.get("cve_id")
    cwes = sorted({c.get("cwe_id") for c in adv.get("cwes") or [] if c.get("cwe_id")})
    row = {
        "repo": full,
        "ghsa_id": ghsa,
        "cve_id": cve,
        "summary": adv.get("summary"),
        "severity": adv.get("severity"),
        "published_at": adv.get("published_at"),
        "cwes": cwes,
        "catalogue_cwes": sorted(set(cwes) & in_scope),
        "in_catalogue": bool(set(cwes) & in_scope),
    }
    if not row["in_catalogue"]:
        return row

    glob = gh_json(f"advisories/{ghsa}") if ghsa else None
    refs = [r for r in (glob or {}).get("references") or [] if isinstance(r, str)]
    patched = patched_versions(adv, glob if isinstance(glob, dict) else None)

    fix_repo, fix_sha, fix_source = full, None, None
    for r in refs:
        m = COMMIT_RE.search(r)
        if m:
            fix_repo, fix_sha, fix_source = m.group(1), m.group(2), "advisory_commit_link"
            break
    if not fix_sha:
        for r in refs:
            m = PULL_RE.search(r)
            if m:
                sha = merged_pr_commit(m.group(1), m.group(2))
                if sha:
                    fix_repo, fix_sha, fix_source = m.group(1), sha, "merged_pull_request"
                    break
    if not fix_sha:
        sha = search_fix_commit(full, [i for i in (ghsa, cve) if i])
        if sha:
            fix_sha, fix_source = sha, "commit_search_by_id"

    has_parent, src, non_test = (False, [], [])
    if fix_sha:
        has_parent, src, non_test = commit_source_files(fix_repo, fix_sha)

    if fix_sha and has_parent and src:
        status = "fixed_with_code"
    elif fix_sha:
        status = "fixed_no_code"
    elif patched:
        status = "patched_no_commit"
    else:
        status = "not_fixed"

    row.update(
        {
            "patched_versions": patched,
            "fix_repo": fix_repo if fix_sha else None,
            "fix_commit": fix_sha,
            "fix_found_by": fix_source,
            "fix_source_files": len(src),
            "fix_non_test_source_files": len(non_test),
            "status": status,
        }
    )
    return row


def main() -> None:
    in_scope = catalogue_cwes()
    results = []
    for full, lang in repos():
        advisories = list_advisories(full)
        if advisories is None:
            results.append({"repo": full, "language": lang, "advisories": [], "error": "no_access_or_none"})
            continue
        items = [classify(full, a, in_scope) for a in advisories]
        results.append({"repo": full, "language": lang, "advisories": items})
        if items:
            scoped = [a for a in items if a["in_catalogue"]]
            print(
                f"{full}: {len(items)} advisories, {len(scoped)} in catalogue, "
                f"{sum(1 for a in scoped if a['status'] == 'fixed_with_code')} with fixed code",
                flush=True,
            )

    all_adv = [a for r in results for a in r["advisories"]]
    scoped = [a for a in all_adv if a["in_catalogue"]]
    status = Counter(a["status"] for a in scoped)
    found_by = Counter(a["fix_found_by"] for a in scoped if a.get("fix_found_by"))
    per_cwe: dict[str, Counter] = {}
    for a in scoped:
        for c in a["catalogue_cwes"]:
            per_cwe.setdefault(c, Counter())[a["status"]] += 1

    summary = {
        "repos_checked": len(results),
        "repos_with_advisories": sum(1 for r in results if r["advisories"]),
        "advisories_total": len(all_adv),
        "advisories_in_catalogue_cwes": len(scoped),
        "status_counts": dict(status),
        "fix_found_by": dict(found_by),
        "catalogue_cwes_total": len(in_scope),
        "catalogue_cwes_with_fixed_code": sorted(c for c, s in per_cwe.items() if s["fixed_with_code"]),
        "catalogue_cwes_missing": sorted(in_scope - set(per_cwe)),
        "per_cwe": {c: dict(s) for c, s in sorted(per_cwe.items(), key=lambda kv: -sum(kv[1].values()))},
        "repos": results,
    }
    OUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    fields = [
        "repo", "ghsa_id", "cve_id", "severity", "published_at", "catalogue_cwes", "status",
        "fix_found_by", "fix_repo", "fix_commit", "fix_source_files", "fix_non_test_source_files",
        "patched_versions", "summary",
    ]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for a in scoped:
            out = dict(a)
            out["catalogue_cwes"] = ";".join(a["catalogue_cwes"])
            out["patched_versions"] = ";".join(a.get("patched_versions") or [])
            w.writerow(out)

    print(json.dumps({k: v for k, v in summary.items() if k != "repos"}, indent=2))


if __name__ == "__main__":
    main()
