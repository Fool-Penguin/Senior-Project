#!/usr/bin/env python3
"""Analyze security-related signals from the collected documentation corpus.

Streams `documentation_files.jsonl` (one JSON record per file: repository,
path, content, ...) and, for every repository in the input sample, computes:

  1. SECURITY.md quality signals (does it exist, does it name a contact
     channel, mention a response SLA, list supported versions).
  2. Agent-specific "guardrail" signals found anywhere in the repo's
     documentation: sandboxing, human-approval gates, tool allow/deny lists,
     rate limiting, credential-handling practices, prompt-injection
     awareness, and audit logging. These map to the "Environment &
     Guardrails" pillar of the project's agentic-software definition.

Output: security_docs_analysis.csv, one row per repository in the sample.

Usage:
    python analyze_security_docs.py
    python analyze_security_docs.py --jsonl documentation_files.jsonl \
        --sample Repos_Final_Sample.csv --output security_docs_analysis.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

# --- Keyword signal definitions --------------------------------------------

# Each category: list of regex patterns (case-insensitive). A repo "has" a
# signal if at least one pattern matches anywhere in its documentation.
GUARDRAIL_SIGNALS: dict[str, list[str]] = {
    "Sandboxing": [
        r"\bsandbox(ed|ing)?\b", r"\bisolated (environment|execution|container)\b",
        r"\bcontainer(ized)? isolation\b", r"\bvm isolation\b", r"\bchroot\b",
    ],
    "Human_Approval_Gate": [
        r"human[- ]in[- ]the[- ]loop", r"require(s)? approval", r"confirm before",
        r"approval required", r"ask (for )?(permission|confirmation) before",
        r"review before (executing|running|applying)",
    ],
    "Tool_Allow_Deny_List": [
        r"\ballow[- ]?list(ed|ing)?\b", r"\bdeny[- ]?list(ed|ing)?\b",
        r"\bwhitelist(ed|ing)?\b", r"\bblacklist(ed|ing)?\b",
        r"blocked commands", r"permitted (tools|commands|actions)",
    ],
    "Rate_Limiting": [
        r"\brate[- ]?limit(ed|ing|s)?\b", r"\bthrottl(e|ed|ing)\b", r"\bquota(s)?\b",
    ],
    "Credential_Handling": [
        r"api key(s)? (are |is )?(stored|encrypted|never sent|kept local)",
        r"\bkeychain\b", r"\benv(ironment)? variable(s)?\b.{0,30}\bkey\b",
        r"stored locally", r"encrypted at rest", r"never (leave|leaves) your (device|machine)",
        r"credentials (stay|remain) (local|on your)",
    ],
    "Prompt_Injection_Awareness": [
        r"prompt injection", r"jailbreak(ing)?", r"untrusted (content|input|data)",
        r"malicious instructions", r"injection attack",
    ],
    "Audit_Logging": [
        r"\baudit log(s|ging)?\b", r"\bactivity log(s|ging)?\b",
        r"\bexecution log(s|ging)?\b", r"\btrace(ability)?\b.{0,20}\b(action|tool|execution)\b",
    ],
}

SECURITY_MD_SIGNALS: dict[str, list[str]] = {
    "Has_Contact_Channel": [
        r"[\w.+-]+@[\w-]+\.[\w.-]+",  # any email address
        r"report(ing)? a (vulnerability|security issue)",
        r"responsible disclosure", r"security@",
    ],
    "Has_Response_SLA": [
        r"respond(s)? within \d+", r"response time", r"\d+\s*(business\s*)?(days|hours)\s*(to respond|response)",
    ],
    "Has_Supported_Versions": [
        r"supported versions", r"version.{0,15}(support|eol|end of life)",
    ],
    "Has_PGP_Key": [
        r"pgp", r"gpg key", r"-----BEGIN PGP",
    ],
}


def compile_signals(signals: dict[str, list[str]]) -> dict[str, re.Pattern]:
    return {
        name: re.compile("|".join(f"(?:{p})" for p in patterns), re.IGNORECASE)
        for name, patterns in signals.items()
    }


GUARDRAIL_PATTERNS = compile_signals(GUARDRAIL_SIGNALS)
SECURITY_MD_PATTERNS = compile_signals(SECURITY_MD_SIGNALS)


def is_security_md(path: str) -> bool:
    return Path(path).name.upper() == "SECURITY.MD"


def is_readme(path: str) -> bool:
    return Path(path).name.upper().startswith("README")


# --- Main --------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", default=str(ROOT_DIR / "documentation_files.jsonl"))
    parser.add_argument("--sample", default=str(ROOT_DIR / "Repos_Final_Sample.csv"))
    parser.add_argument("--output", default=str(BASE_DIR / "security_docs_analysis.csv"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    with open(args.sample, encoding="utf-8-sig") as f:
        sample_rows = list(csv.DictReader(f))

    # Map full_name (owner/repo) -> sample row, derived from Repo_URL.
    def full_name_from_url(url: str) -> str:
        return "/".join(url.rstrip("/").split("/")[-2:])

    sample_by_full_name = {full_name_from_url(r["Repo_URL"]): r for r in sample_rows}

    # Per-repo accumulators.
    security_md_text: dict[str, list[str]] = {}
    all_docs_text: dict[str, list[str]] = {}
    files_seen: dict[str, int] = {}
    readme_present: dict[str, bool] = {}
    security_md_present: dict[str, bool] = {}

    total_lines = 0
    matched_lines = 0
    jsonl_path = Path(args.jsonl)
    print(f"Streaming {jsonl_path} ...")
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            total_lines += 1
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            repo = record.get("repository", "")
            if repo not in sample_by_full_name:
                continue
            matched_lines += 1
            path = record.get("path", "")
            content = record.get("content", "") or ""

            files_seen[repo] = files_seen.get(repo, 0) + 1
            all_docs_text.setdefault(repo, []).append(content)

            if is_security_md(path):
                security_md_present[repo] = True
                security_md_text.setdefault(repo, []).append(content)
            if is_readme(path):
                readme_present[repo] = True

            if total_lines % 20000 == 0:
                print(f"  ...{total_lines} lines scanned, {matched_lines} matched sample repos")

    print(f"Done streaming: {total_lines} total lines, {matched_lines} matched our 175-repo sample.")
    print(f"Repos with at least one doc file found: {len(all_docs_text)} / {len(sample_by_full_name)}")

    # --- Compute per-repo metrics -------------------------------------------

    fieldnames = [
        "Repo_Name", "Repo_URL", "Has_SECURITY_File_In_Docs", "Has_README_In_Docs",
        "Total_Doc_Files_Scanned", "SECURITY_MD_Char_Count",
    ] + list(SECURITY_MD_SIGNALS.keys()) + list(GUARDRAIL_SIGNALS.keys()) + ["Guardrail_Signal_Count"]

    rows_out = []
    for full_name, sample_row in sample_by_full_name.items():
        repo_name = sample_row["Repo_Name"]
        repo_url = sample_row["Repo_URL"]

        sec_texts = security_md_text.get(full_name, [])
        sec_combined = "\n".join(sec_texts)
        doc_texts = all_docs_text.get(full_name, [])
        docs_combined = "\n".join(doc_texts)

        row: dict[str, Any] = {
            "Repo_Name": repo_name,
            "Repo_URL": repo_url,
            "Has_SECURITY_File_In_Docs": security_md_present.get(full_name, False),
            "Has_README_In_Docs": readme_present.get(full_name, False),
            "Total_Doc_Files_Scanned": files_seen.get(full_name, 0),
            "SECURITY_MD_Char_Count": len(sec_combined),
        }

        for name, pattern in SECURITY_MD_PATTERNS.items():
            row[name] = bool(pattern.search(sec_combined)) if sec_combined else False

        guardrail_count = 0
        for name, pattern in GUARDRAIL_PATTERNS.items():
            found = bool(pattern.search(docs_combined)) if docs_combined else False
            row[name] = found
            guardrail_count += int(found)
        row["Guardrail_Signal_Count"] = guardrail_count

        rows_out.append(row)

    # Sort by guardrail signal count desc, then repo name, for easy skimming.
    rows_out.sort(key=lambda r: (-r["Guardrail_Signal_Count"], r["Repo_Name"]))

    with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    print(f"\nWrote {len(rows_out)} rows to {args.output}")

    no_docs = [r["Repo_Name"] for r in rows_out if r["Total_Doc_Files_Scanned"] == 0]
    if no_docs:
        print(f"\n{len(no_docs)} repos had NO matching doc records (likely failed clones): {no_docs}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
