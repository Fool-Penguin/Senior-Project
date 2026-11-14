import json
from collections import defaultdict
import matplotlib.pyplot as plt
import numpy as np
import pathlib

ROOT = pathlib.Path(__file__).parent.parent
KB_PATH = ROOT / "datasets" / "combined" / "knowledge_base.jsonl"
OUT_PNG_LOCAL = ROOT / "visualizations" / "kb_cwe_languages_breakdown.png"
OUT_PNG_ARTIFACT = (
    pathlib.Path(
        r"C:\Users\Ongsa\.gemini\antigravity\brain\a3df399c-835d-4ed9-857c-5ccafcc0bc51"
    )
    / "kb_cwe_languages_breakdown.png"
)

counts = defaultdict(
    lambda: {"python": 0, "javascript": 0, "typescript": 0, "name": "", "has_example": 0}
)

with open(KB_PATH, "r", encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        cwe = d.get("cwe_id", "Unknown")
        lang = d.get("language", "unknown")
        name = d.get("cwe_name", "")
        counts[cwe][lang] += 1
        if d.get("example_sample_id"):
            counts[cwe]["has_example"] += 1
        if not counts[cwe]["name"]:
            counts[cwe]["name"] = name

# Sort CWEs: highest total first
sorted_kb = sorted(
    counts.items(),
    key=lambda x: (
        x[1]["python"] + x[1]["javascript"] + x[1]["typescript"],
        x[0]
    ),
    reverse=True
)

labels = []
py_vals = []
js_vals = []
ts_vals = []
totals = []
examples = []

# Friendly name simplifier
def simplify_name(name):
    if "SQL Injection" in name: return "SQL Injection"
    if "OS Command" in name or "Command Injection" in name: return "Command Injection"
    if "Cross-site Scripting" in name: return "XSS"
    if "Path" in name and "Limitation" in name: return "Path Traversal"
    if "Template Injection" in name: return "SSTI"
    if "Prototype" in name: return "Prototype Pollution"
    if "Direct and Indirect Prompt" in name: return "Prompt Injection"
    if "System Prompt Leakage" in name: return "Prompt Leakage"
    if "Sensitive Information Disclosure" in name: return "Info Disclosure"
    if "XML" in name: return "XXE Injection"
    if "Server-Side Request Forgery" in name: return "SSRF"
    if "Cross-Site Request Forgery" in name: return "CSRF"
    if "Deserialization" in name: return "Insecure Deserialization"
    if "Hard-coded" in name: return "Hardcoded Credentials"
    if "Weak Hash" in name: return "Weak Hash Algorithm"
    if "Weak PRNG" in name or "Weak" in name and "Cryptographically" in name: return "Weak Randomness"
    if "Broken or Risky" in name: return "Weak Cryptography"
    if "Error Message" in name: return "Information in Error"
    if "Regular Expression" in name: return "ReDoS"
    if "Authorization" in name: return "Missing Authorization"
    if "Redirection" in name: return "Open Redirect"
    if "Output Handling" in name: return "LLM Output Handling"
    if "Cryptographic Signature" in name: return "Signature Verification"
    if "Special Elements" in name: return "Special Elements Neutralization"
    if "Execution of Direct" in name: return "Eval Code Injection"
    if "Generation of Code" in name: return "Code Injection"
    return name[:22]

for cwe, data in sorted_kb:
    tot = data["python"] + data["javascript"] + data["typescript"]
    short_name = simplify_name(data["name"])
    labels.append(f"{cwe}: {short_name}")
    py_vals.append(data["python"])
    js_vals.append(data["javascript"])
    ts_vals.append(data["typescript"])
    totals.append(tot)
    examples.append(data["has_example"])

# Reverse for bottom-to-top display
labels.reverse()
py_vals.reverse()
js_vals.reverse()
ts_vals.reverse()
totals.reverse()
examples.reverse()

y = np.arange(len(labels))
height = 0.68

plt.style.use("dark_background")
fig, ax = plt.subplots(figsize=(15, 13), dpi=150)

# Stacked bar plot
p1 = ax.barh(y, py_vals, height, label="Python", color="#58a6ff", alpha=0.9)
p2 = ax.barh(y, js_vals, height, left=py_vals, label="JavaScript", color="#f0db4f", alpha=0.9)
p3 = ax.barh(y, ts_vals, height, left=np.array(py_vals) + np.array(js_vals), label="TypeScript", color="#3178c6", alpha=0.9)

# Annotate counts
for idx, (py, js, ts, tot, ex) in enumerate(zip(py_vals, js_vals, ts_vals, totals, examples)):
    py_txt = f"Py:{py}" if py > 0 else "Py:0"
    js_txt = f"JS:{js}"
    ts_txt = f"TS:{ts}"
    text_content = f"Total: {tot} ({py_txt}, {js_txt}, {ts_txt}) | Few-Shot Pairs: {ex}/{tot}"
    ax.text(
        tot + 0.15,
        idx,
        text_content,
        va="center",
        ha="left",
        fontsize=9,
        color="#e6edf3",
        fontweight="bold",
    )

ax.set_yticks(y)
ax.set_yticklabels(labels, fontsize=10, fontweight="medium")
ax.set_xlabel("Number of Knowledge Base Entries", fontsize=12, fontweight="bold", labelpad=12, color="#f0f6fc")
ax.set_title("CodeDEE Knowledge Base (RAG): Entries per Language across All 27 CWEs", fontsize=14, fontweight="bold", pad=18, color="#f0f6fc")
ax.set_xlim(0, 9.5)
ax.legend(loc="lower right", fontsize=11, framealpha=0.85, facecolor="#161b22", edgecolor="#30363d")
ax.grid(axis="x", linestyle="--", alpha=0.25, color="#8b949e")

# Dark background aesthetics
fig.patch.set_facecolor("#0d1117")
ax.set_facecolor("#161b22")
for spine in ax.spines.values():
    spine.set_color("#30363d")

plt.tight_layout()
plt.savefig(OUT_PNG_LOCAL, bbox_inches="tight")
OUT_PNG_ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(OUT_PNG_ARTIFACT, bbox_inches="tight")
print(f"Saved KB bar chart to {OUT_PNG_LOCAL} and {OUT_PNG_ARTIFACT}")

