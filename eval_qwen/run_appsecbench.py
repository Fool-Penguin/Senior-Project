#!/usr/bin/env python3
"""Score qwen2.5-coder:7b on AppSecBench test.jsonl — all six official tasks.

Hugging Face only. No 170-repo GHSA data.

  python3 eval_qwen/run_appsecbench.py
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import subprocess
import time
import urllib.request
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "datasets/appsecbench/test.jsonl"

SYSTEM = (
    "You are a senior application-security reviewer. "
    "Reply with a single JSON object and no markdown fences."
)

VULN_PROMPT = """\
Review this code for an application-security weakness.

Return ONLY JSON with these keys:
{{
  "vulnerable": true,
  "location": "short description of the buggy line or sink",
  "cwe": "CWE-XXX",
  "owasp": "A0X:2021",
  "severity": "Critical" | "High" | "Medium" | "Low",
  "cvss": 0.0,
  "explanation": "how it is exploited, 2-4 sentences",
  "secure_code": "rewritten safe code",
  "false_positive_probability": 0.0,
  "false_negative_probability": 0.0
}}

Language: {language}
Framework: {framework}

Code:
```
{code}
```
"""

SAFE_PROMPT = """\
Review this code for an application-security weakness.

Return ONLY JSON:
{{"vulnerable": false, "cwe": "", "owasp": "", "severity": "", "cvss": 0, "location": "", "explanation": "", "secure_code": "", "false_positive_probability": 0.0, "false_negative_probability": 0.0}}
If you believe it is still vulnerable, set "vulnerable" to true and fill cwe/owasp/severity.

