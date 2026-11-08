"""Measure the vulnerable (original_code) and fixed (fixed_code) snippets of the combined security dataset.

Usage: python -I 05_derive_threshold/security/measure_snippets.py [path/to/codedee_combined_pairs.jsonl]
Default input: the security_analysis branch checked out next to this repo:
    git worktree add ../Senior-security security_analysis
    git -C ../Senior-security lfs pull --include "datasets/combined/codedee_combined_pairs.jsonl"
Writes results/snippets.csv (one row per snippet) and results/functions.csv (one row per function).

- Exact duplicates removed with the key of split_dataset_kb.py (language + whitespace-collapsed original_code);
  the first row is kept.
- Label comments that start with VULNERABLE or SECURE (dataset annotations, e.g. `// VULNERABLE: no authz`) are
  removed before measuring, so they do not count as comment lines.
- status: measured, parse_error, or excluded by the repo pipeline's rules (measure.py): generated_vendored
  (generated header, minified/bundled, > 1 MB) or vendored_library. Only measured snippets have metrics.
- Parsed = tree-sitter reports no error (the CST only; no Python ast check, so odd indentation is accepted).
- Left out: Gift CVEfixes rows (id CVEFIXES_CVE_YYYY_N_NNNNN) are a fix commit's removed / added diff lines
  glued together, often across files; GHSA rows are truncated line windows of a file joined together. Neither is
  one real piece of code. Kept: AppSecBench, SecureCodePairs and Gift's hand-written rows (SEC_*, SYN_*,
  SEMGREP_*, ..., and 5 hand-written rows named CVEFIXES_PY_* / CVEFIXES_JS_* / CVEFIXES_CVE_*_NOSQL_*).
- TypeScript is retried with the TSX grammar; a bare JS/TS class method is wrapped (metrics.measure_snippet).
- file_sized: the snippet looks like a whole file = it has an import or more than one top-level function.
"""
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
from measure import MAX_BYTES, content_reason  # noqa: E402
from metrics import duplicated_blocks, measure_snippet  # noqa: E402

DEFAULT_DATA = HERE.parents[2] / "Senior-security" / "datasets" / "combined" / "codedee_combined_pairs.jsonl"
RESULTS = HERE / "results"
EXT = {"python": ".py", "javascript": ".js", "typescript": ".ts"}
# ponytail: regex, not the parser; a string literal holding "// VULNERABLE" would also be cut (none seen)
LABEL = {"python": re.compile(r"#\s*(?:VULNERABLE|SECURE)\b[^\n]*"),
         "js": re.compile(r"//\s*(?:VULNERABLE|SECURE)\b[^\n]*|/\*\s*(?:VULNERABLE|SECURE)\b.*?\*/", re.S)}
VERSIONS = {"vulnerable": "original_code", "fixed": "fixed_code"}
SNIPPET_COLS = ["sample_id", "language", "source", "cwe_id", "version", "status", "sloc", "cloc", "comment_density",
                "functions", "file_sized", "duplicated_blocks", "labels_removed"]
DIFF_ROW = re.compile(r"CVEFIXES_CVE_\d{4}_\d+_\d{5}")
FUNCTION_COLS = ["sample_id", "language", "source", "cwe_id", "version", "name", "start_line", "sloc", "cyclomatic",
                 "cognitive", "cognitive_sloc", "params"]


def code_key(language, code):
    blob = re.sub(r"\s+", " ", (code or "").strip())
    return hashlib.sha1(f"{language}\n{blob}".encode()).hexdigest()


def load(path):
    seen, rows = set(), []
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            k = code_key(r["language"], r["original_code"])
            if k not in seen:
                seen.add(k)
                rows.append(r)
    return [r for r in rows if not DIFF_ROW.fullmatch(r["sample_id"]) and source(r) != "ghsa"]


def source(r):
    return (r.get("original_sources") or [""])[0].split(":")[0]


def parse(language, code):
    """(path used, FileResult) or (path, None) on parse error."""
    path = "snippet" + EXT[language]
    result = measure_snippet(path, code)
    if result is None and language == "typescript":
        path = "snippet.tsx"
        result = measure_snippet(path, code)
    return path, result


def top_level(units):
    return [u for u in units if not any(o is not u and o.start_line <= u.start_line and u.end_line <= o.end_line
                                        and (o.start_line, o.end_line) != (u.start_line, u.end_line) for o in units)]


def measure_row(r):
    base = {"sample_id": r["sample_id"], "language": r["language"], "cwe_id": r["cwe_id"], "source": source(r)}
    snippets, functions = [], []
    for version, column in VERSIONS.items():
        code, removed = LABEL["python" if r["language"] == "python" else "js"].subn("", r[column] or "")
        data = code.encode("utf-8")
        reason = ("generated_vendored" if len(data) > MAX_BYTES else None) or content_reason(data, EXT[r["language"]])
        path, res = (None, None) if reason else parse(r["language"], data)
        row = {**base, "version": version, "labels_removed": removed,
               "status": reason or ("measured" if res is not None else "parse_error")}
        if res is not None:
            dup = duplicated_blocks(path, data)
            if dup is None:  # bare class method: measure_snippet parsed it inside a wrapper class
                dup = duplicated_blocks(path, b"class _ {\n" + data + b"\n}")
            lines = res.sloc + res.cloc
            row.update(sloc=res.sloc, cloc=res.cloc, comment_density=f"{100 * res.cloc / lines:.4f}" if lines else "",
                       functions=len(res.units), duplicated_blocks=dup,
                       file_sized=bool(res.imports) or len(top_level(res.units)) > 1)
            functions += [{**base, "version": version, "name": u.name, "start_line": u.start_line, "sloc": u.sloc,
                           "cyclomatic": u.cyclomatic, "cognitive": "" if u.cognitive is None else u.cognitive,
                           "cognitive_sloc": "" if u.cognitive_sloc is None else u.cognitive_sloc,
                           "params": u.params} for u in res.units]
        snippets.append(row)
    return snippets, functions


def write(name, cols, rows):
    with (RESULTS / name).open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main(data=DEFAULT_DATA):
    rows = load(data)
    snippets, functions = [], []
    for r in rows:
        s, f = measure_row(r)
        snippets += s
        functions += f
    RESULTS.mkdir(exist_ok=True)
    write("snippets.csv", SNIPPET_COLS, snippets)
    write("functions.csv", FUNCTION_COLS, functions)
    print(f"{len(rows)} pairs after removing exact duplicates, CVEfixes diff rows and GHSA;{sum(s['status'] == 'measured' for s in snippets)} of "
          f"{len(snippets)} snippets measured; {len(functions)} functions")


if __name__ == "__main__":
    main(*sys.argv[1:])
