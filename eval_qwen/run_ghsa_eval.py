#!/usr/bin/env python3
"""Validate qwen2.5-coder:7b on GHSA parent/fix pairs from the 170 repos.

Main task: given a snippet, say if it is vulnerable, and if so which CWE.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import statistics
import subprocess
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAIRS = ROOT / "datasets/mining/ghsa_eval_pairs.json"
CATALOGUE = ROOT / "data/security_vulnerability_catalogue.yaml"

CATALOGUE_CWES = [
    "CWE-89", "CWE-78", "CWE-94", "CWE-1336", "CWE-943", "CWE-611", "CWE-77",
    "CWE-95", "CWE-79", "CWE-22", "CWE-601", "CWE-862", "CWE-352", "CWE-502",
    "CWE-1321", "CWE-915", "CWE-918", "CWE-798", "CWE-327", "CWE-338", "CWE-328",
    "CWE-347", "CWE-209", "CWE-1333", "CWE-1427", "CWE-200", "CWE-1426",
]

SYSTEM_PROMPT = (
    "You are a senior security engineer reviewing application source code. "
    "You only judge the snippet you are given."
)

USER_TEMPLATE = """\
Review this code snippet for a security vulnerability.

Allowed CWE labels (use one of these if vulnerable):
{cwes}

Reply with EXACTLY one line and nothing else:
- VULNERABLE CWE-XXX
- SAFE

Code:
```
{code}
```

