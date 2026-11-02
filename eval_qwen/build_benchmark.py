#!/usr/bin/env python3
"""Assemble the stripped two-way detection bench.

Sources:
  - handwritten sparse CWE × language pairs
  - SecureCode web TEST (Py/JS/TS) + AIML JS/TS LLM02/LLM07
  - AppSecBench all splits, comment-stripped, deduped

  python3 eval_qwen/build_benchmark.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from handwritten_pairs import pairs as handwritten_pairs  # noqa: E402

APPSEC = ROOT / "datasets/appsecbench"
SECURE = ROOT / "datasets/securecode"
OUT = ROOT / "datasets/benchmark"
OUT.mkdir(parents=True, exist_ok=True)

LANG_MAP = {
    "python": "python",
    "javascript": "javascript",
    "js": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
}
KEEP_LANGS = {"python", "javascript", "typescript"}

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

SKIP_SUFFIX = (
    ".xml", ".txt", ".json", ".toml", ".yml", ".yaml", ".lock",
    ".properties", ".gradle", ".md", ".html", ".css",
)
TITLE_FENCE = re.compile(r"```(\w*)[^\n]*title=\"([^\"]+)\"\n(.*?)```", re.S)
PLAIN_FENCE = re.compile(r"```(\w*)\n(.*?)```", re.S)
HEAD_VULN = re.compile(
    r"(?is)(?:^|\n)(?:#{1,4}|\*\*)\s*([^\n]{0,80}vulnerable[^\n]{0,80})\s*(?:\*\*)?\s*\n+(.*?)(?=(?:\n(?:#{1,4}|\*\*)\s*)|$)"
)
HEAD_SECURE = re.compile(
    r"(?is)(?:^|\n)(?:#{1,4}|\*\*)\s*([^\n]{0,80}secure[^\n]{0,80})\s*(?:\*\*)?\s*\n+(.*?)(?=(?:\n(?:#{1,4}|\*\*)\s*)|$)"
)
STRING_RE = re.compile(r"(\"\"\"[\s\S]*?\"\"\"|'''[\s\S]*?'''|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')")


def norm_lang(value: str) -> str | None:
    return LANG_MAP.get((value or "").strip().lower())


def owasp_2025_from_appsec(row: dict) -> str:
    llm = (row.get("expected_owasp_llm") or "").strip()
    if llm:
        return llm if "2025" in llm or llm.startswith("LLM") else llm
    raw = (row.get("expected_owasp") or "").strip().upper().replace(" ", "")
    m = re.search(r"A0?(\d{1,2}):2021", raw)
    if m:
        key = f"A{int(m.group(1)):02d}:2021"
        return OWASP_2021_TO_2025.get(key, key)
    return raw


def strip_comments(code: str, language: str) -> str:
    if not code:
        return ""
    placeholders = []

    def hold(m):
        placeholders.append(m.group(0))
        return f"__STR{len(placeholders) - 1}__"

    work = STRING_RE.sub(hold, code)
    work = re.sub(r"/\*[\s\S]*?\*/", "", work)
    work = re.sub(r"<!--[\s\S]*?-->", "", work)
    if language == "python":
        work = re.sub(r"#.*?$", "", work, flags=re.M)
    else:
        work = re.sub(r"//.*?$", "", work, flags=re.M)
        work = re.sub(r"#.*?$", "", work, flags=re.M)
    for i, s in enumerate(placeholders):
        work = work.replace(f"__STR{i}__", s)
    lines = []
    for line in work.splitlines():
        if re.search(r"\b(VULNERABLE|SECURE)\b", line, re.I) and not re.search(
            r"\b(def|function|class|return|const|let|var)\b", line
        ):
            continue
        lines.append(line.rstrip())
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def code_key(language: str, code: str) -> str:
    blob = re.sub(r"\s+", " ", (code or "").strip())
    return hashlib.sha1(f"{language}\n{blob}".encode()).hexdigest()


def skip_title(title: str) -> bool:
    t = title.lower()
    return t.endswith(SKIP_SUFFIX) or "/pom.xml" in t or t.endswith("package.json")


def pick_fenced(files: list[tuple[str, str, str]], language: str) -> str | None:
    if not files:
        return None
    ext = {"python": ".py", "javascript": ".js", "typescript": ".ts"}[language]
    ranked = []
    for title, lang, body in files:
        if skip_title(title):
            continue
        score = len(body)
        if title.lower().endswith(ext):
            score += 10_000
        if lang.lower() in {language, language[:2], "js", "ts", "py"}:
            score += 1_000
        ranked.append((score, body))
    if not ranked:
        return None
    ranked.sort(reverse=True)
    return ranked[0][1].strip()


def extract_titled(text: str, language: str) -> tuple[str | None, str | None]:
    vuln, secure = [], []
    for lang, title, body in TITLE_FENCE.findall(text or ""):
        low = title.lower()
        if "vulnerab" in low:
            vuln.append((title, lang, body))
        elif "secure" in low:
            secure.append((title, lang, body))
    return pick_fenced(vuln, language), pick_fenced(secure, language)


def first_fence(block: str) -> str | None:
    m = PLAIN_FENCE.search(block or "")
    return m.group(2).strip() if m else None


def extract_headed(text: str) -> tuple[str | None, str | None]:
    vuln = secure = None
    for title, body in HEAD_VULN.findall(text or ""):
        if re.search(r"secure", title, re.I) and not re.search(r"vulnerab", title, re.I):
            continue
        vuln = first_fence(body) or vuln
    for title, body in HEAD_SECURE.findall(text or ""):
        if re.search(r"vulnerab", title, re.I):
            continue
        secure = first_fence(body) or secure
    return vuln, secure


def two_cases(source_id, language, cwe, owasp, source, vuln, secure, extra=None):
    vuln_s = strip_comments(vuln, language)
    secure_s = strip_comments(secure, language)
    if not vuln_s or not secure_s or vuln_s == secure_s:
        return []
    base = {
        "language": language,
        "source": source,
        "owasp_2025": owasp,
        "source_id": source_id,
        **(extra or {}),
    }
    return [
        {**base, "case_id": f"{source_id}__vuln", "label": "vulnerable", "gold_cwe": cwe, "code": vuln_s},
        {**base, "case_id": f"{source_id}__safe", "label": "safe", "gold_cwe": "SAFE", "code": secure_s},
    ]


def load_jsonl(path: Path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def from_handwritten():
    cases = []
    for i, p in enumerate(handwritten_pairs(), 1):
        sid = f"HW-{p['cwe']}-{p['language']}-{p['item']}"
        cases += two_cases(sid, p["language"], p["cwe"], p["owasp_2025"], "handwritten",
                           p["vulnerable_code"], p["secure_code"], {"item": p["item"]})
    return cases


def from_securecode_web():
    import pyarrow.parquet as pq

    table = pq.read_table(SECURE / "web_test.parquet")
    batch = table.to_pydict()
    cases, skipped = [], 0
    for i in range(table.num_rows):
        md = batch["metadata"][i]
        lang = norm_lang(md.get("lang"))
        if lang not in KEEP_LANGS:
            continue
        text = batch["conversations"][i][1]["content"]
        vuln, secure = extract_titled(text, lang)
        if not vuln or not secure:
            vuln2, secure2 = extract_headed(text)
            vuln, secure = vuln or vuln2, secure or secure2
        made = two_cases(
            batch["uid"][i], lang, md.get("cwe"), md.get("owasp_2025"),
            "securecode-web-test", vuln or "", secure or "",
            {"framework": md.get("framework")},
        )
        if made:
            cases += made
        else:
            skipped += 1
    return cases, skipped


def from_securecode_aiml():
    import pyarrow.parquet as pq

    table = pq.read_table(SECURE / "aiml_train.parquet")
    batch = table.to_pydict()
    cases, skipped = [], 0
    for i in range(table.num_rows):
        md = batch["metadata"][i]
        lang = norm_lang(md.get("lang"))
        llm = (md.get("owasp_llm_2025") or "").upper()
        if lang not in {"javascript", "typescript"} or llm not in {"LLM02", "LLM07"}:
            continue
        turns = batch["conversations"][i]
        text = ""
        for t in turns:
            if t.get("role") in {"assistant", "gpt"}:
                text = t.get("content") or ""
                break
        vuln, secure = extract_headed(text)
        if not vuln or not secure:
            vuln, secure = extract_titled(text, lang)
        gold = llm
        owasp = f"{llm}:2025-Sensitive Information Disclosure" if llm == "LLM02" else f"{llm}:2025-System Prompt Leakage"
        made = two_cases(
            batch["id"][i], lang, gold, owasp, "securecode-aiml",
            vuln or "", secure or "", {"framework": md.get("framework")},
        )
        if made:
            cases += made
        else:
            skipped += 1
    return cases, skipped


def from_appsecbench():
    rows = []
    for split, name in [("train", "train.jsonl"), ("val", "validation.jsonl"), ("test", "test.jsonl")]:
        for r in load_jsonl(APPSEC / name):
            r["_split"] = split
            rows.append(r)

    stripped_groups = defaultdict(list)
    for r in rows:
        lang = norm_lang(r.get("language"))
        if lang not in KEEP_LANGS:
            continue
        key = re.sub(r"\s+", " ", strip_comments(r.get("vulnerable_code") or "", lang))
        stripped_groups[key].append(r)

    extras = sum(len(v) - 1 for v in stripped_groups.values() if len(v) > 1)
    dupe_rows = sum(len(v) for v in stripped_groups.values() if len(v) > 1)
    unique_codes = len(stripped_groups)

    # Prefer test > val > train, then original id.
    rank = {"test": 0, "val": 1, "train": 2}
    kept, dropped = [], 0
    for group in stripped_groups.values():
        group.sort(key=lambda r: (rank[r["_split"]], r.get("benchmark_id") or ""))
        kept.append(group[0])
        dropped += len(group) - 1

    cases = []
    for r in kept:
        lang = norm_lang(r.get("language"))
        cases += two_cases(
            r["benchmark_id"], lang, r.get("expected_cwe"), owasp_2025_from_appsec(r),
            f"appsecbench-{r['_split']}", r.get("vulnerable_code") or "", r.get("secure_code") or "",
            {"framework": r.get("framework"), "split": r["_split"]},
        )
    stats = {
        "appsecbench_all_records": len(rows),
        "appsecbench_pyjsts": sum(1 for r in rows if norm_lang(r.get("language")) in KEEP_LANGS),
        "unique_stripped_vuln_code": unique_codes,
        "duplicate_group_rows": dupe_rows,
        "extra_copies_dropped": extras,
        "kept_pairs": len(kept),
        "two_way_cases": len(cases),
    }
    return cases, stats


def dedupe_cases(cases):
    seen = {}
    out, dropped = [], 0
    priority = {"handwritten": 0, "securecode-web-test": 1, "securecode-aiml": 2,
                "appsecbench-test": 3, "appsecbench-val": 4, "appsecbench-train": 5}
    ordered = sorted(cases, key=lambda c: (priority.get(c["source"], 9), c["case_id"]))
    for c in ordered:
        key = code_key(c["language"], c["code"])
        if key in seen:
            dropped += 1
            continue
        seen[key] = c["case_id"]
        out.append(c)
    return out, dropped


def audit_sample(cases, n=50):
    # Stratified: 10 handwritten, 20 securecode, 20 appsecbench.
    by = defaultdict(list)
    for c in cases:
        if c["source"] == "handwritten":
            by["handwritten"].append(c)
        elif c["source"].startswith("securecode"):
            by["securecode"].append(c)
        else:
            by["appsecbench"].append(c)
    picked = []
    for src, k in [("handwritten", 10), ("securecode", 20), ("appsecbench", 20)]:
        bucket = by[src]
        step = max(1, len(bucket) // k) if bucket else 1
        picked.extend(bucket[::step][:k])
    # pad if short
    if len(picked) < n:
        rest = [c for c in cases if c not in picked]
        picked.extend(rest[: n - len(picked)])
    return picked[:n]


def review_label(case: dict) -> tuple[str, str]:
    """Lightweight hand-style checks on sampled labels."""
    code = case["code"]
    label = case["label"]
    cwe = case["gold_cwe"]
    notes = []
    leak = bool(re.search(r"\b(VULNERABLE|SECURE|CWE-\d+)\b", code, re.I))
    if leak:
        notes.append("giveaway token still present")
    if label == "vulnerable":
        if cwe in {"CWE-78", "CWE-94"} and not re.search(
            r"\b(exec|spawn\(|eval|new Function|runInNewContext|execSync|execFile)\b", code
        ):
            notes.append("sink not obvious for injection CWE")
        if cwe == "CWE-798" and not re.search(
            r"(AKIA|supersecret|admin123|letmein|sk-live|hooks\.slack|postgres://)", code
        ):
            notes.append("hardcoded secret not obvious")
        if label == "vulnerable" and len(code) < 20:
            notes.append("snippet too short")
        verdict = "keep" if not notes else "review"
    else:
        if re.search(r"verify_signature.: False|algorithms: \[.none.\]|Math\.random\(", code):
            notes.append("safe case still looks unsafe")
            verdict = "review"
        else:
            verdict = "keep"
    if leak:
        verdict = "fix"
    return verdict, "; ".join(notes) or "ok"


def main():
    hw = from_handwritten()
    web, web_skip = from_securecode_web()
    aiml, aiml_skip = from_securecode_aiml()
    appsec, appsec_stats = from_appsecbench()
    raw = hw + web + aiml + appsec
    cases, dropped = dedupe_cases(raw)

    OUT.joinpath("cases.jsonl").write_text(
        "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases), encoding="utf-8"
    )

    summary = {
        "n_cases": len(cases),
        "n_vulnerable": sum(1 for c in cases if c["label"] == "vulnerable"),
        "n_safe": sum(1 for c in cases if c["label"] == "safe"),
        "by_source": dict(Counter(c["source"] for c in cases)),
        "by_language": dict(Counter(c["language"] for c in cases)),
        "by_label_cwe": dict(Counter(c["gold_cwe"] for c in cases if c["label"] == "vulnerable")),
        "handwritten_pairs": len(hw) // 2,
        "securecode_web_cases": len(web),
        "securecode_web_skipped": web_skip,
        "securecode_aiml_cases": len(aiml),
        "securecode_aiml_skipped": aiml_skip,
        "appsecbench": appsec_stats,
        "cross_source_dedupe_dropped": dropped,
        "note_appsecbench_duplicates": (
            "Friend cited 46 duplicate records. Full AppSecBench is 572 rows. "
            f"After comment-stripping Py/JS/TS vulnerable_code we keep "
            f"{appsec_stats['unique_stripped_vuln_code']} unique snippets and drop "
            f"{appsec_stats['extra_copies_dropped']} extra copies. "
            "Test+val stripped-code overlap with train is ~52; 46 is in that range."
        ),
    }
    OUT.joinpath("coverage.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    sample = audit_sample(cases, 50)
    audit_path = OUT / "label_audit.csv"
    with audit_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=["case_id", "source", "language", "label", "gold_cwe", "verdict", "notes", "code_preview"],
        )
        w.writeheader()
        for c in sample:
            verdict, notes = review_label(c)
            w.writerow({
                "case_id": c["case_id"],
                "source": c["source"],
                "language": c["language"],
                "label": c["label"],
                "gold_cwe": c["gold_cwe"],
                "verdict": verdict,
                "notes": notes,
                "code_preview": c["code"][:240].replace("\n", " / "),
            })

    print(json.dumps(summary, indent=2))
    print(f"[out] {OUT / 'cases.jsonl'}")
    print(f"[out] {OUT / 'coverage.json'}")
    print(f"[out] {audit_path}")


if __name__ == "__main__":
    main()
