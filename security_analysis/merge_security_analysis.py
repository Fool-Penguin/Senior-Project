#!/usr/bin/env python3
"""Merge all security-analysis outputs into one combined CSV, keyed by repo.

Combines:
  - Repos_Final_Sample.csv        (core sample metadata: domain, stars, etc.)
  - security_docs_analysis.csv    (SECURITY.md quality + agent guardrail signals)
  - security_advisory_signals.csv (GHSA API + Releases + docs-corpus CVE/GHSA mentions)
  - security_dependency_risk.csv  (OSV.dev supply-chain vulnerability exposure)
  - no_signal_diagnosis.csv       (diagnostic notes for repos with no advisory signal)

Output: Security_Analysis_Combined.csv
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent


def load_csv(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        print(f"Warning: {path} not found, skipping its columns.")
        return []
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def index_by_name(rows: list[dict], prefix_exclude: set[str]) -> dict[str, dict]:
    return {r["Repo_Name"]: {k: v for k, v in r.items() if k not in prefix_exclude} for r in rows}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", default=str(ROOT_DIR / "Repos_Final_Sample.csv"))
    parser.add_argument("--docs", default=str(BASE_DIR / "security_docs_analysis.csv"))
    parser.add_argument("--advisories", default=str(BASE_DIR / "security_advisory_signals.csv"))
    parser.add_argument("--dependency-risk", default=str(BASE_DIR / "security_dependency_risk.csv"))
    parser.add_argument("--no-signal-diagnosis", default=str(BASE_DIR / "no_signal_diagnosis.csv"))
    parser.add_argument("--output", default=str(BASE_DIR / "Security_Analysis_Combined.csv"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    sample_rows = load_csv(args.sample)
    docs_rows = load_csv(args.docs)
    advisory_rows = load_csv(args.advisories)
    dep_rows = load_csv(args.dependency_risk)
    diag_rows = load_csv(args.no_signal_diagnosis)

    common_exclude = {"Repo_Name", "Repo_URL"}
    docs_by_name = index_by_name(docs_rows, common_exclude)
    advisory_by_name = index_by_name(advisory_rows, common_exclude)
    dep_by_name = index_by_name(dep_rows, common_exclude)
    diag_by_name = index_by_name(diag_rows, common_exclude)

    # Prefix columns from each source so the combined header stays readable
    # and unambiguous about provenance.
    def prefixed(d: dict, prefix: str) -> dict:
        return {f"{prefix}{k}": v for k, v in d.items()}

    combined_rows = []
    for row in sample_rows:
        name = row["Repo_Name"]
        merged = {
            "Repo_Name": name,
            "Repo_URL": row["Repo_URL"],
            "Domain": row.get("Domain", ""),
            "Primary_Language": row.get("Primary_Language", ""),
            "Stars": row.get("Stars", ""),
            "Has_SECURITY_md_flag": row.get("Has_SECURITY", ""),
        }
        merged.update(prefixed(docs_by_name.get(name, {}), "Docs_"))
        merged.update(prefixed(advisory_by_name.get(name, {}), "Advisory_"))
        merged.update(prefixed(dep_by_name.get(name, {}), "DepRisk_"))
        if name in diag_by_name:
            merged.update(prefixed(diag_by_name.get(name, {}), "Diagnosis_"))
        combined_rows.append(merged)

    fieldnames: list[str] = []
    for row in combined_rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    # Ensure every row has every column (blank if that source was missing this repo).
    for row in combined_rows:
        for key in fieldnames:
            row.setdefault(key, "")

    with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(combined_rows)

    print(f"Wrote {len(combined_rows)} rows x {len(fieldnames)} columns to {args.output}")
    print(f"Sources merged: sample={len(sample_rows)}, docs={len(docs_rows)}, "
          f"advisories={len(advisory_rows)}, dependency_risk={len(dep_rows)}, "
          f"no_signal_diagnosis={len(diag_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
