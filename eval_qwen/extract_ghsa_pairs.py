#!/usr/bin/env python3
"""Pull parent (vulnerable) vs fix source for one-file, single-CWE GHSA pairs."""

from __future__ import annotations

import base64
import csv
import json
import re
import subprocess
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS_CSV = ROOT / "datasets/mining/ghsa_fix_status_170.csv"
OUT_JSON = ROOT / "datasets/mining/ghsa_eval_pairs.json"
OUT_CSV = ROOT / "datasets/mining/ghsa_eval_pairs.csv"

SOURCE_EXTS = {"py", "js", "mjs", "cjs", "jsx", "ts", "tsx"}
TEST_RE = re.compile(r"(^|/)(tests?|__tests__|spec)/|\.(test|spec)\.|(^|/)test_[^/]*\.py$|_test\.py$")
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.M)
MAX_SNIPPET = 3500
CONTEXT = 25


def gh_json(path: str, retries: int = 5) -> object | None:
    cmd = ["gh", "api", "-H", "Accept: application/vnd.github+json", path]
    for attempt in range(retries):
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            try:
                return json.loads(proc.stdout)
            except json.JSONDecodeError:
                return None
        err = (proc.stderr + proc.stdout).lower()
        if "rate limit" in err or "secondary" in err or "429" in err:
            wait = 60 * (attempt + 1)
            print(f"RATE LIMIT {path}: wait {wait}s", flush=True)
            time.sleep(wait)
            continue
        print(f"API fail {path}: {proc.stderr.strip()[:200]}", flush=True)
        return None
    return None


def file_at(repo: str, path: str, ref: str) -> str | None:
    enc = urllib.parse.quote(path)
    data = gh_json(f"repos/{repo}/contents/{enc}?ref={ref}")
    if not isinstance(data, dict) or data.get("type") != "file":
        return None
    if data.get("encoding") == "base64" and data.get("content"):
        raw = data["content"].replace("\n", "")
        try:
            return base64.b64decode(raw).decode("utf-8", errors="replace")
        except Exception:
            return None
    return None


def source_files(commit: dict) -> list[dict]:
    out = []
    for f in commit.get("files") or []:
        name = f.get("filename") or ""
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if ext not in SOURCE_EXTS or TEST_RE.search(name):
            continue
        out.append(f)
    return out


def slice_file(text: str, ranges: list[tuple[int, int]]) -> str:
    lines = text.splitlines()
    chunks = []
    seen: set[tuple[int, int]] = set()
    for start, end in ranges:
        a = max(1, start)
        b = min(len(lines), end)
        key = (a, b)
        if key in seen:
            continue
        seen.add(key)
        body = "\n".join(f"{i}| {lines[i - 1]}" for i in range(a, b + 1))
        chunks.append(f"# lines {a}-{b}\n{body}")
    snippet = "\n\n".join(chunks)
    if len(snippet) > MAX_SNIPPET:
        snippet = snippet[:MAX_SNIPPET] + "\n# [truncated]"
    return snippet


def make_snippet(text: str, patch: str | None, side: str) -> tuple[str, str]:
    if not text.strip():
        return "", "empty"
    if len(text) <= MAX_SNIPPET or not patch:
        body = text if len(text) <= MAX_SNIPPET else text[:MAX_SNIPPET] + "\n# [truncated]"
        return body, "full_file" if len(text) <= MAX_SNIPPET else "truncated_file"
    ranges = []
    for m in HUNK_RE.finditer(patch):
        if side == "parent":
            start = int(m.group(1))
            count = int(m.group(2) or 1)
        else:
            start = int(m.group(3))
            count = int(m.group(4) or 1)
        ranges.append((max(1, start - CONTEXT), start + count + CONTEXT))
    if not ranges:
        return text[:MAX_SNIPPET] + "\n# [truncated]", "truncated_file"
    return slice_file(text, ranges), "hunks"


def candidates() -> list[dict]:
    rows = list(csv.DictReader(STATUS_CSV.read_text(encoding="utf-8").splitlines()))
    return [
        r
        for r in rows
        if r["status"] == "fixed_with_code"
        and r.get("fix_non_test_source_files") == "1"
        and ";" not in (r.get("catalogue_cwes") or "")
        and r.get("fix_commit")
    ]


def extract_one(row: dict) -> dict | None:
    repo = row["fix_repo"] or row["repo"]
    sha = row["fix_commit"]
    commit = gh_json(f"repos/{repo}/commits/{sha}")
    if not isinstance(commit, dict):
        return None
    parents = [p.get("sha") for p in commit.get("parents") or [] if p.get("sha")]
    if not parents:
        return None
    parent = parents[0]
    files = source_files(commit)
    if len(files) != 1:
        return None
    f = files[0]
    path = f["filename"]
    parent_path = f.get("previous_filename") or path
    vuln = file_at(repo, parent_path, parent)
    fixed = file_at(repo, path, sha)
    if vuln is None or fixed is None:
        return None
    patch = f.get("patch")
    vuln_snip, vuln_how = make_snippet(vuln, patch, "parent")
    fix_snip, fix_how = make_snippet(fixed, patch, "fixed")
    if not vuln_snip.strip() or not fix_snip.strip():
        return None
    if vuln_snip == fix_snip:
        return None
    return {
        "ghsa_id": row["ghsa_id"],
        "cve_id": row.get("cve_id") or None,
        "repo": row["repo"],
        "fix_repo": repo,
        "cwe_id": row["catalogue_cwes"],
        "severity": row.get("severity"),
        "summary": row.get("summary"),
        "file": path,
        "parent_commit": parent,
        "fix_commit": sha,
        "vuln_snippet": vuln_snip,
        "fixed_snippet": fix_snip,
        "vuln_extract": vuln_how,
        "fixed_extract": fix_how,
        "vuln_chars": len(vuln),
        "fixed_chars": len(fixed),
    }


def main() -> None:
    rows = candidates()
    print(f"candidates: {len(rows)}", flush=True)
    pairs = []
    skipped = 0
    for i, row in enumerate(rows, 1):
        item = extract_one(row)
        if item:
            pairs.append(item)
            print(
                f"[{i}/{len(rows)}] OK {row['repo']} {row['ghsa_id']} {row['catalogue_cwes']} {item['file']}",
                flush=True,
            )
        else:
            skipped += 1
            print(f"[{i}/{len(rows)}] SKIP {row['repo']} {row['ghsa_id']}", flush=True)
        time.sleep(0.15)

    OUT_JSON.write_text(json.dumps({"n": len(pairs), "skipped": skipped, "pairs": pairs}, indent=2) + "\n")
    fields = [
        "ghsa_id", "cve_id", "repo", "cwe_id", "severity", "file",
        "parent_commit", "fix_commit", "vuln_extract", "fixed_extract",
        "vuln_chars", "fixed_chars", "summary",
    ]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(pairs)
    print(f"extracted {len(pairs)} skipped {skipped} -> {OUT_JSON}")


if __name__ == "__main__":
    main()
