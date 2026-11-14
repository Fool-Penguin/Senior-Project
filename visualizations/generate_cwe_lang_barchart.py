import json
from collections import defaultdict
import matplotlib.pyplot as plt
import numpy as np
import pathlib

ROOT = pathlib.Path(__file__).parent.parent
DATASET_PATH = ROOT / "datasets" / "combined" / "dataset.jsonl"
OUT_PNG_LOCAL = ROOT / "visualizations" / "cwe_languages_breakdown.png"
OUT_PNG_ARTIFACT = (
    pathlib.Path(
        r"C:\Users\Ongsa\.gemini\antigravity\brain\a3df399c-835d-4ed9-857c-5ccafcc0bc51"
    )
    / "cwe_languages_breakdown.png"
)

counts = defaultdict(
    lambda: {"python": 0, "javascript": 0, "typescript": 0, "name": ""}
)
with open(DATASET_PATH, "r", encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        cwe = d.get("cwe_id", "Unknown")
        lang = d.get("language", "unknown")
        name = d.get("cwe_name", "")
        counts[cwe][lang] += 1
        if not counts[cwe]["name"]:
            counts[cwe]["name"] = name

# Sort and pick top 25 CWEs
sorted_cwes = sorted(
    counts.items(),
    key=lambda x: x[1]["python"] + x[1]["javascript"] + x[1]["typescript"],
    reverse=True,
)[:25]

labels = []
py_vals = []
js_vals = []
ts_vals = []
totals = []

for cwe, data in sorted_cwes:
    tot = data["python"] + data["javascript"] + data["typescript"]
    short_name = (
        data["name"][:22] + "..." if len(data["name"]) > 25 else data["name"]
    )
    labels.append(f"{cwe}: {short_name}")
    py_vals.append(data["python"])
    js_vals.append(data["javascript"])
    ts_vals.append(data["typescript"])
    totals.append(tot)

# Reverse so largest is at the top
labels.reverse()
py_vals.reverse()
js_vals.reverse()
ts_vals.reverse()
totals.reverse()

y = np.arange(len(labels))
height = 0.68

plt.style.use("dark_background")
fig, ax = plt.subplots(figsize=(15, 12), dpi=150)

# Stacked horizontal bar chart
p1 = ax.barh(y, py_vals, height, label="Python", color="#58a6ff", alpha=0.9)
p2 = ax.barh(
    y,
    js_vals,
    height,
    left=py_vals,
    label="JavaScript",
    color="#f0db4f",
    alpha=0.9,
)
p3 = ax.barh(
    y,
    ts_vals,
    height,
    left=np.array(py_vals) + np.array(js_vals),
    label="TypeScript",
    color="#3178c6",
    alpha=0.9,
)

# Annotate total and per-language count on bars
for idx, (py, js, ts, tot) in enumerate(
    zip(py_vals, js_vals, ts_vals, totals)
):
    ax.text(
        tot + 2,
        idx,
        f"Total: {tot} (Py:{py}, JS:{js}, TS:{ts})",
        va="center",
        ha="left",
        fontsize=9,
        color="#e6edf3",
        fontweight="bold",
    )

ax.set_yticks(y)
ax.set_yticklabels(labels, fontsize=10, fontweight="medium")
ax.set_xlabel(
    "Number of Vulnerable Samples",
    fontsize=12,
    fontweight="bold",
    labelpad=12,
    color="#f0f6fc",
)
ax.set_title(
    "CodeDEE Evaluation Dataset: Sample Distribution per Language across Top 25 CWEs",
    fontsize=14,
    fontweight="bold",
    pad=18,
    color="#f0f6fc",
)
ax.set_xlim(0, max(totals) + 55)
ax.legend(
    loc="lower right",
    fontsize=11,
    framealpha=0.85,
    facecolor="#161b22",
    edgecolor="#30363d",
)
ax.grid(axis="x", linestyle="--", alpha=0.25, color="#8b949e")

# Styling background
fig.patch.set_facecolor("#0d1117")
ax.set_facecolor("#161b22")
for spine in ax.spines.values():
    spine.set_color("#30363d")

plt.tight_layout()
plt.savefig(OUT_PNG_LOCAL, bbox_inches="tight")
OUT_PNG_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(OUT_PNG_ARTIFACT, bbox_inches="tight")
print(f"Saved PNG to {OUT_PNG_LOCAL} and {OUT_PNG_ARTIFACT}")

