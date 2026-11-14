"""Paired analysis of the AllMode_AllModel_SmallSample run (dataset v4, 1911 samples).

Reads per-sample checkpoints, writes stats JSON and figures into ../Prompting_Paradigm_Benchmark_v1-0_figs/.
"""
import json, pathlib
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = pathlib.Path(__file__).resolve().parent
RUN = pathlib.Path(r"D:\4th-year\Senior-Project\benchmarks_full_scale\runs\AllMode_AllModel_SmallSample")
FIGS = HERE.parent / "Prompting_Paradigm_Benchmark_v1-0_figs"
FIGS.mkdir(exist_ok=True)

MODELS = {
    "qwen2.5-coder:7b": "qwen2_5-coder_7b",
    "Foundation-Sec-8B-Instruct": "Foundation-Sec-8B-Instruct",
    "llama3.1:8b": "llama3_1_8b",
    "drana-infinity-3b": "IHA089_drana-infinity-3b_3b",
}
MODES = ["zero-shot", "one-shot", "few-shot", "cot"]


def load(dirname, mode):
    p = RUN / "checkpoints" / dirname / mode / "checkpoint.json"
    return json.load(open(p, encoding="utf-8"))["completed_results"]


data = {m: {md: load(d, md) for md in MODES} for m, d in MODELS.items()}
out = {"per_run": {}, "paired_vs_zero_shot": {}}

for m in MODELS:
    ids = sorted(data[m]["zero-shot"])
    for md in MODES:
        r = data[m][md]
        n = len(r)
        correct = sum(r[i]["is_correct"] for i in r)
        safe = [i for i in r if r[i]["true_cwe"] == "CWE-NONE"]
        vuln = [i for i in r if r[i]["true_cwe"] != "CWE-NONE"]
        tn = sum(r[i]["predicted_cwe"] == "CWE-NONE" for i in safe)
        flagged_vuln = sum(r[i]["predicted_cwe"] not in ("CWE-NONE", "UNKNOWN", "ERROR") for i in vuln)
        unknown = sum(r[i]["predicted_cwe"] in ("UNKNOWN", "ERROR") for i in r)
        alpha = sum(str(r[i]["predicted_cwe"]).startswith("CWE-ALPHA") or str(r[i]["predicted_cwe"]).startswith("CWE-BETA") for i in r)
        vuln_exact = sum(r[i]["is_correct"] for i in vuln)
        out["per_run"][f"{m}|{md}"] = dict(
            n=n, exact_acc=correct / n, n_safe=len(safe), n_vuln=len(vuln),
            safe_specificity=tn / len(safe), vuln_flag_recall=flagged_vuln / len(vuln),
            vuln_exact_recall=vuln_exact / len(vuln),
            unknown_or_error=unknown, placeholder_labels=alpha,
            avg_latency=float(np.mean([r[i]["latency_sec"] for i in r])),
        )
    base = np.array([data[m]["zero-shot"][i]["is_correct"] for i in ids], dtype=float)
    for md in MODES[1:]:
        cur = np.array([data[m][md][i]["is_correct"] for i in ids], dtype=float)
        d = cur - base
        better = int((d > 0).sum()); worse = int((d < 0).sum())
        # exact McNemar-type test on discordant pairs (binary outcomes) + t-test + Wilcoxon
        t_p = float(stats.ttest_rel(cur, base).pvalue) if d.std() > 0 else 1.0
        try:
            w_p = float(stats.wilcoxon(cur, base, zero_method="wilcox").pvalue)
        except ValueError:
            w_p = 1.0
        out["paired_vs_zero_shot"][f"{m}|{md}"] = dict(
            delta_pp=float(d.mean() * 100), better=better, worse=worse, n=len(ids),
            t_p=t_p, wilcoxon_p=w_p)

json.dump(out, open(FIGS / "stats.json", "w"), indent=2)

# Figure 1: exact accuracy per model and mode
fig, ax = plt.subplots(figsize=(8, 4), dpi=200)
w = 0.2
for k, md in enumerate(MODES):
    vals = [out["per_run"][f"{m}|{md}"]["exact_acc"] * 100 for m in MODELS]
    ax.bar(np.arange(len(MODELS)) + (k - 1.5) * w, vals, w, label=md)
ax.set_xticks(range(len(MODELS))); ax.set_xticklabels(list(MODELS), fontsize=8)
ax.set_ylabel("Exact CWE accuracy (%)"); ax.legend(fontsize=8); ax.axhline(50, ls=":", c="gray", lw=0.8)
fig.tight_layout(); fig.savefig(FIGS / "fig1_accuracy.png"); plt.close(fig)

# Figure 2: safe-code specificity vs vulnerable flag recall
fig, ax = plt.subplots(figsize=(8, 4), dpi=200)
for k, md in enumerate(MODES):
    vals = [out["per_run"][f"{m}|{md}"]["safe_specificity"] * 100 for m in MODELS]
    ax.bar(np.arange(len(MODELS)) + (k - 1.5) * w, vals, w, label=md)
ax.set_xticks(range(len(MODELS))); ax.set_xticklabels(list(MODELS), fontsize=8)
ax.set_ylabel("Safe-patch samples labelled CWE-NONE (%)"); ax.legend(fontsize=8)
fig.tight_layout(); fig.savefig(FIGS / "fig2_safe_specificity.png"); plt.close(fig)

for k, v in out["per_run"].items():
    print(k, {a: (round(b, 4) if isinstance(b, float) else b) for a, b in v.items()})
print()
for k, v in out["paired_vs_zero_shot"].items():
    print(k, {a: (round(b, 5) if isinstance(b, float) else b) for a, b in v.items()})