Language: {language}
Code:
```
{code}
```
"""

CWE_RE = re.compile(r"CWE-\d+", re.I)
OWASP_RE = re.compile(r"A0?\d{1,2}:202[15]", re.I)
SEV_RE = re.compile(r"\b(Critical|High|Medium|Low)\b", re.I)
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
        "prompt_eval_s": ns_to_s(prompt_ns),
        "gen_eval_s": ns_to_s(gen_ns),
        "total_duration_s": ns_to_s(body.get("total_duration")),
        "prompt_tps": tps(prompt_n, prompt_ns),
        "gen_tps": tps(gen_n, gen_ns),
    }


def parse_json(text: str) -> dict:
    raw = text.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.S)
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


def tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9_]+", (text or "").lower()) if len(t) > 2}


def overlap_f1(pred: str, gold: str) -> float:
    a, b = tokens(pred), tokens(gold)
    if not a or not b:
        return 0.0
    hit = len(a & b)
    prec = hit / len(a)
    rec = hit / len(b)
    return round(2 * prec * rec / (prec + rec), 4) if prec + rec else 0.0


def norm_code(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def norm_owasp(s: str) -> str:
    s = (s or "").strip().upper().replace(" ", "")
    m = re.search(r"A0?(\d{1,2}):(202[15])", s)
    if not m:
        return s
    return f"A{int(m.group(1)):02d}:{m.group(2)}"


def to_float(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        m = re.search(r"\d+(?:\.\d+)?", str(v))
        return float(m.group(0)) if m else None


def load_rows(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def score_vuln(gold: dict, pred: dict) -> dict:
    flagged = bool(pred.get("vulnerable") is True or str(pred.get("vulnerable")).lower() == "true")
    pred_cwe = ""
    if pred.get("cwe"):
        m = CWE_RE.search(str(pred["cwe"]))
        pred_cwe = m.group(0).upper() if m else str(pred["cwe"]).upper()
    pred_owasp = norm_owasp(str(pred.get("owasp") or ""))
    gold_owasp = norm_owasp(str(gold.get("expected_owasp") or ""))
    pred_sev = ""
    if pred.get("severity"):
        m = SEV_RE.search(str(pred["severity"]))
        pred_sev = m.group(1).title() if m else str(pred["severity"]).title()
    gold_sev = str(gold.get("expected_severity") or "").title()
    pred_cvss = to_float(pred.get("cvss"))
    gold_cvss = to_float(gold.get("expected_cvss_score"))
    expl = str(pred.get("explanation") or "")
    loc = str(pred.get("location") or "")
    loc_hay = (loc + " " + expl).lower()
    loc_hit = any(
        tok.lower() in loc_hay
        for tok in re.findall(r"[A-Za-z_]{4,}", gold.get("vulnerable_code") or "")
        if tok.lower() not in {"function", "return", "const", "vulnerable", "secure"}
    )
    sec_pred = str(pred.get("secure_code") or "")
    sec_gold = gold.get("expected_secure_code") or gold.get("secure_code") or ""
    code_sim = round(SequenceMatcher(None, norm_code(sec_pred), norm_code(sec_gold)).ratio(), 4)
    fp_p, fn_p = to_float(pred.get("false_positive_probability")), to_float(pred.get("false_negative_probability"))
    fp_g = to_float(gold.get("expected_false_positive_probability"))
    fn_g = to_float(gold.get("expected_false_negative_probability"))
    return {
        "flagged": flagged,
        "pred_cwe": pred_cwe,
        "cwe_correct": pred_cwe == str(gold.get("expected_cwe") or "").upper(),
        "pred_owasp": pred_owasp,
        "owasp_correct": pred_owasp == gold_owasp and bool(gold_owasp),
        "pred_severity": pred_sev,
        "severity_correct": pred_sev == gold_sev,
        "pred_cvss": pred_cvss,
        "cvss_abs_err": round(abs(pred_cvss - gold_cvss), 3) if pred_cvss is not None and gold_cvss is not None else None,
        "cvss_within_1": (
            pred_cvss is not None and gold_cvss is not None and abs(pred_cvss - gold_cvss) <= 1.0
        ),
        "location": loc[:240],
        "location_mentions_code": loc_hit,
        "explanation_f1": overlap_f1(expl, gold.get("exploitability_explanation") or ""),
        "secure_code_similarity": code_sim,
        "secure_code_exact": norm_code(sec_pred) == norm_code(sec_gold) and bool(sec_gold),
        "pred_fp": fp_p,
        "pred_fn": fn_p,
        "fp_within_0_15": fp_p is not None and fp_g is not None and abs(fp_p - fp_g) <= 0.15,
        "fn_within_0_15": fn_p is not None and fn_g is not None and abs(fn_p - fn_g) <= 0.15,
        "raw_explanation": expl[:400],
        "raw_secure_code": sec_pred[:400],
    }


def mean(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    return round(statistics.mean(vals), 4) if vals else None


def rate(rows, key):
    if not rows:
        return 0.0
    return round(sum(1 for r in rows if r.get(key)) / len(rows), 4)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen2.5-coder:7b")
    parser.add_argument("--test", default=str(TEST))
    parser.add_argument("--out-dir", default=str(ROOT / "eval_qwen/results"))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()

    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
    except Exception as exc:
        raise SystemExit(f"Ollama not reachable: {exc}")

    golds = load_rows(Path(args.test))
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[data] AppSecBench test {len(golds)} records  model={args.model}", flush=True)

    ram_baseline = ollama_rss_mb()
    ollama_generate(args.model, SYSTEM, 'Return {"vulnerable": false}', args.temperature, args.timeout)
    ram_loaded = ollama_rss_mb()
    loaded = ollama_ps(args.model)
    print(f"[perf] RAM baseline={ram_baseline} loaded={ram_loaded} size={loaded.get('size_mb')}", flush=True)

    records = []
    ram_peak = ram_loaded
    wall0 = time.time()

    for i, g in enumerate(golds, 1):
        user = VULN_PROMPT.format(
            language=g.get("language") or "",
            framework=g.get("framework") or "",
            code=g.get("vulnerable_code") or "",
        )
        t0 = time.time()
        try:
            timing = ollama_generate(args.model, SYSTEM, user, args.temperature, args.timeout)
            parsed = parse_json(timing["text"])
            err = ""
        except Exception as exc:
            timing = {"text": f"ERROR: {exc}"}
            parsed = {}
            err = str(exc)
        latency = round(time.time() - t0, 3)
        ram_now = ollama_rss_mb()
        ram_peak = max(ram_peak, ram_now)
        sc = score_vuln(g, parsed)
        rec = {
            "benchmark_id": g.get("benchmark_id"),
            "language": g.get("language"),
            "framework": g.get("framework"),
            "gold_cwe": g.get("expected_cwe"),
            "gold_owasp": g.get("expected_owasp"),
            "gold_severity": g.get("expected_severity"),
            "gold_cvss": g.get("expected_cvss_score"),
            "latency_s": latency,
            "error": err,
            "raw_output": (timing.get("text") or "")[:500],
            "prompt_tokens": timing.get("prompt_tokens"),
            "gen_tokens": timing.get("gen_tokens"),
            "prompt_tps": timing.get("prompt_tps"),
            "gen_tps": timing.get("gen_tps"),
            "ram_rss_mb": ram_now,
            **sc,
        }
        records.append(rec)
        mark = "OK" if sc["cwe_correct"] else ("FG" if sc["flagged"] else "XX")
        if i % 5 == 0 or i <= 3:
            print(
                f"  [{i:3d}/{len(golds)}] {mark} gold={g.get('expected_cwe')} "
                f"pred={sc['pred_cwe'] or '-'} owasp={sc['owasp_correct']} "
                f"fix_sim={sc['secure_code_similarity']} {latency:.2f}s",
                flush=True,
            )

    # Detection on secure_code (false positives)
    fp_rows = []
    for i, g in enumerate(golds, 1):
        user = SAFE_PROMPT.format(language=g.get("language") or "", code=g.get("secure_code") or "")
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
        flagged = bool(parsed.get("vulnerable") is True or str(parsed.get("vulnerable")).lower() == "true")
        fp_rows.append({
            "benchmark_id": g.get("benchmark_id"),
            "flagged_secure": flagged,
            "latency_s": latency,
            "prompt_tokens": timing.get("prompt_tokens"),
            "gen_tokens": timing.get("gen_tokens"),
            "prompt_tps": timing.get("prompt_tps"),
            "gen_tps": timing.get("gen_tps"),
            "ram_rss_mb": ram_now,
            "raw_output": (timing.get("text") or "")[:240],
        })
        if i % 10 == 0:
            print(f"  [secure {i:3d}/{len(golds)}] flagged={flagged} {latency:.2f}s", flush=True)

    wall_s = round(time.time() - wall0, 3)
    tp = sum(1 for r in records if r["flagged"])
    fn = len(records) - tp
    fp = sum(1 for r in fp_rows if r["flagged_secure"])
    tn = len(fp_rows) - fp
    scored = tp + fp + tn + fn
    prec = tp / (tp + fp) if tp + fp else 0
    rec_ = tp / (tp + fn) if tp + fn else 0
    spec = tn / (tn + fp) if tn + fp else 0
    f1 = 2 * prec * rec_ / (prec + rec_) if prec + rec_ else 0

    lat = [r["latency_s"] for r in records] + [r["latency_s"] for r in fp_rows]
    summary = {
        "model": args.model,
        "dataset": "ismailtasdelen/AppSecBench",
        "split": "test",
        "n_records": len(golds),
        "n_calls": len(records) + len(fp_rows),
        "timestamp": ts,
        "task1_detection": {
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "accuracy": round((tp + tn) / scored, 4) if scored else 0,
            "precision": round(prec, 4),
            "recall": round(rec_, 4),
            "specificity": round(spec, 4),
            "f1": round(f1, 4),
            "location_mentions_code_rate": rate(records, "location_mentions_code"),
        },
        "task2_cwe_owasp": {
            "cwe_accuracy": rate(records, "cwe_correct"),
            "owasp_accuracy": rate(records, "owasp_correct"),
            "cwe_correct": sum(1 for r in records if r["cwe_correct"]),
            "owasp_correct": sum(1 for r in records if r["owasp_correct"]),
        },
        "task3_severity": {
            "severity_accuracy": rate(records, "severity_correct"),
            "cvss_within_1_rate": rate(records, "cvss_within_1"),
            "cvss_mae": mean([r["cvss_abs_err"] for r in records if r["cvss_abs_err"] is not None]),
        },
        "task4_explanation": {
            "mean_token_f1_vs_gold": mean([r["explanation_f1"] for r in records]),
        },
        "task5_secure_code": {
            "mean_similarity": mean([r["secure_code_similarity"] for r in records]),
            "exact_match_rate": rate(records, "secure_code_exact"),
        },
        "task6_fp_fn_priors": {
            "fp_within_0_15_rate": rate(records, "fp_within_0_15"),
            "fn_within_0_15_rate": rate(records, "fn_within_0_15"),
        },
        "perf": {
            "e2e_latency_mean_s": mean(lat),
            "e2e_latency_median_s": round(statistics.median(lat), 4) if lat else None,
            "snippets_per_sec": round(len(lat) / wall_s, 4) if wall_s else None,
            "total_wall_s": wall_s,
            "prompt_tps_mean": mean([r.get("prompt_tps") for r in records + fp_rows]),
            "gen_tps_mean": mean([r.get("gen_tps") for r in records + fp_rows]),
            "ram_baseline_mb": ram_baseline,
            "ram_loaded_mb": ram_loaded,
            "ram_peak_mb": ram_peak,
            "ollama_size_mb": loaded.get("size_mb"),
            "ollama_size_vram_mb": loaded.get("size_vram_mb"),
        },
    }

    sum_path = out_dir / f"appsecbench_summary_{ts}.json"
    sum_path.write_text(json.dumps(summary, indent=2) + "\n")
    latest = out_dir / "appsecbench_summary.json"
    latest.write_text(json.dumps(summary, indent=2) + "\n")

    detail_path = out_dir / f"appsecbench_eval_{ts}.csv"
    fields = [
        "benchmark_id", "language", "framework", "gold_cwe", "pred_cwe", "cwe_correct",
        "gold_owasp", "pred_owasp", "owasp_correct", "gold_severity", "pred_severity",
        "severity_correct", "gold_cvss", "pred_cvss", "cvss_abs_err", "cvss_within_1",
        "flagged", "location_mentions_code", "explanation_f1", "secure_code_similarity",
        "secure_code_exact", "fp_within_0_15", "fn_within_0_15", "latency_s",
        "prompt_tps", "gen_tps", "ram_rss_mb", "location", "raw_explanation", "raw_output",
    ]
    with detail_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(records)

    fp_path = out_dir / f"appsecbench_secure_detection_{ts}.csv"
    with fp_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fp_rows[0].keys()) if fp_rows else ["benchmark_id"])
        w.writeheader()
        w.writerows(fp_rows)

    headline = {
        "model": args.model,
        "n_test": len(golds),
        "detection_accuracy": summary["task1_detection"]["accuracy"],
        "detection_recall": summary["task1_detection"]["recall"],
        "detection_specificity": summary["task1_detection"]["specificity"],
        "cwe_accuracy": summary["task2_cwe_owasp"]["cwe_accuracy"],
        "owasp_accuracy": summary["task2_cwe_owasp"]["owasp_accuracy"],
        "severity_accuracy": summary["task3_severity"]["severity_accuracy"],
        "cvss_within_1": summary["task3_severity"]["cvss_within_1_rate"],
        "explanation_token_f1": summary["task4_explanation"]["mean_token_f1_vs_gold"],
        "secure_code_similarity": summary["task5_secure_code"]["mean_similarity"],
        "secure_code_exact": summary["task5_secure_code"]["exact_match_rate"],
        "fp_prior_close": summary["task6_fp_fn_priors"]["fp_within_0_15_rate"],
        "fn_prior_close": summary["task6_fp_fn_priors"]["fn_within_0_15_rate"],
        **summary["perf"],
    }
    head_path = out_dir / "appsecbench_headline.csv"
    with head_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(headline.keys()))
        w.writeheader()
        w.writerow(headline)

    t1, t2, t3 = summary["task1_detection"], summary["task2_cwe_owasp"], summary["task3_severity"]
    print("\n" + "=" * 64)
    print("  AppSecBench test  |  qwen2.5-coder:7b  |  all 6 tasks")
    print(f"  1 detection       acc={t1['accuracy']:.3f}  rec={t1['recall']:.3f}  spec={t1['specificity']:.3f}")
    print(f"  2 CWE / OWASP     cwe={t2['cwe_accuracy']:.3f}  owasp={t2['owasp_accuracy']:.3f}")
    print(f"  3 severity/CVSS   sev={t3['severity_accuracy']:.3f}  cvss±1={t3['cvss_within_1_rate']:.3f}")
    print(f"  4 explanation F1  {summary['task4_explanation']['mean_token_f1_vs_gold']}")
    print(f"  5 secure-code sim {summary['task5_secure_code']['mean_similarity']}  exact={summary['task5_secure_code']['exact_match_rate']}")
    print(f"  6 FP/FN ±0.15     fp={summary['task6_fp_fn_priors']['fp_within_0_15_rate']}  fn={summary['task6_fp_fn_priors']['fn_within_0_15_rate']}")
    print(f"  latency mean      {summary['perf']['e2e_latency_mean_s']}s  wall={wall_s}s")
    print(f"  RAM               loaded={ram_loaded}  peak={ram_peak}")
    print("=" * 64)
    print(f"[out] {detail_path}")
    print(f"[out] {head_path}")
    print(f"[out] {sum_path}")


if __name__ == "__main__":
    main()
