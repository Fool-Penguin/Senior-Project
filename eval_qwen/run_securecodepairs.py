#!/usr/bin/env python3
"""Score qwen2.5-coder:7b on SecureCodePairs official test split.

  python3 eval_qwen/run_securecodepairs.py
"""

from __future__ import annotations

import csv
import json
import re
import statistics
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_appsecbench import (  # noqa: E402
    ollama_generate,
    ollama_ps,
    ollama_rss_mb,
    parse_json,
)

TEST = ROOT / "datasets/securecodepairs/test.jsonl"
OUT = ROOT / "eval_qwen/results/benchmark"
OUT.mkdir(parents=True, exist_ok=True)

SYSTEM = "You are a senior application-security reviewer. Reply with a single JSON object and no markdown fences."
PROMPT = """\
Review this code for an application-security weakness.

Return ONLY JSON:
{{
  "vulnerable": true or false,
  "cwe": "CWE-XXX or empty if not vulnerable"
}}

Language: {language}
Code:
```
{code}
```
"""

CWE_RE = re.compile(r"CWE-\d+", re.I)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.fmean(xs), 4) if xs else None


def norm_cwe(value: str) -> str:
    m = CWE_RE.search(value or "")
    return m.group(0).upper() if m else ""


def load_pairs(path: Path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def cases_from_pairs(pairs):
    out = []
    for r in pairs:
        out.append({
            "case_id": f"{r['id']}__vuln",
            "pair_id": r["id"],
            "language": r.get("language") or "",
            "framework": r.get("framework") or "",
            "label": "vulnerable",
            "gold_cwe": r.get("cwe") or "",
            "code": r.get("vulnerable_code") or "",
            "owasp": r.get("owasp") or "",
        })
        out.append({
            "case_id": f"{r['id']}__safe",
            "pair_id": r["id"],
            "language": r.get("language") or "",
            "framework": r.get("framework") or "",
            "label": "safe",
            "gold_cwe": "SAFE",
            "code": r.get("secure_code") or "",
            "owasp": r.get("owasp") or "",
        })
    return out


def score_rows(rows):
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
    vuln = [r for r in rows if r["gold_vuln"]]
    cwe_ok = sum(1 for r in vuln if r["cwe_correct"])
    return {
        "n": n, "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "specificity": round(spec, 4),
        "f1": round(f1, 4),
        "cwe_accuracy": round(cwe_ok / len(vuln), 4) if vuln else 0,
        "cwe_correct": cwe_ok,
        "n_vuln": len(vuln),
    }


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen2.5-coder:7b")
    ap.add_argument("--split", default="test", choices=["test", "benchmark", "validation"])
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args()

    path = ROOT / "datasets/securecodepairs" / f"{args.split}.jsonl"
    pairs = load_pairs(path)
    cases = cases_from_pairs(pairs)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    ram_baseline = ollama_rss_mb()
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
    except Exception as exc:
        raise SystemExit(f"Ollama not reachable: {exc}") from exc
    ollama_generate(args.model, SYSTEM, 'warmup. reply {"ok":true}', 0, args.timeout)
    ram_loaded = ollama_rss_mb()
    loaded = ollama_ps(args.model)
    print(f"[data] SecureCodePairs {args.split} {len(pairs)} pairs / {len(cases)} snippets  model={args.model}", flush=True)
    print(f"[perf] RAM baseline={ram_baseline} loaded={ram_loaded}", flush=True)

    records = []
    ram_peak = ram_loaded
    wall0 = time.time()
    for i, c in enumerate(cases, 1):
        user = PROMPT.format(language=c["language"], code=c["code"])
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
        gold_cwe = norm_cwe(c["gold_cwe"])
        rec = {
            "case_id": c["case_id"],
            "pair_id": c["pair_id"],
            "language": c["language"],
            "framework": c["framework"],
            "label": c["label"],
            "gold_cwe": c["gold_cwe"],
            "pred_cwe": pred_cwe,
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
            print(f"  [{i:3d}/{len(cases)}] {mark} {c['pair_id']} gold={c['gold_cwe']} pred={pred_cwe or '-'} {latency:.2f}s", flush=True)

    wall_s = round(time.time() - wall0, 3)
    overall = score_rows(records)
    summary = {
        "model": args.model,
        "dataset": "ismailtasdelen/SecureCodePairs",
        "split": args.split,
        "n_pairs": len(pairs),
        "n_snippets": len(records),
        "timestamp": ts,
        "detection": overall,
        "perf": {
            "e2e_latency_mean_s": mean([r["latency_s"] for r in records]),
            "e2e_latency_median_s": round(statistics.median(r["latency_s"] for r in records), 4) if records else None,
            "total_wall_s": wall_s,
            "prompt_tps_mean": mean([r.get("prompt_tps") for r in records]),
            "gen_tps_mean": mean([r.get("gen_tps") for r in records]),
            "ram_baseline_mb": ram_baseline,
            "ram_loaded_mb": ram_loaded,
            "ram_peak_mb": ram_peak,
            "ollama_size_mb": loaded.get("size_mb"),
        },
    }
    sum_path = OUT / f"scp_{args.split}_summary_{ts}.json"
    sum_path.write_text(json.dumps(summary, indent=2) + "\n")
    (OUT / "scp_summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    detail = OUT / f"scp_{args.split}_eval_{ts}.csv"
    fields = ["case_id", "pair_id", "language", "framework", "label", "gold_cwe", "pred_cwe",
              "gold_vuln", "pred_vuln", "cwe_correct", "latency_s", "prompt_tps", "gen_tps",
              "ram_rss_mb", "raw_output"]
    with detail.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(records)

    headline = {
        "model": args.model,
        "split": args.split,
        "n_pairs": len(pairs),
        "n_snippets": len(records),
        "detection_accuracy": overall["accuracy"],
        "detection_recall": overall["recall"],
        "detection_specificity": overall["specificity"],
        "cwe_accuracy": overall["cwe_accuracy"],
        "latency_mean_s": summary["perf"]["e2e_latency_mean_s"],
        "wall_s": wall_s,
        "ram_peak_mb": ram_peak,
        "gen_tps_mean": summary["perf"]["gen_tps_mean"],
    }
    head_path = OUT / "scp_headline.csv"
    with head_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(headline.keys()))
        w.writeheader()
        w.writerow(headline)

    print("\n" + "=" * 64)
    print(f"  SecureCodePairs {args.split}  |  {args.model}")
    print(f"  detection  acc={overall['accuracy']:.3f}  rec={overall['recall']:.3f}  spec={overall['specificity']:.3f}")
    print(f"  CWE        {overall['cwe_accuracy']:.3f}  ({overall['cwe_correct']}/{overall['n_vuln']})")
    print(f"  latency    mean={summary['perf']['e2e_latency_mean_s']}s  wall={wall_s}s")
    print(f"  RAM        loaded={ram_loaded}  peak={ram_peak}")
    print("=" * 64)
    print(f"[out] {detail}")
    print(f"[out] {head_path}")
    print(f"[out] {sum_path}")


if __name__ == "__main__":
    main()
