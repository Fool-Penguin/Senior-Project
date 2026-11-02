#!/usr/bin/env python3
"""Qwen detection + CWE on the stripped two-way bench.

Default eval set (not AppSecBench train clones):
  handwritten + SecureCode + AppSecBench TEST

Also scores the original 69 AppSecBench test records with comments stripped
so it can be compared with the previous comment-leaking run.

  python3 eval_qwen/run_benchmark.py
"""

from __future__ import annotations

import csv
import json
import re
import statistics
import subprocess
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_benchmark import load_jsonl, norm_lang, strip_comments, two_cases, owasp_2025_from_appsec  # noqa: E402

CASES = ROOT / "datasets/benchmark/cases.jsonl"
APPSEC_TEST = ROOT / "datasets/appsecbench/test.jsonl"
OUT = ROOT / "eval_qwen/results/benchmark"
OUT.mkdir(parents=True, exist_ok=True)

EVAL_SOURCES = {
    "handwritten",
    "securecode-web-test",
    "securecode-aiml",
    "appsecbench-test",
}

SYSTEM = "You are a senior application-security reviewer. Reply with a single JSON object and no markdown fences."
PROMPT = """\
Review this code for an application-security weakness.

Return ONLY JSON:
{{
  "vulnerable": true or false,
  "cwe": "CWE-XXX or LLM0X or empty if not vulnerable"
}}

Language: {language}
Code:
```
{code}
```
"""

CWE_RE = re.compile(r"(CWE-\d+|LLM0?\d+)", re.I)
JSON_RE = re.compile(r"\{.*\}", re.S)


def ns_to_s(value):
    if value is None:
        return None
    return round(int(value) / 1e9, 4)


def tps(count, duration_ns):
    if not count or not duration_ns:
        return None
    seconds = int(duration_ns) / 1e9
    return round(int(count) / seconds, 2) if seconds > 0 else None


def ollama_rss_mb() -> float:
    proc = subprocess.run(["ps", "-axo", "rss=,comm="], capture_output=True, text=True)
    total_kb = 0
    for line in proc.stdout.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        if "ollama" in parts[1].lower():
            try:
                total_kb += int(parts[0])
            except ValueError:
                pass
    return round(total_kb / 1024, 1)


def ollama_ps(model: str) -> dict:
    try:
        with urllib.request.urlopen("http://localhost:11434/api/ps", timeout=5) as resp:
            body = json.loads(resp.read())
    except Exception:
        return {}
    for m in body.get("models") or []:
        if m.get("name") == model or m.get("model") == model:
            return {
                "size_mb": round((m.get("size") or 0) / 1024 / 1024, 1),
                "size_vram_mb": round((m.get("size_vram") or 0) / 1024 / 1024, 1),
            }
    return {}


def ollama_generate(model: str, system: str, user: str, temperature: float, timeout: int) -> dict:
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"temperature": temperature, "seed": 42},
            "stream": False,
        }
    ).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read())
    prompt_n = body.get("prompt_eval_count")
    gen_n = body.get("eval_count")
    prompt_ns = body.get("prompt_eval_duration")
    gen_ns = body.get("eval_duration")
    return {
        "text": ((body.get("message") or {}).get("content") or "").strip(),
        "prompt_tokens": prompt_n,
        "gen_tokens": gen_n,
        "prompt_tps": tps(prompt_n, prompt_ns),
        "gen_tps": tps(gen_n, gen_ns),
    }


def parse_json(text: str) -> dict:
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip(), flags=re.I | re.S)
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    m = JSON_RE.search(raw)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    return {}


def norm_cwe(value: str) -> str:
    m = CWE_RE.search(value or "")
    if not m:
        return ""
    tok = m.group(1).upper().replace("LLM0", "LLM")
    if tok.startswith("LLM") and not tok.startswith("LLM0"):
        num = re.sub(r"^LLM", "", tok)
        tok = f"LLM{int(num):02d}" if num.isdigit() else tok
    return tok


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.fmean(xs), 4) if xs else None


