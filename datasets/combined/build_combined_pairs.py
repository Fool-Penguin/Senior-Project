#!/usr/bin/env python3
"""Combine Gift 879 + AppSecBench Py/JS/TS + SecureCodePairs Py/JS/TS + GHSA 74.

One row per vuln/fixed pair. CWE-200 is split by catalogue_id:
  VULN-LLM-002 = LLM02 context/RAG leak
  VULN-LLM-007 = LLM07 system-prompt leak
  none         = generic web disclosure (not LLM)

  python3 datasets/combined/build_combined_pairs.py
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent

OWASP_2021_TO_2025 = {
    "A01:2021": "A01:2025-Broken Access Control",
    "A02:2021": "A04:2025-Cryptographic Failures",
    "A03:2021": "A05:2025-Injection",
    "A04:2021": "A06:2025-Insecure Design",
    "A05:2021": "A02:2025-Security Misconfiguration",
    "A06:2021": "A03:2025-Software Supply Chain Failures",
    "A07:2021": "A07:2025-Authentication Failures",
    "A08:2021": "A08:2025-Software or Data Integrity Failures",
    "A09:2021": "A09:2025-Security Logging and Alerting Failures",
    "A10:2021": "A01:2025-Broken Access Control",
}

SHORT_NAME = {
    "CWE-89": "SQL Injection",
    "CWE-78": "OS Command Injection",
    "CWE-77": "Command Injection (General)",
    "CWE-94": "Code Injection",
    "CWE-95": "Eval Injection",
    "CWE-1336": "Server-Side Template Injection (SSTI)",
    "CWE-943": "NoSQL Injection",
    "CWE-79": "Cross-site Scripting (XSS)",
    "CWE-1427": "Direct and Indirect Prompt Injection",
    "CWE-1426": "Improper Output Handling",
    "CWE-22": "Path Traversal",
    "CWE-601": "Open Redirect",
    "CWE-862": "Missing Authorization",
    "CWE-352": "Cross-Site Request Forgery (CSRF)",
    "CWE-918": "Server-Side Request Forgery (SSRF)",
    "CWE-502": "Deserialization of Untrusted Data",
    "CWE-1321": "Prototype Pollution",
    "CWE-915": "Mass Assignment",
    "CWE-798": "Use of Hard-coded Credentials",
    "CWE-327": "Use of Broken Cryptographic Algorithm",
    "CWE-328": "Weak Hash Algorithm",
    "CWE-338": "Weak PRNG",
    "CWE-347": "Improper Verification of Cryptographic Signature",
    "CWE-611": "XML External Entity (XXE)",
    "CWE-1333": "Regular Expression Denial of Service (ReDoS)",
    "CWE-209": "Generation of Error Message with Sensitive Info",
}

COLUMNS = [
    "sample_id",
    "language",
    "is_vulnerable",
    "cwe_id",
    "cwe_name",
    "cwe_description",
    "owasp_category",
    "cvss_v31_vector",
    "original_sources",
    "source_pattern",
    "sink_pattern",
    "sanitizer_pattern",
    "original_code",
    "fixed_code",
    "catalogue_id",
    "owasp_llm",
]


def nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and value != value:
        return False
    text = str(value).strip()
    return text not in ("", "nan", "None", "null", "NaN")


def clean_str(value) -> str:
    if not nonempty(value):
        return ""
    return str(value).strip()


def norm_cwe(value) -> str:
    match = re.search(r"(\d+)", str(value or ""))
    return f"CWE-{int(match.group(1))}" if match else ""


def norm_lang(value) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"js", "javascript", "node", "nodejs"}:
        return "javascript"
    if raw in {"ts", "typescript"}:
        return "typescript"
    if raw in {"py", "python"}:
        return "python"
    return raw


def lang_from_path(path: str) -> str:
    lower = (path or "").lower()
    if lower.endswith((".ts", ".tsx")):
        return "typescript"
    if lower.endswith((".js", ".jsx", ".mjs", ".cjs")):
        return "javascript"
    if lower.endswith(".py"):
        return "python"
    return ""


def llm_key(value) -> str:
    match = re.search(r"LLM\s*(\d{1,2})", str(value or ""), re.I)
    return f"LLM{int(match.group(1)):02d}" if match else ""


def owasp_2025_from_web(value: str) -> str:
    raw = (value or "").strip().upper().replace(" ", "")
    match = re.search(r"A0?(\d{1,2}):2021", raw)
    if match:
        key = f"A{int(match.group(1)):02d}:2021"
        return OWASP_2021_TO_2025.get(key, "")
    match = re.search(r"A0?(\d{1,2}):2025", raw)
    if match:
        return f"A{int(match.group(1)):02d}:2025"
    return clean_str(value)


def join_patterns(value, language: str) -> str:
    if isinstance(value, dict):
        items = value.get(language) or value.get("javascript" if language == "typescript" else language) or []
        return "; ".join(str(x) for x in items if x)
    if isinstance(value, list):
        return "; ".join(str(x) for x in value if x)
    return clean_str(value)


def load_catalogue():
    yaml_text = (ROOT / "data/security_vulnerability_catalogue.yaml").read_text()
    body = yaml_text.split("exclusions:")[0]
    entries = []
    current: dict = {}
    section = None
    for line in body.splitlines():
        match = re.match(r'  - id: "([^"]+)"', line)
        if match:
            if current:
                entries.append(current)
            current = {"id": match.group(1)}
            section = None
            continue
        match = re.match(r'    (cwe_id|name|owasp_web|owasp_llm|cvss_v31_vector): "([^"]*)"', line)
        if match and current:
            current[match.group(1)] = match.group(2)
            continue
        match = re.match(r"    (source_patterns|sink_patterns|sanitizer_patterns):", line)
        if match and current:
            section = match.group(1)
            current[section] = {}
            continue
        match = re.match(r'      (python|javascript): \[(.*)\]', line)
        if match and current and section:
            items = re.findall(r'"([^"]*)"', match.group(2))
            current[section][match.group(1)] = items
    if current:
        entries.append(current)
    by_id = {e["id"]: e for e in entries}
    by_cwe: dict[str, list[str]] = {}
    for e in entries:
        by_cwe.setdefault(e["cwe_id"], []).append(e["id"])
    return by_id, by_cwe


def gift_cwe200_class(sample_id: str, cwe_name: str) -> str:
    sid = sample_id or ""
    if "LLM02" in sid or cwe_name == "Sensitive Information Disclosure":
        return "LLM02"
    if "LLM07" in sid or cwe_name == "System Prompt Leakage":
        return "LLM07"
    return ""


def catalogue_for(cwe: str, llm: str, sample_id: str, cwe_name: str, by_cwe: dict[str, list[str]]) -> str:
    if "LLM02" in (sample_id or "") or llm == "LLM02":
        return "VULN-LLM-002"
    if "LLM07" in (sample_id or "") or llm == "LLM07":
        return "VULN-LLM-007"
    if llm == "LLM01":
        return "VULN-LLM-001"
    if llm == "LLM05":
        return "VULN-LLM-005"
    if cwe == "CWE-200":
        hint = gift_cwe200_class(sample_id, cwe_name)
        if hint == "LLM02":
            return "VULN-LLM-002"
        if hint == "LLM07":
            return "VULN-LLM-007"
        return ""
    ids = by_cwe.get(cwe) or []
    if len(ids) == 1:
        return ids[0]
    return ids[0] if ids else ""


def names_for(catalogue_id: str, cwe: str, by_id: dict) -> tuple[str, str, str, str]:
    if catalogue_id == "VULN-LLM-002":
        entry = by_id["VULN-LLM-002"]
        return (
            "Sensitive Information Disclosure (LLM Context / RAG)",
            entry["name"],
            entry["owasp_web"],
            entry["owasp_llm"],
        )
    if catalogue_id == "VULN-LLM-007":
        entry = by_id["VULN-LLM-007"]
        return (
            "System Prompt Leakage",
            entry["name"],
            entry["owasp_web"],
            entry["owasp_llm"],
        )
    if catalogue_id and catalogue_id in by_id:
        entry = by_id[catalogue_id]
        return (
            SHORT_NAME.get(cwe, entry["name"]),
            entry["name"],
            entry.get("owasp_web") or "",
            entry.get("owasp_llm") or "",
        )
    if cwe == "CWE-200":
        return (
            "Sensitive Information Disclosure",
            "Exposure of Sensitive Information to an Unauthorized Actor (generic web leak, not LLM02/LLM07)",
            "A01:2025-Broken Access Control",
            "",
        )
    return SHORT_NAME.get(cwe, cwe), SHORT_NAME.get(cwe, cwe), "", ""


def yaml_patterns(catalogue_id: str, language: str, by_id: dict) -> tuple[str, str, str]:
    entry = by_id.get(catalogue_id) or {}
    return (
        join_patterns(entry.get("source_patterns"), language),
        join_patterns(entry.get("sink_patterns"), language),
        join_patterns(entry.get("sanitizer_patterns"), language),
    )


def make_row(
    *,
    sample_id: str,
    language: str,
    cwe_id: str,
    original_sources: list[str],
    original_code: str,
    fixed_code: str,
    by_id: dict,
    by_cwe: dict,
    llm: str = "",
    cwe_name_hint: str = "",
    owasp_fallback: str = "",
    cvss_fallback: str = "",
    source_pattern: str = "",
    sink_pattern: str = "",
    sanitizer_pattern: str = "",
) -> dict | None:
    language = norm_lang(language)
    cwe_id = norm_cwe(cwe_id)
    original_code = original_code or ""
    fixed_code = fixed_code or ""
    if not language or not cwe_id or not original_code.strip() or not fixed_code.strip():
        return None
    catalogue_id = catalogue_for(cwe_id, llm, sample_id, cwe_name_hint, by_cwe)
    cwe_name, cwe_description, owasp_web, owasp_llm = names_for(catalogue_id, cwe_id, by_id)
    if llm and not owasp_llm:
        owasp_llm = {
            "LLM01": "LLM01:2025-Prompt Injection",
            "LLM02": "LLM02:2025-Sensitive Information Disclosure",
            "LLM05": "LLM05:2025-Improper Output Handling",
            "LLM06": "LLM06:2025-Excessive Agency",
            "LLM07": "LLM07:2025-System Prompt Leakage",
        }.get(llm, llm)
    ysrc, ysink, ysan = yaml_patterns(catalogue_id, language, by_id)
    cvss = ""
    if catalogue_id and catalogue_id in by_id:
        cvss = by_id[catalogue_id].get("cvss_v31_vector") or ""
    cvss = cvss or cvss_fallback
    owasp = owasp_web or owasp_2025_from_web(owasp_fallback)
    return {
        "sample_id": sample_id,
        "language": language,
        "is_vulnerable": True,
        "cwe_id": cwe_id,
        "cwe_name": cwe_name,
        "cwe_description": cwe_description,
        "owasp_category": owasp,
        "cvss_v31_vector": cvss,
        "original_sources": original_sources,
        "source_pattern": clean_str(source_pattern) or ysrc,
        "sink_pattern": clean_str(sink_pattern) or ysink,
        "sanitizer_pattern": clean_str(sanitizer_pattern) or ysan,
        "original_code": original_code,
        "fixed_code": fixed_code,
        "catalogue_id": catalogue_id,
        "owasp_llm": owasp_llm,
    }


def from_gift(by_id, by_cwe) -> list[dict]:
    rows = json.loads((ROOT / "datasets/unified/codedee_security_dataset_catalogue_scope.json").read_text())
    out = []
    for row in rows:
        if not nonempty(row.get("fixed_code")):
            continue
        made = make_row(
            sample_id=row["sample_id"],
            language=row.get("language"),
            cwe_id=row.get("cwe_id"),
            original_sources=[f"gift:{row['sample_id']}"],
            original_code=row.get("code") or "",
            fixed_code=row.get("fixed_code") or "",
            by_id=by_id,
            by_cwe=by_cwe,
            cwe_name_hint=clean_str(row.get("cwe_name")),
            owasp_fallback=clean_str(row.get("owasp_category")),
            source_pattern=row.get("source_pattern"),
            sink_pattern=row.get("sink_pattern"),
            sanitizer_pattern=row.get("sanitizer_pattern"),
        )
        if made:
            out.append(made)
    return out


def from_appsec(by_id, by_cwe) -> list[dict]:
    out = []
    for split, name in [("train", "train.jsonl"), ("validation", "validation.jsonl"), ("test", "test.jsonl")]:
        path = ROOT / "datasets/appsecbench" / name
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            lang = norm_lang(row.get("language"))
            if lang not in {"python", "javascript", "typescript"}:
                continue
            bid = row.get("benchmark_id") or row.get("id")
            made = make_row(
                sample_id=f"ASB-{bid}",
                language=lang,
                cwe_id=row.get("expected_cwe") or (row.get("metadata") or {}).get("cwe"),
                original_sources=[f"appsecbench:{bid}:{split}"],
                original_code=row.get("vulnerable_code") or "",
                fixed_code=row.get("secure_code") or "",
                by_id=by_id,
                by_cwe=by_cwe,
                llm=llm_key(row.get("expected_owasp_llm") or (row.get("metadata") or {}).get("owasp_llm")),
                owasp_fallback=row.get("expected_owasp") or "",
                cvss_fallback=clean_str(row.get("expected_cvss")),
                source_pattern=row.get("vulnerability_name") or "",
                sink_pattern=row.get("exploit_example") or "",
                sanitizer_pattern=row.get("expected_fix") or "",
            )
            if made:
                out.append(made)
    return out


def from_scp(by_id, by_cwe) -> list[dict]:
    seen = set()
    out = []
    for name in ["train.jsonl", "validation.jsonl", "test.jsonl", "benchmark.jsonl"]:
        path = ROOT / "datasets/securecodepairs" / name
        split = name.replace(".jsonl", "")
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            rid = row.get("id")
            if rid in seen:
                continue
            seen.add(rid)
            lang = norm_lang(row.get("language"))
            if lang not in {"python", "javascript", "typescript"}:
                continue
            made = make_row(
                sample_id=rid,
                language=lang,
                cwe_id=row.get("cwe"),
                original_sources=[f"securecodepairs:{rid}:{split}"],
                original_code=row.get("vulnerable_code") or "",
                fixed_code=row.get("secure_code") or "",
                by_id=by_id,
                by_cwe=by_cwe,
                llm=llm_key(row.get("owasp_llm")),
                owasp_fallback=row.get("owasp") or "",
                cvss_fallback=clean_str(row.get("cvss_vector")),
                source_pattern=row.get("root_cause") or "",
                sink_pattern=row.get("attack") or "",
                sanitizer_pattern=row.get("fix") or "",
            )
            if made:
                out.append(made)
    return out


def from_ghsa(by_id, by_cwe) -> list[dict]:
    payload = json.loads((ROOT / "datasets/mining/ghsa_eval_pairs.json").read_text())
    out = []
    for row in payload["pairs"]:
        lang = lang_from_path(row.get("file") or "")
        ghsa = row.get("ghsa_id")
        made = make_row(
            sample_id=ghsa,
            language=lang,
            cwe_id=row.get("cwe_id"),
            original_sources=[
                f"ghsa:{ghsa}:{row.get('repo')}:{row.get('file')}:{row.get('parent_commit')}"
            ],
            original_code=row.get("vuln_snippet") or "",
            fixed_code=row.get("fixed_snippet") or "",
            by_id=by_id,
            by_cwe=by_cwe,
            owasp_fallback="",
            source_pattern=row.get("file") or "",
            sink_pattern=row.get("summary") or "",
            sanitizer_pattern="",
        )
        if made:
            out.append(made)
    return out


def main() -> None:
    by_id, by_cwe = load_catalogue()
    gift = from_gift(by_id, by_cwe)
    appsec = from_appsec(by_id, by_cwe)
    scp = from_scp(by_id, by_cwe)
    ghsa = from_ghsa(by_id, by_cwe)
    combined = gift + appsec + scp + ghsa

    jsonl_path = OUT / "codedee_combined_pairs.jsonl"
    json_path = OUT / "codedee_combined_pairs.json"
    csv_path = OUT / "codedee_combined_pairs.csv"
    summary_path = OUT / "codedee_combined_summary.json"

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in combined:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    json_path.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in combined:
            dump = dict(row)
            dump["original_sources"] = json.dumps(row["original_sources"], ensure_ascii=False)
            writer.writerow({k: dump.get(k, "") for k in COLUMNS})

    c200 = [r for r in combined if r["cwe_id"] == "CWE-200"]
    summary = {
        "n_rows": len(combined),
        "by_source": {
            "gift_879": len(gift),
            "appsecbench_pyjsts": len(appsec),
            "securecodepairs_pyjsts": len(scp),
            "ghsa_74": len(ghsa),
        },
        "by_language": dict(Counter(r["language"] for r in combined)),
        "cwe_200": {
            "total": len(c200),
            "LLM02": sum(1 for r in c200 if r["catalogue_id"] == "VULN-LLM-002"),
            "LLM07": sum(1 for r in c200 if r["catalogue_id"] == "VULN-LLM-007"),
            "generic_web": sum(1 for r in c200 if not r["catalogue_id"]),
        },
        "in_catalogue": sum(1 for r in combined if r["catalogue_id"]),
        "out_of_catalogue": sum(1 for r in combined if not r["catalogue_id"]),
        "columns": COLUMNS,
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("wrote", jsonl_path)
    print("wrote", json_path)
    print("wrote", csv_path)


if __name__ == "__main__":
    main()
