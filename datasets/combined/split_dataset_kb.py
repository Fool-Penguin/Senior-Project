#!/usr/bin/env python3
"""Split combined pairs into an exam dataset and a YAML knowledge base.

Knowledge base = every catalogue type in
data/security_vulnerability_catalogue.yaml, one card per language, plus at
most one short example. Dataset = every remaining combined pair (exam).
A snippet is never in both files.

  python3 datasets/combined/split_dataset_kb.py
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from build_combined_pairs import join_patterns, load_catalogue

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
COMBINED = HERE / "codedee_combined_pairs.jsonl"

LANGS = ("python", "javascript", "typescript")
SKIP_CELLS = {("VULN-PROTO-001", "python")}
MAX_EXAMPLE_CHARS = 1600
STRING_RE = re.compile(
    r"(\"\"\"[\s\S]*?\"\"\"|'''[\s\S]*?'''|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')"
)


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
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def source_tag(row: dict) -> tuple[str, str]:
    raw = (row.get("original_sources") or [""])[0]
    kind, _, rest = raw.partition(":")
    if kind == "appsecbench":
        split = raw.split(":")[-1]
        return "appsec", split
    if kind == "securecodepairs":
        split = raw.split(":")[-1]
        return "scp", split
    if kind == "ghsa":
        return "ghsa", "eval"
    if kind == "gift":
        return "gift", "879"
    return kind, rest


def code_key(language: str, code: str) -> str:
    blob = re.sub(r"\s+", " ", (code or "").strip())
    return hashlib.sha1(f"{language}\n{blob}".encode()).hexdigest()


def prefer_example(row: dict) -> tuple:
    sid = row.get("sample_id") or ""
    n = len(row.get("original_code") or "")
    kind, _ = source_tag(row)
    rank = 3
    if "SYN_LLM" in sid or sid.startswith("SYNTH-"):
        rank = 0
    elif kind == "scp":
        rank = 1
    elif kind == "appsec":
        rank = 2
    elif kind == "gift":
        rank = 3
    return (rank, n, sid)


def dumps(obj) -> str:
    text = json.dumps(obj, ensure_ascii=False)
    return (
        text.replace("\u0085", "\\u0085")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def load_json_objects(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    decoder = json.JSONDecoder()
    rows = []
    idx = 0
    n = len(text)
    while idx < n:
        while idx < n and text[idx] in " \t\r\n":
            idx += 1
        if idx >= n:
            break
        obj, end = decoder.raw_decode(text, idx)
        rows.append(obj)
        idx = end
    return rows


def maybe_strip(code: str, language: str) -> str:
    if not code:
        return ""
    if len(code) > 12000:
        kept = []
        for line in code.splitlines():
            if re.search(r"\b(VULNERABLE|SECURE)\b", line, re.I) and not re.search(
                r"\b(def|function|class|return|const|let|var)\b", line
            ):
                continue
            kept.append(line)
        return "\n".join(kept).strip()
    return strip_comments(code, language)


def load_rows() -> list[dict]:
    rows = []
    for row in load_json_objects(COMBINED):
        lang = row["language"]
        row["original_code"] = maybe_strip(row.get("original_code") or "", lang)
        row["fixed_code"] = maybe_strip(row.get("fixed_code") or "", lang)
        if not row["original_code"] or not row["fixed_code"]:
            continue
        rows.append(row)
    return rows


def reason_of(row: dict) -> str:
    kind, split = source_tag(row)
    if kind == "ghsa":
        return "ghsa"
    if kind == "gift":
        return "gift"
    return f"{kind}_{split}"


def build_kb(rows: list[dict]) -> list[dict]:
    """YAML catalogue × language, plus one short unused example when it exists."""
    by_id, _ = load_catalogue()
    pool = []
    for row in rows:
        kind, split = source_tag(row)
        if kind == "ghsa":
            continue
        if kind in {"appsec", "scp"} and split != "train":
            continue
        if len(row["original_code"]) > MAX_EXAMPLE_CHARS:
            continue
        if not row.get("catalogue_id"):
            continue
        pool.append(row)

    cell_n = Counter((r.get("catalogue_id"), r["language"]) for r in rows if r.get("catalogue_id"))
    best: dict[tuple[str, str], dict] = {}
    for row in pool:
        k = (row["catalogue_id"], row["language"])
        if cell_n[k] < 2:
            continue
        prev = best.get(k)
        if prev is None or prefer_example(row) < prefer_example(prev):
            best[k] = row

    cards = []
    for cid, entry in by_id.items():
        for lang in LANGS:
            if (cid, lang) in SKIP_CELLS:
                continue
            src = join_patterns(entry.get("source_patterns"), lang)
            sink = join_patterns(entry.get("sink_patterns"), lang)
            san = join_patterns(entry.get("sanitizer_patterns"), lang)
            ex = best.get((cid, lang))
            cards.append(
                {
                    "kb_id": f"{cid}:{lang}",
                    "kb_kind": "definition",
                    "catalogue_id": cid,
                    "language": lang,
                    "cwe_id": entry["cwe_id"],
                    "cwe_name": entry["name"],
                    "cwe_description": entry["name"],
                    "owasp_category": entry.get("owasp_web") or "",
                    "owasp_llm": entry.get("owasp_llm") or "",
                    "cvss_v31_vector": entry.get("cvss_v31_vector") or "",
                    "source_pattern": src,
                    "sink_pattern": sink,
                    "sanitizer_pattern": san,
                    "example_sample_id": ex["sample_id"] if ex else "",
                    "example_original_code": ex["original_code"] if ex else "",
                    "example_fixed_code": ex["fixed_code"] if ex else "",
                    "example_original_sources": ex["original_sources"] if ex else [],
                }
            )
    return cards


def build_dataset(rows: list[dict], kb: list[dict]):
    """Every combined pair except KB examples and exact code duplicates."""
    kb_ids = {r["example_sample_id"] for r in kb if r.get("example_sample_id")}
    kb_keys = {
        code_key(r["language"], r["example_original_code"])
        for r in kb
        if r.get("example_original_code")
    }
    dataset: list[dict] = []
    used_keys: set[str] = set()
    used_ids: set[str] = set()
    skipped_kb = 0
    skipped_dup = 0

    def add(row: dict) -> bool:
        nonlocal skipped_kb, skipped_dup
        if row["sample_id"] in used_ids:
            return False
        if not row["original_code"] or not row["fixed_code"]:
            return False
        if row["sample_id"] in kb_ids:
            skipped_kb += 1
            return False
        key = code_key(row["language"], row["original_code"])
        if key in kb_keys:
            skipped_dup += 1
            return False
        if key in used_keys and not str(row["sample_id"]).startswith("GHSA-"):
            skipped_dup += 1
            return False
        item = dict(row)
        item["split"] = "dataset"
        item["split_reason"] = reason_of(row)
        dataset.append(item)
        used_ids.add(row["sample_id"])
        used_keys.add(key)
        return True

    # Keep GHSA and official tests first so a train clone loses the tie.
    order = {"ghsa": 0, "appsec": 1, "scp": 2, "gift": 3}
    split_rank = {"test": 0, "eval": 0, "benchmark": 1, "validation": 2, "train": 3, "879": 4}

    def sort_key(row: dict):
        kind, split = source_tag(row)
        return (order.get(kind, 9), split_rank.get(split, 9), row.get("sample_id") or "")

    for row in sorted(rows, key=sort_key):
        add(row)

    return dataset, used_keys, {
        "excluded_kb_examples": skipped_kb,
        "excluded_exact_duplicates": skipped_dup,
    }


def main() -> None:
    rows = load_rows()
    kb = build_kb(rows)
    dataset, used_keys, extra = build_dataset(rows, kb)

    ds_path = HERE / "dataset.jsonl"
    kb_path = HERE / "knowledge_base.jsonl"
    with ds_path.open("w", encoding="utf-8") as handle:
        for row in dataset:
            handle.write(dumps(row) + "\n")
    with kb_path.open("w", encoding="utf-8") as handle:
        for row in kb:
            handle.write(dumps(row) + "\n")

    kb_ex = sum(1 for r in kb if r["example_sample_id"])
    kb_keys = {
        code_key(r["language"], r["example_original_code"])
        for r in kb
        if r["example_original_code"]
    }
    overlap = used_keys & kb_keys
    covered = Counter((r.get("catalogue_id") or "none", r["language"]) for r in dataset)
    by_id, _ = load_catalogue()
    holes = []
    for cid in by_id:
        for lang in LANGS:
            if (cid, lang) in SKIP_CELLS:
                continue
            if covered[(cid, lang)] == 0:
                holes.append(f"{cid}:{lang}")

    summary = {
        "dataset_n": len(dataset),
        "dataset_by_reason": dict(Counter(r["split_reason"] for r in dataset)),
        "dataset_by_language": dict(Counter(r["language"] for r in dataset)),
        "knowledge_base_n": len(kb),
        "knowledge_base_with_example": kb_ex,
        "knowledge_base_definition_only": len(kb) - kb_ex,
        "overlap_dataset_vs_kb_examples": len(overlap),
        "catalogue_cells_with_zero_test": holes,
        **extra,
        "how_to_use": {
            "dataset": "Score the model on original_code (vuln). Optionally score fixed_code as SAFE. Do not put these rows in the prompt.",
            "knowledge_base": "YAML catalogue (all 28 types for language L). Do not inject only the gold CWE. Example fields are optional few-shot, never from this dataset.",
        },
    }
    (HERE / "split_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("wrote", ds_path)
    print("wrote", kb_path)


if __name__ == "__main__":
    main()