def appsec_test_all_langs():
    rows = []
    for r in load_jsonl(APPSEC_TEST):
        lang = norm_lang(r.get("language")) or (r.get("language") or "unknown").lower()
        lang_for_strip = lang if lang in {"python", "javascript", "typescript"} else "javascript"
        made = two_cases(
            r["benchmark_id"], lang, r.get("expected_cwe"), owasp_2025_from_appsec(r),
            "appsecbench-test-all", r.get("vulnerable_code") or "", r.get("secure_code") or "",
            {"framework": r.get("framework"), "split": "test"},
        )
        # two_cases uses KEEP_LANG via strip; for other langs still strip as js-style comments
        if not made:
            vuln = strip_comments(r.get("vulnerable_code") or "", lang_for_strip)
            secure = strip_comments(r.get("secure_code") or "", lang_for_strip)
            if vuln and secure and vuln != secure:
                made = [
                    {"case_id": f"{r['benchmark_id']}__vuln", "label": "vulnerable", "gold_cwe": r.get("expected_cwe"),
                     "language": lang, "source": "appsecbench-test-all", "owasp_2025": owasp_2025_from_appsec(r),
                     "code": vuln, "source_id": r["benchmark_id"]},
                    {"case_id": f"{r['benchmark_id']}__safe", "label": "safe", "gold_cwe": "SAFE",
                     "language": lang, "source": "appsecbench-test-all", "owasp_2025": owasp_2025_from_appsec(r),
                     "code": secure, "source_id": r["benchmark_id"]},
                ]
        for c in made:
            c["source"] = "appsecbench-test-all"
        rows.extend(made)
    return rows


def load_eval_cases():
    core = [json.loads(l) for l in CASES.read_text(encoding="utf-8").splitlines() if l.strip()]
    core = [c for c in core if c.get("source") in EVAL_SOURCES]
    have = {c["case_id"] for c in core}
    # Other-language AppSecBench TEST rows, comments stripped, for a same-split comparison.
    for c in appsec_test_all_langs():
        if c["case_id"] not in have:
            core.append(c)
    return core