Answer:"""

VERDICT_RE = re.compile(r"\b(SAFE|VULNERABLE)\b", re.I)
CWE_RE = re.compile(r"\bCWE-\d+\b", re.I)


def ns_to_s(value) -> float | None:
    if value is None:
        return None
    return round(int(value) / 1e9, 4)


def tps(count, duration_ns) -> float | None:
    if not count or not duration_ns:
        return None
    seconds = int(duration_ns) / 1e9
    if seconds <= 0:
        return None
    return round(int(count) / seconds, 2)


def ollama_rss_mb() -> float:
    """Sum RSS of Ollama server + runner processes (macOS/Linux)."""
    proc = subprocess.run(["ps", "-axo", "rss=,comm="], capture_output=True, text=True)
    total_kb = 0
    for line in proc.stdout.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        rss, comm = parts
        name = comm.lower()
        if "ollama" in name:
            try:
                total_kb += int(rss)
            except ValueError:
                continue
    return round(total_kb / 1024, 1)


def ollama_ps(model: str) -> dict:
    try:
        req = urllib.request.Request("http://localhost:11434/api/ps")
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
    except Exception:
        return {}
    for m in body.get("models") or []:
        if m.get("name") == model or m.get("model") == model:
            return {
                "size_bytes": m.get("size"),
                "size_vram_bytes": m.get("size_vram"),
                "size_mb": round((m.get("size") or 0) / 1024 / 1024, 1),
                "size_vram_mb": round((m.get("size_vram") or 0) / 1024 / 1024, 1),
                "context_length": (m.get("details") or {}).get("parameter_size"),
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
    total_ns = body.get("total_duration")
    load_ns = body.get("load_duration")
    return {
        "text": ((body.get("message") or {}).get("content") or "").strip(),
        "prompt_tokens": prompt_n,
        "gen_tokens": gen_n,
        "prompt_eval_s": ns_to_s(prompt_ns),
        "gen_eval_s": ns_to_s(gen_ns),
        "total_duration_s": ns_to_s(total_ns),
        "load_duration_s": ns_to_s(load_ns),
        "prompt_tps": tps(prompt_n, prompt_ns),
        "gen_tps": tps(gen_n, gen_ns),
    }


def parse_output(text: str) -> tuple[str, str]:
    """Return (VULNERABLE|SAFE|UNKNOWN, CWE-id or '')."""
    if not text:
        return "UNKNOWN", ""
    cwe_match = CWE_RE.search(text)
    cwe = cwe_match.group(0).upper() if cwe_match else ""
    verdict_match = VERDICT_RE.search(text)
    if verdict_match:
        label = verdict_match.group(1).upper()
    elif cwe:
        label = "VULNERABLE"
    else:
        return "UNKNOWN", ""
    if label == "SAFE":
        return "SAFE", ""
    return "VULNERABLE", cwe


def load_samples(path: Path, cap_openclaw: int, seed: int) -> list[dict]:
    data = json.loads(path.read_text())
    pairs = list(data["pairs"])
    rng = random.Random(seed)
    if cap_openclaw >= 0:
        claw = [p for p in pairs if p["repo"] == "openclaw/openclaw"]
        rest = [p for p in pairs if p["repo"] != "openclaw/openclaw"]
        rng.shuffle(claw)
        pairs = rest + claw[:cap_openclaw]
    samples = []
    for p in pairs:
        samples.append({
            "sample_id": p["ghsa_id"] + "_VULN",
            "ghsa_id": p["ghsa_id"],
            "repo": p["repo"],
            "file": p["file"],
            "cwe_id": p["cwe_id"],
            "true_label": "VULNERABLE",
            "code": p["vuln_snippet"],
            "extract": p.get("vuln_extract"),
        })
        samples.append({
            "sample_id": p["ghsa_id"] + "_FIXED",
            "ghsa_id": p["ghsa_id"],
            "repo": p["repo"],
            "file": p["file"],
            "cwe_id": p["cwe_id"],
            "true_label": "SAFE",
            "code": p["fixed_snippet"],
            "extract": p.get("fixed_extract"),
        })
    rng.shuffle(samples)
    return samples, len(pairs)


def metrics(rows: list[dict]) -> dict:
    tp = fp = tn = fn = unk = 0
    cwe_correct = cwe_total = 0
    joint = 0
    for r in rows:
        pred, true = r["predicted_label"], r["true_label"]
        if pred == "UNKNOWN":
            unk += 1
            continue
        if true == "VULNERABLE":
            if pred == "VULNERABLE":
                tp += 1
            else:
                fn += 1
            cwe_total += 1
            if r.get("predicted_cwe") == r["cwe_id"]:
                cwe_correct += 1
            if pred == "VULNERABLE" and r.get("predicted_cwe") == r["cwe_id"]:
                joint += 1
        else:
            if pred == "VULNERABLE":
                fp += 1
            else:
                tn += 1
                joint += 1
    scored = tp + fp + tn + fn
    acc = (tp + tn) / scored if scored else 0
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    spec = tn / (tn + fp) if tn + fp else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    return {
        "n": len(rows),
        "scored": scored,
        "unknown": unk,
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "specificity": round(spec, 4),
        "f1": round(f1, 4),
        "cwe_accuracy_on_vuln": round(cwe_correct / cwe_total, 4) if cwe_total else 0,
        "cwe_correct": cwe_correct,
        "cwe_total": cwe_total,
        "joint_correct": joint,
        "joint_accuracy": round(joint / scored, 4) if scored else 0,
    }


def paired_stats(rows: list[dict]) -> dict:
    by = {}
    for r in rows:
        by.setdefault(r["ghsa_id"], {})[r["true_label"]] = r
    both = 0
    parent_flagged = 0
    fix_cleared = 0
    ideal = 0
    for pair in by.values():
        if "VULNERABLE" not in pair or "SAFE" not in pair:
            continue
        both += 1
        v, s = pair["VULNERABLE"], pair["SAFE"]
        if v["predicted_label"] == "VULNERABLE":
            parent_flagged += 1
        if s["predicted_label"] == "SAFE":
            fix_cleared += 1
        if (
            v["predicted_label"] == "VULNERABLE"
            and s["predicted_label"] == "SAFE"
            and v.get("predicted_cwe") == v["cwe_id"]
        ):
            ideal += 1
    return {
        "pairs": both,
        "parent_flagged": parent_flagged,
        "fix_cleared": fix_cleared,
        "ideal_parent_vuln_cwe_and_fix_safe": ideal,
        "ideal_rate": round(ideal / both, 4) if both else 0,
        "parent_flagged_rate": round(parent_flagged / both, 4) if both else 0,
        "fix_cleared_rate": round(fix_cleared / both, 4) if both else 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen2.5-coder:7b")
    parser.add_argument("--pairs", default=str(PAIRS))
    parser.add_argument("--out-dir", default=str(ROOT / "eval_qwen/results"))
    parser.add_argument("--cap-openclaw", type=int, default=10,
                        help="Max OpenClaw pairs to keep (-1 = no cap)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
    except Exception as exc:
        raise SystemExit(f"Ollama not reachable: {exc}")

    samples, n_pairs = load_samples(Path(args.pairs), args.cap_openclaw, args.seed)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pred_path = out_dir / f"predictions_ghsa_{ts}.jsonl"
    print(f"[data] {n_pairs} pairs -> {len(samples)} snippets  model={args.model}", flush=True)

    ram_baseline_mb = ollama_rss_mb()
    print(f"[perf] RAM before load: {ram_baseline_mb} MB", flush=True)
    print("[perf] warmup (loads model, excluded from metrics)", flush=True)
    try:
        ollama_generate(
            args.model, SYSTEM_PROMPT, "Reply with exactly: SAFE", args.temperature, args.timeout
        )
    except Exception as exc:
        raise SystemExit(f"warmup failed: {exc}")
    ram_loaded_mb = ollama_rss_mb()
    ollama_loaded = ollama_ps(args.model)
    print(
        f"[perf] RAM after load: {ram_loaded_mb} MB  ollama size={ollama_loaded.get('size_mb')} MB "
        f"vram={ollama_loaded.get('size_vram_mb')} MB",
        flush=True,
    )

    cwe_list = " ".join(CATALOGUE_CWES)
    predictions = []
    ram_peak_mb = ram_loaded_mb
    wall0 = time.time()
    with pred_path.open("w", encoding="utf-8") as fh:
        for i, sample in enumerate(samples, 1):
            user = USER_TEMPLATE.format(cwes=cwe_list, code=sample["code"])
            t0 = time.time()
            timing = {}
            try:
                timing = ollama_generate(args.model, SYSTEM_PROMPT, user, args.temperature, args.timeout)
                raw = timing["text"]
                pred, cwe = parse_output(raw)
                err = ""
            except Exception as exc:
                raw, pred, cwe, err = f"ERROR: {exc}", "UNKNOWN", "", str(exc)
            latency = round(time.time() - t0, 3)
            ram_now = ollama_rss_mb()
            ram_peak_mb = max(ram_peak_mb, ram_now)
            rec = {
                **{k: v for k, v in sample.items() if k != "code"},
                "predicted_label": pred,
                "predicted_cwe": cwe,
                "correct_binary": pred == sample["true_label"],
                "correct_cwe": (
                    sample["true_label"] == "VULNERABLE" and pred == "VULNERABLE" and cwe == sample["cwe_id"]
                ) or (sample["true_label"] == "SAFE" and pred == "SAFE"),
                "raw_output": raw[:400],
                "latency_s": latency,
                "e2e_s": timing.get("total_duration_s"),
                "prompt_eval_s": timing.get("prompt_eval_s"),
                "gen_eval_s": timing.get("gen_eval_s"),
                "load_duration_s": timing.get("load_duration_s"),
                "prompt_tokens": timing.get("prompt_tokens"),
                "gen_tokens": timing.get("gen_tokens"),
                "prompt_tps": timing.get("prompt_tps"),
                "gen_tps": timing.get("gen_tps"),
                "ram_rss_mb": ram_now,
                "error": err,
            }
            predictions.append(rec)
            fh.write(json.dumps(rec) + "\n")
            fh.flush()
            mark = "OK" if rec["correct_binary"] else "XX"
            if i % 5 == 0 or i <= 3:
                print(
                    f"  [{i:3d}/{len(samples)}] {mark} true={sample['true_label']:10s} "
                    f"pred={pred:10s} cwe={cwe or '-':10s} gold={sample['cwe_id']}  "
                    f"{latency:.2f}s gen_tps={timing.get('gen_tps')}",
                    flush=True,
                )
    wall_s = round(time.time() - wall0, 3)

    m = metrics(predictions)
    pstats = paired_stats(predictions)
    by_cwe = []
    for cwe, _ in Counter(r["cwe_id"] for r in predictions if r["true_label"] == "VULNERABLE").most_common():
        sub = [r for r in predictions if r["cwe_id"] == cwe]
        row = {"cwe_id": cwe, **metrics(sub)}
        by_cwe.append(row)

    def mean_of(key):
        vals = [r[key] for r in predictions if isinstance(r.get(key), (int, float))]
        return round(statistics.mean(vals), 4) if vals else None

    def median_of(key):
        vals = [r[key] for r in predictions if isinstance(r.get(key), (int, float))]
        return round(statistics.median(vals), 4) if vals else None

    lat = [r["latency_s"] for r in predictions if isinstance(r.get("latency_s"), (int, float))]
    perf = {
        "e2e_latency_mean_s": round(statistics.mean(lat), 4) if lat else None,
        "e2e_latency_median_s": round(statistics.median(lat), 4) if lat else None,
        "e2e_latency_p90_s": round(sorted(lat)[int(0.9 * (len(lat) - 1))], 4) if lat else None,
        "e2e_latency_min_s": round(min(lat), 4) if lat else None,
        "e2e_latency_max_s": round(max(lat), 4) if lat else None,
        "ollama_e2e_mean_s": mean_of("e2e_s"),
        "prompt_eval_mean_s": mean_of("prompt_eval_s"),
        "gen_eval_mean_s": mean_of("gen_eval_s"),
        "prompt_tokens_mean": mean_of("prompt_tokens"),
        "gen_tokens_mean": mean_of("gen_tokens"),
        "prompt_tps_mean": mean_of("prompt_tps"),
        "gen_tps_mean": mean_of("gen_tps"),
        "snippets_per_sec": round(len(predictions) / wall_s, 4) if wall_s else None,
        "total_wall_s": wall_s,
        "ram_baseline_mb": ram_baseline_mb,
        "ram_loaded_mb": ram_loaded_mb,
        "ram_peak_mb": ram_peak_mb,
        "ram_mean_mb": mean_of("ram_rss_mb"),
        "ollama_size_mb": ollama_loaded.get("size_mb"),
        "ollama_size_vram_mb": ollama_loaded.get("size_vram_mb"),
    }

    summary = {
        "model": args.model,
        "timestamp": ts,
        "cap_openclaw": args.cap_openclaw,
        "n_pairs": n_pairs,
        "n_snippets": len(samples),
        **m,
        "paired": pstats,
        "perf": perf,
        "by_cwe": by_cwe,
        "repos": sorted({r["repo"] for r in predictions}),
    }
    sum_path = out_dir / f"summary_ghsa_{ts}.json"
    sum_path.write_text(json.dumps(summary, indent=2) + "\n")

    csv_path = out_dir / f"qwen_ghsa_eval_{ts}.csv"
    fields = [
        "sample_id", "ghsa_id", "repo", "file", "true_label", "cwe_id",
        "predicted_label", "predicted_cwe", "correct_binary", "correct_cwe",
        "latency_s", "e2e_s", "prompt_eval_s", "gen_eval_s",
        "prompt_tokens", "gen_tokens", "prompt_tps", "gen_tps", "ram_rss_mb",
        "extract", "raw_output",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(predictions)

    headline_path = out_dir / f"qwen_ghsa_headline_{ts}.csv"
    latest_path = out_dir / "qwen_ghsa_headline.csv"
    headline = {
        "model": args.model,
        "n_pairs": n_pairs,
        "n_snippets": len(samples),
        "openclaw_cap": args.cap_openclaw,
        "binary_accuracy": m["accuracy"],
        "precision": m["precision"],
        "recall": m["recall"],
        "specificity": m["specificity"],
        "cwe_accuracy_on_vulnerable": m["cwe_accuracy_on_vuln"],
        "joint_accuracy": m["joint_accuracy"],
        "parent_flagged_rate": pstats["parent_flagged_rate"],
        "fix_cleared_rate": pstats["fix_cleared_rate"],
        "ideal_pair_rate": pstats["ideal_rate"],
        "tp": m["tp"], "fp": m["fp"], "tn": m["tn"], "fn": m["fn"],
        "cwe_correct": m["cwe_correct"], "cwe_total": m["cwe_total"],
        **perf,
    }
    for path in (headline_path, latest_path):
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(headline.keys()))
            w.writeheader()
            w.writerow(headline)

    cwe_csv = out_dir / f"qwen_ghsa_by_cwe_{ts}.csv"
    with cwe_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "cwe_id", "n", "tp", "fp", "tn", "fn", "accuracy", "recall",
            "specificity", "cwe_accuracy_on_vuln", "joint_accuracy",
        ])
        w.writeheader()
        for row in by_cwe:
            w.writerow({
                "cwe_id": row["cwe_id"],
                "n": row["n"],
                "tp": row["tp"], "fp": row["fp"], "tn": row["tn"], "fn": row["fn"],
                "accuracy": row["accuracy"],
                "recall": row["recall"],
                "specificity": row["specificity"],
                "cwe_accuracy_on_vuln": row["cwe_accuracy_on_vuln"],
                "joint_accuracy": row["joint_accuracy"],
            })

    repo_csv = out_dir / f"qwen_ghsa_by_repo_{ts}.csv"
    by_repo: dict[str, list] = {}
    for r in predictions:
        by_repo.setdefault(r["repo"], []).append(r)
    with repo_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "repo", "n_snippets", "n_vuln", "binary_accuracy",
            "cwe_accuracy_on_vuln", "joint_accuracy", "tp", "fp", "tn", "fn",
        ])
        w.writeheader()
        for repo, rs in sorted(by_repo.items(), key=lambda kv: -len(kv[1])):
            sm = metrics(rs)
            w.writerow({
                "repo": repo,
                "n_snippets": sm["n"],
                "n_vuln": sm["cwe_total"],
                "binary_accuracy": sm["accuracy"],
                "cwe_accuracy_on_vuln": sm["cwe_accuracy_on_vuln"],
                "joint_accuracy": sm["joint_accuracy"],
                "tp": sm["tp"], "fp": sm["fp"], "tn": sm["tn"], "fn": sm["fn"],
            })
    claw_m = metrics([r for r in predictions if r["repo"] == "openclaw/openclaw"])
    rest_m = metrics([r for r in predictions if r["repo"] != "openclaw/openclaw"])

    print("\n" + "=" * 64)
    print(f"  model              {args.model}")
    print(f"  pairs / snippets   {n_pairs} / {len(samples)}")
    print(f"  binary accuracy    {m['accuracy']:.4f}   (P={m['precision']:.4f} R={m['recall']:.4f} spec={m['specificity']:.4f})")
    print(f"  CWE acc on vuln    {m['cwe_accuracy_on_vuln']:.4f}   ({m['cwe_correct']}/{m['cwe_total']})")
    print(f"  joint accuracy     {m['joint_accuracy']:.4f}   (SAFE ok, or VULN+correct CWE)")
    print(f"  paired ideal       {pstats['ideal_rate']:.4f}   parent flagged+CWE and fix SAFE")
    print(f"  parent flagged     {pstats['parent_flagged_rate']:.4f}")
    print(f"  fix cleared        {pstats['fix_cleared_rate']:.4f}")
    print(f"  e2e latency        mean={perf['e2e_latency_mean_s']}s  median={perf['e2e_latency_median_s']}s  p90={perf['e2e_latency_p90_s']}s")
    print(f"  tokens/sec         prompt={perf['prompt_tps_mean']}  gen={perf['gen_tps_mean']}")
    print(f"  speed              {perf['snippets_per_sec']} snippets/s  wall={perf['total_wall_s']}s")
    print(f"  RAM MB             baseline={perf['ram_baseline_mb']}  loaded={perf['ram_loaded_mb']}  peak={perf['ram_peak_mb']}")
    print(f"  openclaw           n={claw_m['n']} bin={claw_m['accuracy']:.4f} cwe={claw_m['cwe_accuracy_on_vuln']:.4f}")
    print(f"  other repos        n={rest_m['n']} bin={rest_m['accuracy']:.4f} cwe={rest_m['cwe_accuracy_on_vuln']:.4f}")
    print("=" * 64)
    print(f"[out] {pred_path}")
    print(f"[out] {sum_path}")
    print(f"[out] {csv_path}")
    print(f"[out] {cwe_csv}")
    print(f"[out] {repo_csv}")
    print(f"[out] {headline_path}")


if __name__ == "__main__":
    main()