def metrics(rows):
    tp = sum(1 for r in rows if r["gold_vuln"] and r["pred_vuln"])
    fn = sum(1 for r in rows if r["gold_vuln"] and not r["pred_vuln"])
    fp = sum(1 for r in rows if not r["gold_vuln"] and r["pred_vuln"])
    tn = sum(1 for r in rows if not r["gold_vuln"] and not r["pred_vuln"])
    n = tp + fp + tn + fn
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    spec = tn / (tn + fp) if tn + fp else 0
    acc = (tp + tn) / n if n else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    vuln_rows = [r for r in rows if r["gold_vuln"]]
    cwe_ok = sum(1 for r in vuln_rows if r["cwe_correct"])
    return {
        "n": n, "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "accuracy": round(acc, 4), "precision": round(prec, 4),
        "recall": round(rec, 4), "specificity": round(spec, 4), "f1": round(f1, 4),
        "cwe_accuracy": round(cwe_ok / len(vuln_rows), 4) if vuln_rows else 0,
        "cwe_correct": cwe_ok, "n_vuln": len(vuln_rows),
        "latency_mean_s": mean([r["latency_s"] for r in rows]),
    }


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen2.5-coder:7b")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args()

    cases = load_eval_cases()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ram_baseline = ollama_rss_mb()
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
    except Exception as exc:
        raise SystemExit(f"Ollama not reachable: {exc}") from exc
    ollama_generate(args.model, SYSTEM, "warmup. reply {\"ok\":true}", 0, args.timeout)
    ram_loaded = ollama_rss_mb()
    loaded = ollama_ps(args.model)
    print(f"[data] {len(cases)} cases  model={args.model}", flush=True)
    print(f"[perf] RAM baseline={ram_baseline} loaded={ram_loaded}", flush=True)

    records = []
    ram_peak = ram_loaded
    wall0 = time.time()
    for i, c in enumerate(cases, 1):
        user = PROMPT.format(language=c.get("language") or "", code=c.get("code") or "")
        t0 = time.time()
        try:
            timing = ollama_generate(args.model, SYSTEM, user, args.temperature, args.timeout)
            parsed = parse_json(timing["text"])
        except Exception as exc:
            timing = {"text": str(exc), "prompt_tokens": None, "gen_tokens": None,
                      "prompt_tps": None, "gen_tps": None}
            parsed = {}
        latency = round(time.time() - t0, 3)
        ram_now = ollama_rss_mb()
        ram_peak = max(ram_peak, ram_now)
        pred_vuln = parsed.get("vulnerable") is True or str(parsed.get("vulnerable")).lower() == "true"
        pred_cwe = norm_cwe(str(parsed.get("cwe") or timing.get("text") or ""))
        gold_vuln = c["label"] == "vulnerable"
        gold_cwe = norm_cwe(c.get("gold_cwe") or "")
        rec = {
            "case_id": c["case_id"],
            "source": c["source"],
            "language": c["language"],
            "label": c["label"],
            "gold_cwe": c.get("gold_cwe"),
            "pred_cwe": pred_cwe or "",
            "gold_vuln": gold_vuln,
            "pred_vuln": pred_vuln,
            "cwe_correct": bool(gold_vuln and pred_vuln and pred_cwe == gold_cwe),
            "latency_s": latency,
            "prompt_tps": timing.get("prompt_tps"),
            "gen_tps": timing.get("gen_tps"),
            "ram_rss_mb": ram_now,
            "raw_output": (timing.get("text") or "")[:400],
        }
        records.append(rec)
        if i % 10 == 0 or i <= 3:
            mark = "OK" if rec["cwe_correct"] else ("FG" if rec["pred_vuln"] == gold_vuln else "XX")
            print(f"  [{i:4d}/{len(cases)}] {mark} {c['source']} {c['gold_cwe']} pred={pred_cwe or '-'} {latency:.2f}s", flush=True)

    wall_s = round(time.time() - wall0, 3)
    overall = metrics(records)
    by_source = {src: metrics(rs) for src, rs in _group(records, "source").items()}
    by_lang = {lang: metrics(rs) for lang, rs in _group(records, "language").items()}
    summary = {
        "model": args.model,
        "n_cases": len(records),
        "timestamp": ts,
        "overall": overall,
        "by_source": by_source,
        "by_language": by_lang,
        "perf": {
            "e2e_latency_mean_s": mean([r["latency_s"] for r in records]),
            "e2e_latency_median_s": round(statistics.median(r["latency_s"] for r in records), 4),
            "total_wall_s": wall_s,
            "prompt_tps_mean": mean([r.get("prompt_tps") for r in records]),
            "gen_tps_mean": mean([r.get("gen_tps") for r in records]),
            "ram_baseline_mb": ram_baseline,
            "ram_loaded_mb": ram_loaded,
            "ram_peak_mb": ram_peak,
            "ollama_size_mb": loaded.get("size_mb"),
        },
        "previous_appsecbench_six_task": {
            "note": "comment-leaking AppSecBench test, 69 records × 2 passes",
            "detection_accuracy": 0.8043,
            "cwe_accuracy": 0.1014,
        },
    }
    sum_path = OUT / f"bench_summary_{ts}.json"
    sum_path.write_text(json.dumps(summary, indent=2) + "\n")
    (OUT / "bench_summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    detail = OUT / f"bench_eval_{ts}.csv"
    fields = ["case_id", "source", "language", "label", "gold_cwe", "pred_cwe",
              "gold_vuln", "pred_vuln", "cwe_correct", "latency_s", "prompt_tps",
              "gen_tps", "ram_rss_mb", "raw_output"]
    with detail.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(records)

    head_path = OUT / "bench_headline.csv"
    headline = {
        "model": args.model,
        "n": overall["n"],
        "detection_accuracy": overall["accuracy"],
        "detection_recall": overall["recall"],
        "detection_specificity": overall["specificity"],
        "cwe_accuracy": overall["cwe_accuracy"],
        **{f"{src}_acc": by_source[src]["accuracy"] for src in sorted(by_source)},
        **{f"{src}_cwe": by_source[src]["cwe_accuracy"] for src in sorted(by_source)},
        "latency_mean_s": summary["perf"]["e2e_latency_mean_s"],
        "wall_s": wall_s,
        "ram_peak_mb": ram_peak,
        "gen_tps_mean": summary["perf"]["gen_tps_mean"],
    }
    with head_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(headline.keys()))
        w.writeheader()
        w.writerow(headline)

    print("\n" + "=" * 64)
    print(f"  stripped two-way bench  |  {args.model}")
    print(f"  overall  acc={overall['accuracy']:.3f} rec={overall['recall']:.3f} spec={overall['specificity']:.3f} cwe={overall['cwe_accuracy']:.3f}")
    for src, m in sorted(by_source.items()):
        print(f"  {src:24s} n={m['n']:4d} acc={m['accuracy']:.3f} cwe={m['cwe_accuracy']:.3f}")
    print(f"  latency mean {summary['perf']['e2e_latency_mean_s']}s  wall={wall_s}s")
    print("=" * 64)
    print(f"[out] {detail}")
    print(f"[out] {head_path}")
    print(f"[out] {sum_path}")


def _group(rows, key):
    out = defaultdict(list)
    for r in rows:
        out[r.get(key) or ""].append(r)
    return out


if __name__ == "__main__":
    main()
