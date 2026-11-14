"""
Integrated Data Visualization Generator for CodeDEE Evaluation:
- datasets/combined/dataset.jsonl (1,208 test samples for Local LLM evaluation)
- datasets/combined/knowledge_base.jsonl (83 entries for Local RAG / Knowledge Base)

Generates:
- visualizations/codedee_evaluation_rag_dashboard.html
- C:/Users/Ongsa/.gemini/antigravity/brain/a3df399c-835d-4ed9-857c-5ccafcc0bc51/codedee_evaluation_rag_dashboard.html
"""

import json
import math
import pathlib
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).parent.parent
VIS_DIR = ROOT / "visualizations"
VIS_DIR.mkdir(parents=True, exist_ok=True)

ARTIFACT_DIR = pathlib.Path(r"C:\Users\Ongsa\.gemini\antigravity\brain\a3df399c-835d-4ed9-857c-5ccafcc0bc51")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

DATASET_PATH = ROOT / "datasets" / "combined" / "dataset.jsonl"
KB_PATH = ROOT / "datasets" / "combined" / "knowledge_base.jsonl"
SPLIT_SUMMARY_PATH = ROOT / "datasets" / "combined" / "split_summary.json"


def parse_cvss31(v):
    if not v or not isinstance(v, str):
        return None, "Unspecified"
    parts = dict(p.split(":", 1) for p in v.strip().split("/") if ":" in p)
    av_map = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}
    ac_map = {"L": 0.77, "H": 0.44}
    pr_map = {
        "U": {"N": 0.85, "L": 0.62, "H": 0.27},
        "C": {"N": 0.85, "L": 0.68, "H": 0.50},
    }
    ui_map = {"N": 0.85, "R": 0.62}
    scope_changed = parts.get("S") == "C"
    s_key = "C" if scope_changed else "U"
    c_map = {"H": 0.56, "L": 0.22, "N": 0.0}
    i_map = {"H": 0.56, "L": 0.22, "N": 0.0}
    a_map = {"H": 0.56, "L": 0.22, "N": 0.0}

    try:
        av = av_map[parts["AV"]]
        ac = ac_map[parts["AC"]]
        pr = pr_map[s_key][parts["PR"]]
        ui = ui_map[parts["UI"]]
        c = c_map[parts["C"]]
        i = i_map[parts["I"]]
        a = a_map[parts["A"]]
    except KeyError:
        return None, "Invalid"

    iss = 1.0 - ((1.0 - c) * (1.0 - i) * (1.0 - a))
    impact = (
        (7.52 * (iss - 0.029) - 3.25 * ((iss - 0.02) ** 15))
        if scope_changed
        else (6.42 * iss)
    )
    exploitability = 8.22 * av * ac * pr * ui
    if impact <= 0:
        base_score = 0.0
    else:
        base_score = min(
            10.0, (1.08 if scope_changed else 1.0) * (impact + exploitability)
        )

    int_val = round(base_score * 100000)
    score = (
        (int_val / 100000.0)
        if int_val % 10000 == 0
        else (((int_val // 10000) + 1) / 10.0)
    )

    if score == 0.0:
        r = "None"
    elif score <= 3.9:
        r = "Low"
    elif score <= 6.9:
        r = "Medium"
    elif score <= 8.9:
        r = "High"
    else:
        r = "Critical"
    return score, r


print("Loading dataset...")
dataset_samples = []
with open(DATASET_PATH, "r", encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        score, risk = parse_cvss31(d.get("cvss_v31_vector"))
        d["calculated_cvss"] = score
        d["calculated_risk"] = risk
        dataset_samples.append(d)

print(f"Loaded {len(dataset_samples)} dataset samples.")

print("Loading knowledge base...")
kb_entries = []
with open(KB_PATH, "r", encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        score, risk = parse_cvss31(d.get("cvss_v31_vector"))
        d["calculated_cvss"] = score
        d["calculated_risk"] = risk
        kb_entries.append(d)

print(f"Loaded {len(kb_entries)} KB entries.")

# Summary calculations
ds_langs = Counter(s["language"] for s in dataset_samples)
ds_risks = Counter(s["calculated_risk"] for s in dataset_samples)
ds_cwes = Counter(f"{s['cwe_id']}: {s['cwe_name']}" for s in dataset_samples)
ds_splits = Counter(s.get("split_reason", "unknown") for s in dataset_samples)
ds_owasp = Counter(
    s.get("owasp_category") or "Uncategorized" for s in dataset_samples
)

# Detailed Language Breakdown per CWE
cwe_lang_breakdown = defaultdict(lambda: {"python": 0, "javascript": 0, "typescript": 0, "name": ""})
for s in dataset_samples:
    cwe = s.get("cwe_id", "Unknown")
    l = s.get("language", "unknown")
    cwe_lang_breakdown[cwe][l] += 1
    if not cwe_lang_breakdown[cwe]["name"]:
        cwe_lang_breakdown[cwe]["name"] = s.get("cwe_name", "")

# Sort top 15 CWEs by total samples
top_15_cwes_sorted = sorted(
    cwe_lang_breakdown.items(),
    key=lambda x: x[1]["python"] + x[1]["javascript"] + x[1]["typescript"],
    reverse=True
)[:15]

top_cwe_bar_labels = [f"{cwe} ({data['name'][:18]}...)" for cwe, data in top_15_cwes_sorted]
top_cwe_bar_py = [data["python"] for cwe, data in top_15_cwes_sorted]
top_cwe_bar_js = [data["javascript"] for cwe, data in top_15_cwes_sorted]
top_cwe_bar_ts = [data["typescript"] for cwe, data in top_15_cwes_sorted]

kb_langs = Counter(k["language"] for k in kb_entries)
kb_risks = Counter(k["calculated_risk"] for k in kb_entries)
kb_cwes = Counter(f"{k['cwe_id']}: {k['cwe_name']}" for k in kb_entries)
kb_examples = Counter(bool(k.get("example_sample_id")) for k in kb_entries)

# Detailed Language Breakdown for KB
kb_cwe_lang_breakdown = defaultdict(lambda: {"python": 0, "javascript": 0, "typescript": 0, "name": ""})
for k in kb_entries:
    cwe = k.get("cwe_id", "Unknown")
    l = k.get("language", "unknown")
    kb_cwe_lang_breakdown[cwe][l] += 1
    if not kb_cwe_lang_breakdown[cwe]["name"]:
        kb_cwe_lang_breakdown[cwe]["name"] = k.get("cwe_name", "")

kb_cwes_sorted = sorted(
    kb_cwe_lang_breakdown.items(),
    key=lambda x: (x[1]["python"] + x[1]["javascript"] + x[1]["typescript"], x[0]),
    reverse=True
)

kb_cwe_bar_labels = [f"{cwe} ({data['name'][:18]}...)" for cwe, data in kb_cwes_sorted]
kb_cwe_bar_py = [data["python"] for cwe, data in kb_cwes_sorted]
kb_cwe_bar_js = [data["javascript"] for cwe, data in kb_cwes_sorted]
kb_cwe_bar_ts = [data["typescript"] for cwe, data in kb_cwes_sorted]

# Build Coverage Matrix by Catalogue ID and Language
# Collect all unique catalogue IDs
all_cat_ids = set(k["catalogue_id"] for k in kb_entries)
for s in dataset_samples:
    cid = s.get("catalogue_id")
    if cid:
        all_cat_ids.add(cid)

all_cat_ids = sorted(list(all_cat_ids))

matrix_data = []
for cid in all_cat_ids:
    # Find metadata from KB or dataset
    sample_kb = next(
        (k for k in kb_entries if k.get("catalogue_id") == cid), None
    )
    sample_ds = next(
        (s for s in dataset_samples if s.get("catalogue_id") == cid), None
    )

    cwe_id = (
        sample_kb.get("cwe_id")
        if sample_kb
        else (sample_ds.get("cwe_id") if sample_ds else "-")
    )
    cwe_name = (
        sample_kb.get("cwe_name")
        if sample_kb
        else (sample_ds.get("cwe_name") if sample_ds else "-")
    )
    owasp = (
        sample_kb.get("owasp_category")
        if sample_kb
        else (sample_ds.get("owasp_category") if sample_ds else "-")
    )
    risk = (
        sample_kb.get("calculated_risk")
        if sample_kb
        else (sample_ds.get("calculated_risk") if sample_ds else "Unknown")
    )

    row = {
        "catalogue_id": cid,
        "cwe_id": cwe_id,
        "cwe_name": cwe_name,
        "owasp_category": owasp,
        "risk_level": risk,
        "py_kb": any(
            k["catalogue_id"] == cid and k["language"] == "python"
            for k in kb_entries
        ),
        "js_kb": any(
            k["catalogue_id"] == cid and k["language"] == "javascript"
            for k in kb_entries
        ),
        "ts_kb": any(
            k["catalogue_id"] == cid and k["language"] == "typescript"
            for k in kb_entries
        ),
        "py_ds": sum(
            1
            for s in dataset_samples
            if s.get("catalogue_id") == cid and s["language"] == "python"
        ),
        "js_ds": sum(
            1
            for s in dataset_samples
            if s.get("catalogue_id") == cid and s["language"] == "javascript"
        ),
        "ts_ds": sum(
            1
            for s in dataset_samples
            if s.get("catalogue_id") == cid and s["language"] == "typescript"
        ),
    }
    row["total_ds"] = row["py_ds"] + row["js_ds"] + row["ts_ds"]
    matrix_data.append(row)

# Also account for unmapped dataset samples
unmapped_samples = [s for s in dataset_samples if not s.get("catalogue_id")]
unmapped_cwes = Counter(
    f"{s['cwe_id']}: {s['cwe_name']}" for s in unmapped_samples
)

print(f"Matrix computed for {len(matrix_data)} catalogue IDs.")
print(f"Unmapped samples count: {len(unmapped_samples)}")

# Prepare serialized data for UI tables (strip heavy code to keep HTML fast and light, keep snippets)
table_dataset_samples = []
for s in dataset_samples:
    orig_snippet = s.get("original_code", "")[:280] + (
        "..." if len(s.get("original_code", "")) > 280 else ""
    )
    fixed_snippet = s.get("fixed_code", "")[:280] + (
        "..." if len(s.get("fixed_code", "")) > 280 else ""
    )
    table_dataset_samples.append(
        {
            "id": s.get("sample_id"),
            "lang": s.get("language"),
            "cwe_id": s.get("cwe_id"),
            "cwe_name": s.get("cwe_name"),
            "catalogue_id": s.get("catalogue_id") or "Unmapped",
            "owasp": s.get("owasp_category") or "-",
            "cvss": s.get("calculated_cvss"),
            "risk": s.get("calculated_risk"),
            "split_reason": s.get("split_reason"),
            "code_snippet": orig_snippet,
            "fixed_snippet": fixed_snippet,
        }
    )

table_kb_entries = []
for k in kb_entries:
    table_kb_entries.append(
        {
            "kb_id": k.get("kb_id"),
            "catalogue_id": k.get("catalogue_id"),
            "lang": k.get("language"),
            "cwe_id": k.get("cwe_id"),
            "cwe_name": k.get("cwe_name"),
            "owasp": k.get("owasp_category") or "-",
            "risk": k.get("calculated_risk"),
            "has_example": bool(k.get("example_sample_id")),
            "source_pat": (k.get("source_pattern") or "")[:150],
            "sink_pat": (k.get("sink_pattern") or "")[:150],
            "sanitizer_pat": (k.get("sanitizer_pattern") or "")[:150],
        }
    )

def safe_json_dumps(obj):
    return json.dumps(obj).replace("<", "\\u003c").replace(">", "\\u003e")


# Prepare HTML Template
html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CodeDEE: LLM Evaluation Dataset & Knowledge Base RAG Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
  <style>
    :root {{
      --bg-primary: #0d1117;
      --bg-secondary: #161b22;
      --bg-card: #21262d;
      --border-color: #30363d;
      --text-primary: #f0f6fc;
      --text-secondary: #8b949e;
      --text-muted: #6e7681;
      --accent-blue: #58a6ff;
      --accent-green: #3fb950;
      --accent-purple: #bc8cff;
      --accent-orange: #d29922;
      --accent-red: #f85149;
      --accent-cyan: #39c5cf;
      --risk-critical: #ff5252;
      --risk-high: #ff7b72;
      --risk-medium: #d29922;
      --risk-low: #3fb950;
      --risk-unspecified: #8b949e;
    }}
    
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
      background-color: var(--bg-primary);
      color: var(--text-primary);
      line-height: 1.5;
      padding: 24px;
    }}
    
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border-color);
      margin-bottom: 24px;
    }}
    
    .title-area h1 {{
      font-size: 26px;
      font-weight: 700;
      color: var(--text-primary);
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    
    .badge-pill {{
      display: inline-block;
      padding: 4px 10px;
      font-size: 12px;
      font-weight: 600;
      border-radius: 12px;
      background-color: rgba(88, 166, 255, 0.15);
      color: var(--accent-blue);
      border: 1px solid rgba(88, 166, 255, 0.4);
    }}
    
    .subtitle {{
      color: var(--text-secondary);
      font-size: 14px;
      margin-top: 6px;
    }}
    
    .meta-tags {{
      display: flex;
      gap: 10px;
      margin-top: 10px;
    }}
    
    .tag {{
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      padding: 3px 8px;
      border-radius: 6px;
      font-size: 12px;
      color: var(--text-secondary);
    }}
    
    /* Navigation Tabs */
    .tab-bar {{
      display: flex;
      gap: 8px;
      border-bottom: 1px solid var(--border-color);
      margin-bottom: 24px;
    }}
    
    .tab-btn {{
      background: transparent;
      border: none;
      color: var(--text-secondary);
      padding: 10px 18px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      border-bottom: 2px solid transparent;
      transition: all 0.2s;
    }}
    
    .tab-btn:hover {{
      color: var(--text-primary);
    }}
    
    .tab-btn.active {{
      color: var(--accent-blue);
      border-bottom-color: var(--accent-blue);
    }}
    
    .tab-content {{
      display: none;
    }}
    
    .tab-content.active {{
      display: block;
    }}
    
    /* KPI Cards */
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    
    .kpi-card {{
      background-color: var(--bg-secondary);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 18px;
      position: relative;
    }}
    
    .kpi-card::before {{
      content: "";
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 3px;
      border-radius: 8px 8px 0 0;
    }}
    
    .kpi-card.blue::before {{ background: var(--accent-blue); }}
    .kpi-card.purple::before {{ background: var(--accent-purple); }}
    .kpi-card.green::before {{ background: var(--accent-green); }}
    .kpi-card.orange::before {{ background: var(--accent-orange); }}
    .kpi-card.red::before {{ background: var(--accent-red); }}
    .kpi-card.cyan::before {{ background: var(--accent-cyan); }}
    
    .kpi-title {{
      font-size: 13px;
      color: var(--text-secondary);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      font-weight: 600;
    }}
    
    .kpi-value {{
      font-size: 28px;
      font-weight: 700;
      color: var(--text-primary);
      margin: 8px 0 4px 0;
    }}
    
    .kpi-subtext {{
      font-size: 12px;
      color: var(--text-muted);
    }}
    
    /* Charts Grid */
    .charts-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
      gap: 20px;
      margin-bottom: 28px;
    }}
    
    .chart-card {{
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 20px;
    }}
    
    .chart-card.full-width {{
      grid-column: 1 / -1;
    }}
    
    .chart-title {{
      font-size: 16px;
      font-weight: 600;
      margin-bottom: 6px;
      color: var(--text-primary);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    
    .chart-desc {{
      font-size: 12px;
      color: var(--text-secondary);
      margin-bottom: 16px;
    }}
    
    .chart-wrapper {{
      position: relative;
      height: 290px;
      width: 100%;
    }}
    
    .chart-wrapper.tall {{
      height: 420px;
    }}
    
    /* Tables */
    .table-container {{
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      overflow: hidden;
      margin-bottom: 24px;
    }}
    
    .table-header-tools {{
      padding: 16px;
      border-bottom: 1px solid var(--border-color);
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
    }}
    
    .search-box {{
      background: var(--bg-primary);
      border: 1px solid var(--border-color);
      color: var(--text-primary);
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 13px;
      width: 280px;
    }}
    
    .search-box:focus {{
      outline: none;
      border-color: var(--accent-blue);
    }}
    
    .filter-select {{
      background: var(--bg-primary);
      border: 1px solid var(--border-color);
      color: var(--text-primary);
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 13px;
    }}
    
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    
    th {{
      background-color: #1f242c;
      color: var(--text-secondary);
      text-align: left;
      padding: 12px 14px;
      font-weight: 600;
      border-bottom: 1px solid var(--border-color);
      position: sticky;
      top: 0;
    }}
    
    td {{
      padding: 10px 14px;
      border-bottom: 1px solid var(--border-color);
      color: var(--text-primary);
    }}
    
    tr:hover td {{
      background-color: rgba(88, 166, 255, 0.04);
    }}
    
    .risk-badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
    }}
    
    .risk-critical {{ background: rgba(255, 82, 82, 0.2); color: var(--risk-critical); border: 1px solid rgba(255, 82, 82, 0.4); }}
    .risk-high {{ background: rgba(255, 123, 114, 0.2); color: var(--risk-high); border: 1px solid rgba(255, 123, 114, 0.4); }}
    .risk-medium {{ background: rgba(210, 153, 34, 0.2); color: var(--risk-medium); border: 1px solid rgba(210, 153, 34, 0.4); }}
    .risk-low {{ background: rgba(63, 185, 80, 0.2); color: var(--risk-low); border: 1px solid rgba(63, 185, 80, 0.4); }}
    .risk-unspecified {{ background: rgba(139, 148, 158, 0.2); color: var(--risk-unspecified); border: 1px solid rgba(139, 148, 158, 0.4); }}
    
    .lang-badge {{
      display: inline-block;
      padding: 2px 7px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
    }}
    .lang-py {{ background: #2b3a4a; color: #58a6ff; }}
    .lang-js {{ background: #3b3a2a; color: #f0db4f; }}
    .lang-ts {{ background: #263852; color: #3178c6; }}
    
    .matrix-cell-yes {{
      color: var(--accent-green);
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 4px;
    }}
    
    .matrix-cell-no {{
      color: var(--accent-red);
      opacity: 0.7;
    }}
    
    .matrix-count {{
      font-family: monospace;
      font-weight: 600;
      padding: 2px 6px;
      border-radius: 4px;
    }}
    .count-zero {{ background: rgba(248, 81, 73, 0.15); color: var(--accent-red); }}
    .count-ok {{ background: rgba(63, 185, 80, 0.15); color: var(--accent-green); }}
    
    .code-preview {{
      font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
      font-size: 11px;
      background: #111418;
      padding: 6px 8px;
      border-radius: 4px;
      max-height: 80px;
      overflow-y: auto;
      white-space: pre-wrap;
      word-break: break-all;
      color: #adbac7;
      border: 1px solid #2d333b;
    }}
    
    .eval-spec-box {{
      background: #17202d;
      border: 1px solid rgba(88, 166, 255, 0.3);
      border-radius: 8px;
      padding: 16px 20px;
      margin-bottom: 24px;
    }}
    
    .eval-spec-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-top: 12px;
    }}
    
    .eval-item {{
      background: var(--bg-card);
      padding: 12px;
      border-radius: 6px;
      border-left: 3px solid var(--accent-blue);
    }}
    .eval-item-title {{
      font-size: 12px;
      font-weight: 700;
      color: var(--accent-blue);
      text-transform: uppercase;
    }}
    .eval-item-desc {{
      font-size: 13px;
      color: var(--text-primary);
      margin-top: 4px;
    }}
    
    .info-pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      background: rgba(57, 197, 207, 0.15);
      color: var(--accent-cyan);
      border-radius: 6px;
      font-size: 12px;
      font-weight: 500;
    }}
  </style>
</head>
<body>

  <!-- Header -->
  <div class="header">
    <div class="title-area">
      <h1>
        CodeDEE: LLM Vulnerability Evaluation & RAG Dashboard
        <span class="badge-pill">Local Testbed / Ollama</span>
      </h1>
      <div class="subtitle">
        Visualizing <strong>1,208 Test Evaluation Samples</strong> (dataset.jsonl) &amp; <strong>83 Knowledge Base Entries</strong> (knowledge_base.jsonl)
      </div>
      <div class="meta-tags">
        <span class="tag">🎯 Target Languages: Python, JavaScript, TypeScript</span>
        <span class="tag">⚡ Testbed: RTX 5080 (16GB VRAM) / Core Ultra 9 / Windows 11</span>
        <span class="tag">🛡️ Taxonomy: 28 CWE / OWASP Classes</span>
      </div>
    </div>
  </div>

  <!-- Model Evaluation Output Contract Box -->
  <div class="eval-spec-box">
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <h3 style="color:var(--text-primary); font-size:15px; display:flex; align-items:center; gap:8px;">
        <span>🎯</span> Expected Ollama Model Evaluation Output Schema
      </h3>
      <span class="info-pill">Stage 3B Neural Oracle Contract</span>
    </div>
    <div class="eval-spec-grid">
      <div class="eval-item">
        <div class="eval-item-title">1. CWE-ID</div>
        <div class="eval-item-desc">Predicted CWE code (e.g. <code>CWE-89</code>, <code>CWE-79</code>) matching ground truth.</div>
      </div>
      <div class="eval-item">
        <div class="eval-item-title">2. Reason / Flaw Explanation</div>
        <div class="eval-item-desc">Chain-of-thought rationale explaining tainted dataflow from Source to Sink.</div>
      </div>
      <div class="eval-item">
        <div class="eval-item-title">3. Confidence Score</div>
        <div class="eval-item-desc">Model confidence (0.0 – 1.0). Low confidence triggers Review Tab.</div>
      </div>
      <div class="eval-item">
        <div class="eval-item-title">4. Risk Level</div>
        <div class="eval-item-desc">Severity rating (Critical, High, Medium, Low) derived from CVSS v3.1 metrics.</div>
      </div>
    </div>
  </div>

  <!-- KPI Top Cards -->
  <div class="kpi-grid">
    <div class="kpi-card blue">
      <div class="kpi-title">Test Dataset Samples</div>
      <div class="kpi-value">1,208</div>
      <div class="kpi-subtext">Original vulnerable code for LLM benchmark</div>
    </div>
    <div class="kpi-card purple">
      <div class="kpi-title">Knowledge Base Records</div>
      <div class="kpi-value">83</div>
      <div class="kpi-subtext">28 CWE catalogue definitions for RAG</div>
    </div>
    <div class="kpi-card green">
      <div class="kpi-title">KB Few-Shot Examples</div>
      <div class="kpi-value">67</div>
      <div class="kpi-subtext">16 definition-only (zero data leakage)</div>
    </div>
    <div class="kpi-card orange">
      <div class="kpi-title">Critical &amp; High Risk</div>
      <div class="kpi-value">{ds_risks['Critical'] + ds_risks['High']} / 1,208</div>
      <div class="kpi-subtext">{round((ds_risks['Critical'] + ds_risks['High']) / len(dataset_samples) * 100, 1)}% of test samples</div>
    </div>
    <div class="kpi-card cyan">
      <div class="kpi-title">Catalogue Classes</div>
      <div class="kpi-value">28</div>
      <div class="kpi-subtext">Injection, XSS, SSRF, Deserialization, LLM...</div>
    </div>
  </div>

  <!-- Tabs Navigation -->
  <div class="tab-bar">
    <button class="tab-btn active" onclick="switchTab('tab-overview')">📊 Executive Overview</button>
    <button class="tab-btn" onclick="switchTab('tab-dataset')">🧪 Test Dataset (1,208 Samples)</button>
    <button class="tab-btn" onclick="switchTab('tab-kb')">📚 Knowledge Base RAG (83 Entries)</button>
    <button class="tab-btn" onclick="switchTab('tab-matrix')">⚖️ Catalogue Coverage Matrix (28 Classes)</button>
    <button class="tab-btn" onclick="switchTab('tab-specs')">📑 Ground Truth Table &amp; Specs</button>
  </div>

  <!-- ================= TAB 1: OVERVIEW ================= -->
  <div id="tab-overview" class="tab-content active">
    <div class="charts-grid">
      <!-- Chart 1: Language Breakdown Comparison -->
      <div class="chart-card">
        <div class="chart-title">
          <span>Language Distribution: Test Dataset vs. Knowledge Base</span>
        </div>
        <div class="chart-desc">Compares test sample volume against RAG knowledge base across Python, JS, TS.</div>
        <div class="chart-wrapper">
          <canvas id="chartLangComparison"></canvas>
        </div>
      </div>

      <!-- Chart 2: Risk Level Distribution (CVSS v3.1 derived) -->
      <div class="chart-card">
        <div class="chart-title">
          <span>Risk Level Distribution (Ground Truth CVSS v3.1)</span>
        </div>
        <div class="chart-desc">Distribution of Critical, High, Medium, and Low risk samples for model evaluation.</div>
        <div class="chart-wrapper">
          <canvas id="chartRiskDist"></canvas>
        </div>
      </div>

      <!-- Chart 3: Top CWE Classes Stacked by Language -->
      <div class="chart-card full-width">
        <div class="chart-title">
          <span>Top 15 CWE Vulnerability Classes: Sample Breakdown per Language (Python vs. JS vs. TS)</span>
        </div>
        <div class="chart-desc">Shows exact sample counts per programming language within each vulnerability class (e.g. CWE-78: Python: 24, JS: 24, TS: 24).</div>
        <div class="chart-wrapper tall">
          <canvas id="chartTopCWE"></canvas>
        </div>
      </div>

      <!-- Chart 4: OWASP Category Breakdown -->
      <div class="chart-card">
        <div class="chart-title">
          <span>OWASP Top 10 Distribution (Dataset)</span>
        </div>
        <div class="chart-desc">Proportion of Injection, Broken Access Control, Cryptographic Failures, etc.</div>
        <div class="chart-wrapper">
          <canvas id="chartOwaspDist"></canvas>
        </div>
      </div>

      <!-- Chart 5: Benchmark Split Sources -->
      <div class="chart-card">
        <div class="chart-title">
          <span>Benchmark Provenance &amp; Split Reasons</span>
        </div>
        <div class="chart-desc">Distribution across GIFT (synthetic), AppSec, GHSA real-world CVEs, and SCP pairs.</div>
        <div class="chart-wrapper">
          <canvas id="chartSplitSources"></canvas>
        </div>
      </div>
    </div>
  </div>

  <!-- ================= TAB 2: TEST DATASET ================= -->
  <div id="tab-dataset" class="tab-content">
    <div class="charts-grid">
      <div class="chart-card">
        <div class="chart-title">Test Dataset Language Ratio</div>
        <div class="chart-desc">Total 1,208 test instances (Python: 443, JS: 532, TS: 233)</div>
        <div class="chart-wrapper">
          <canvas id="chartDsLangPie"></canvas>
        </div>
      </div>
      <div class="chart-card">
        <div class="chart-title">CVSS v3.1 Score Spread</div>
        <div class="chart-desc">Histogram of continuous CVSS base scores (0.0 to 10.0)</div>
        <div class="chart-wrapper">
          <canvas id="chartCvssHistogram"></canvas>
        </div>
      </div>
    </div>

    <!-- Interactive Table for Dataset -->
    <div class="table-container">
      <div class="table-header-tools">
        <h3 style="font-size:15px; color:var(--text-primary);">Test Dataset Samples Explorer (1,208 records)</h3>
        <div style="display:flex; gap:10px; align-items:center;">
          <input type="text" id="dsSearch" class="search-box" placeholder="Filter by ID, CWE, or description..." oninput="filterDatasetTable()">
          <select id="dsLangFilter" class="filter-select" onchange="filterDatasetTable()">
            <option value="ALL">All Languages</option>
            <option value="python">Python</option>
            <option value="javascript">JavaScript</option>
            <option value="typescript">TypeScript</option>
          </select>
          <select id="dsRiskFilter" class="filter-select" onchange="filterDatasetTable()">
            <option value="ALL">All Risk Levels</option>
            <option value="Critical">Critical</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </select>
        </div>
      </div>
      <div style="max-height: 520px; overflow-y: auto;">
        <table id="datasetTable">
          <thead>
            <tr>
              <th>Sample ID</th>
              <th>Language</th>
              <th>CWE-ID &amp; Name</th>
              <th>Catalogue ID</th>
              <th>Risk Level</th>
              <th>CVSS</th>
              <th>Split</th>
              <th style="width: 32%;">Vulnerable Code Snippet</th>
            </tr>
          </thead>
          <tbody id="datasetTableBody">
            <!-- Rendered via JS -->
          </tbody>
        </table>
      </div>
      <div style="padding:10px 16px; font-size:12px; color:var(--text-secondary); background:var(--bg-secondary); border-top:1px solid var(--border-color);" id="dsTableFooter">
        Showing records...
      </div>
    </div>
  </div>

  <!-- ================= TAB 3: KNOWLEDGE BASE ================= -->
  <div id="tab-kb" class="tab-content">
    <div class="charts-grid">
      <div class="chart-card full-width">
        <div class="chart-title">
          <span>Knowledge Base (RAG): Entries per Language across All 27 CWEs</span>
        </div>
        <div class="chart-desc">Shows knowledge base catalog rules and few-shot pairs available for Python, JavaScript, and TypeScript across each vulnerability class.</div>
        <div class="chart-wrapper tall">
          <canvas id="chartKbCweLangBar"></canvas>
        </div>
      </div>
      <div class="chart-card">
        <div class="chart-title">RAG Knowledge Base Structure (83 Entries)</div>
        <div class="chart-desc">67 entries contain few-shot code pairs, 16 are pure definitions</div>
        <div class="chart-wrapper">
          <canvas id="chartKbKindPie"></canvas>
        </div>
      </div>
      <div class="chart-card">
        <div class="chart-title">RAG Patterns Availability</div>
        <div class="chart-desc">Distribution of Source, Sink, and Sanitizer pattern specifications</div>
        <div class="chart-wrapper">
          <canvas id="chartKbPatternsBar"></canvas>
        </div>
      </div>
    </div>

    <!-- Interactive Table for KB -->
    <div class="table-container">
      <div class="table-header-tools">
        <h3 style="font-size:15px; color:var(--text-primary);">RAG Knowledge Base Catalog (83 entries)</h3>
        <div style="display:flex; gap:10px; align-items:center;">
          <input type="text" id="kbSearch" class="search-box" placeholder="Search KB ID, CWE, Source, Sink..." oninput="filterKbTable()">
          <select id="kbLangFilter" class="filter-select" onchange="filterKbTable()">
            <option value="ALL">All Languages</option>
            <option value="python">Python</option>
            <option value="javascript">JavaScript</option>
            <option value="typescript">TypeScript</option>
          </select>
        </div>
      </div>
      <div style="max-height: 520px; overflow-y: auto;">
        <table id="kbTable">
          <thead>
            <tr>
              <th>KB ID</th>
              <th>Catalogue ID</th>
              <th>Lang</th>
              <th>CWE-ID &amp; Name</th>
              <th>Risk</th>
              <th>Few-Shot Example</th>
              <th style="width: 20%;">Source Pattern</th>
              <th style="width: 20%;">Sink Pattern</th>
              <th style="width: 20%;">Sanitizer Pattern</th>
            </tr>
          </thead>
          <tbody id="kbTableBody">
            <!-- Rendered via JS -->
          </tbody>
        </table>
      </div>
      <div style="padding:10px 16px; font-size:12px; color:var(--text-secondary); background:var(--bg-secondary); border-top:1px solid var(--border-color);" id="kbTableFooter">
        Showing KB entries...
      </div>
    </div>
  </div>

  <!-- ================= TAB 4: COVERAGE MATRIX ================= -->
  <div id="tab-matrix" class="tab-content">
    <div class="chart-card full-width" style="margin-bottom: 24px;">
      <div class="chart-title">
        <span>28 Vulnerability Catalogue Classes: RAG Support vs. Test Evaluation Density</span>
      </div>
      <div class="chart-desc">
        Visualizes whether each vulnerability class has RAG knowledge base support (📘 KB) and test sample count (🧪 Test) across Python, JavaScript, and TypeScript.
      </div>
      <div class="chart-wrapper tall">
        <canvas id="chartMatrixCoverageBar"></canvas>
      </div>
    </div>

    <div class="table-container">
      <div class="table-header-tools">
        <h3 style="font-size:15px; color:var(--text-primary);">28 Taxonomy Classes: Detailed Language Grid</h3>
        <span class="tag">Zero-Leakage Assurance: No KB examples overlap with test samples</span>
      </div>
      <div style="max-height: 600px; overflow-y: auto;">
        <table>
          <thead>
            <tr>
              <th>Catalogue ID</th>
              <th>CWE-ID</th>
              <th>Vulnerability Name</th>
              <th>OWASP</th>
              <th>Risk Level</th>
              <th style="text-align:center;">Python RAG</th>
              <th style="text-align:center;">Python Tests</th>
              <th style="text-align:center;">JS RAG</th>
              <th style="text-align:center;">JS Tests</th>
              <th style="text-align:center;">TS RAG</th>
              <th style="text-align:center;">TS Tests</th>
              <th style="text-align:center;">Total Tests</th>
            </tr>
          </thead>
          <tbody>
            {''.join([f'''<tr>
              <td><code>{m['catalogue_id']}</code></td>
              <td><strong>{m['cwe_id']}</strong></td>
              <td>{m['cwe_name']}</td>
              <td><span style="font-size:11px; color:var(--text-secondary);">{m['owasp_category']}</span></td>
              <td><span class="risk-badge risk-{m['risk_level'].lower()}">{m['risk_level']}</span></td>
              <td style="text-align:center;">{'<span class="matrix-cell-yes">✓ Available</span>' if m['py_kb'] else '<span class="matrix-cell-no">✗ Missing</span>'}</td>
              <td style="text-align:center;"><span class="matrix-count {'count-ok' if m['py_ds']>0 else 'count-zero'}">{m['py_ds']}</span></td>
              <td style="text-align:center;">{'<span class="matrix-cell-yes">✓ Available</span>' if m['js_kb'] else '<span class="matrix-cell-no">✗ Missing</span>'}</td>
              <td style="text-align:center;"><span class="matrix-count {'count-ok' if m['js_ds']>0 else 'count-zero'}">{m['js_ds']}</span></td>
              <td style="text-align:center;">{'<span class="matrix-cell-yes">✓ Available</span>' if m['ts_kb'] else '<span class="matrix-cell-no">✗ Missing</span>'}</td>
              <td style="text-align:center;"><span class="matrix-count {'count-ok' if m['ts_ds']>0 else 'count-zero'}">{m['ts_ds']}</span></td>
              <td style="text-align:center;"><strong>{m['total_ds']}</strong></td>
            </tr>''' for m in matrix_data])}
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- ================= TAB 5: SPECS & UNMAPPED ================= -->
  <div id="tab-specs" class="tab-content">
    <div class="charts-grid">
      <div class="chart-card">
        <div class="chart-title">Unmapped Samples Analysis (194 samples)</div>
        <div class="chart-desc">Samples with empty catalogue_id (general CWEs not part of the 28 core classes)</div>
        <div class="chart-wrapper">
          <canvas id="chartUnmappedCwes"></canvas>
        </div>
      </div>
      <div class="chart-card">
        <div class="chart-title">Evaluation Readiness &amp; Split Protocol</div>
        <div class="chart-desc">Operational guidelines for running Ollama on Local Testbed</div>
        <div style="font-size:13px; line-height:1.7; color:var(--text-secondary); padding: 10px 0;">
          <p><strong>1. Strict No-Leakage Policy:</strong> All 67 few-shot examples inside <code>knowledge_base.jsonl</code> are isolated. None exist in <code>dataset.jsonl</code>.</p>
          <p style="margin-top:8px;"><strong>2. Evaluation Inputs:</strong> Ollama will receive <code>original_code</code> as input along with RAG context from the corresponding language's KB.</p>
          <p style="margin-top:8px;"><strong>3. Evaluation Outputs:</strong> The model must output JSON containing <code>cwe_id</code>, <code>reason</code>, <code>confidence</code>, and <code>risk_level</code>.</p>
          <p style="margin-top:8px;"><strong>4. Performance Metrics:</strong></p>
          <ul style="margin-left: 20px; margin-top:4px;">
            <li>Exact Match Accuracy: <code>predicted_cwe == true_cwe</code></li>
            <li>Risk Level Correlation: Match against ground truth CVSS risk tier</li>
            <li>Inference Speed (tokens/sec) &amp; VRAM utilization on RTX 5080</li>
          </ul>
        </div>
      </div>
    </div>
  </div>

  <!-- Scripts for Charts and Interactivity -->
  <script>
    // Data Injected from Python
    const DATASET_SAMPLES = {safe_json_dumps(table_dataset_samples)};
    const KB_ENTRIES = {safe_json_dumps(table_kb_entries)};
    
    // Tab switching
    function switchTab(tabId) {{
      document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
      
      const activeBtn = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.getAttribute('onclick').includes(tabId));
      if (activeBtn) activeBtn.classList.add('active');
      
      const targetTab = document.getElementById(tabId);
      if (targetTab) targetTab.classList.add('active');
      
      window.dispatchEvent(new Event('resize'));
    }}

    // Filter Dataset Table
    function filterDatasetTable() {{
      const query = document.getElementById('dsSearch').value.toLowerCase();
      const lang = document.getElementById('dsLangFilter').value;
      const risk = document.getElementById('dsRiskFilter').value;
      
      const filtered = DATASET_SAMPLES.filter(s => {{
        const matchesQuery = !query || 
          s.id.toLowerCase().includes(query) || 
          s.cwe_id.toLowerCase().includes(query) || 
          s.cwe_name.toLowerCase().includes(query) ||
          s.catalogue_id.toLowerCase().includes(query);
          
        const matchesLang = (lang === 'ALL') || (s.lang === lang);
        const matchesRisk = (risk === 'ALL') || (s.risk === risk);
        
        return matchesQuery && matchesLang && matchesRisk;
      }});
      
      renderDatasetTable(filtered.slice(0, 150), filtered.length);
    }}

    function renderDatasetTable(items, totalCount) {{
      const tbody = document.getElementById('datasetTableBody');
      tbody.innerHTML = items.map(s => `
        <tr>
          <td><code style="color:var(--accent-blue);">${{s.id}}</code></td>
          <td><span class="lang-badge lang-${{s.lang === 'python' ? 'py' : (s.lang === 'javascript' ? 'js' : 'ts')}}">${{s.lang}}</span></td>
          <td><strong>${{s.cwe_id}}</strong> <span style="font-size:12px; color:var(--text-secondary);"><br>${{s.cwe_name}}</span></td>
          <td><code style="font-size:11px;">${{s.catalogue_id}}</code></td>
          <td><span class="risk-badge risk-${{s.risk.toLowerCase()}}">${{s.risk}}</span></td>
          <td><code>${{s.cvss !== null ? s.cvss : '-'}}</code></td>
          <td><span style="font-size:11px; color:var(--text-muted);">${{s.split_reason}}</span></td>
          <td><div class="code-preview">${{escapeHtml(s.code_snippet)}}</div></td>
        </tr>
      `).join('');
      
      document.getElementById('dsTableFooter').innerText = `Showing ${{items.length}} of ${{totalCount}} matched samples (display capped at 150 for rendering speed)`;
    }}

    // Filter KB Table
    function filterKbTable() {{
      const query = document.getElementById('kbSearch').value.toLowerCase();
      const lang = document.getElementById('kbLangFilter').value;
      
      const filtered = KB_ENTRIES.filter(k => {{
        const matchesQuery = !query ||
          k.kb_id.toLowerCase().includes(query) ||
          k.catalogue_id.toLowerCase().includes(query) ||
          k.cwe_id.toLowerCase().includes(query) ||
          k.cwe_name.toLowerCase().includes(query) ||
          k.source_pat.toLowerCase().includes(query) ||
          k.sink_pat.toLowerCase().includes(query);
          
        const matchesLang = (lang === 'ALL') || (k.lang === lang);
        return matchesQuery && matchesLang;
      }});
      
      renderKbTable(filtered);
    }}

    function renderKbTable(items) {{
      const tbody = document.getElementById('kbTableBody');
      tbody.innerHTML = items.map(k => `
        <tr>
          <td><code style="color:var(--accent-purple); font-size:11px;">${{k.kb_id}}</code></td>
          <td><code>${{k.catalogue_id}}</code></td>
          <td><span class="lang-badge lang-${{k.lang === 'python' ? 'py' : (k.lang === 'javascript' ? 'js' : 'ts')}}">${{k.lang}}</span></td>
          <td><strong>${{k.cwe_id}}</strong> <span style="font-size:11px; color:var(--text-secondary);"><br>${{k.cwe_name}}</span></td>
          <td><span class="risk-badge risk-${{k.risk.toLowerCase()}}">${{k.risk}}</span></td>
          <td style="text-align:center;">${{k.has_example ? '<span style="color:var(--accent-green); font-weight:bold;">Yes (Pair)</span>' : '<span style="color:var(--text-muted);">Def Only</span>'}}</td>
          <td><div class="code-preview" style="max-height:50px;">${{escapeHtml(k.source_pat || '-')}}</div></td>
          <td><div class="code-preview" style="max-height:50px;">${{escapeHtml(k.sink_pat || '-')}}</div></td>
          <td><div class="code-preview" style="max-height:50px;">${{escapeHtml(k.sanitizer_pat || '-')}}</div></td>
        </tr>
      `).join('');
      document.getElementById('kbTableFooter').innerText = `Showing ${{items.length}} knowledge base entries`;
    }}

    function escapeHtml(text) {{
      return (text || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }}

    // Initialize Charts on Load
    window.addEventListener('DOMContentLoaded', () => {{
      renderDatasetTable(DATASET_SAMPLES.slice(0, 100), DATASET_SAMPLES.length);
      renderKbTable(KB_ENTRIES);

      Chart.defaults.color = '#8b949e';
      Chart.defaults.borderColor = '#30363d';

      // Chart 1: Language Comparison Bar
      new Chart(document.getElementById('chartLangComparison'), {{
        type: 'bar',
        data: {{
          labels: ['Python', 'JavaScript', 'TypeScript'],
          datasets: [
            {{
              label: 'Test Dataset (Eval)',
              data: [{ds_langs['python']}, {ds_langs['javascript']}, {ds_langs['typescript']}],
              backgroundColor: '#58a6ff',
              borderRadius: 6
            }},
            {{
              label: 'Knowledge Base (RAG)',
              data: [{kb_langs['python']}, {kb_langs['javascript']}, {kb_langs['typescript']}],
              backgroundColor: '#bc8cff',
              borderRadius: 6
            }}
          ]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          plugins: {{ legend: {{ position: 'top' }} }}
        }}
      }});

      // Chart 2: Risk Level Distribution Pie
      new Chart(document.getElementById('chartRiskDist'), {{
        type: 'doughnut',
        data: {{
          labels: ['Critical (CVSS 9.0-10.0)', 'High (CVSS 7.0-8.9)', 'Medium (CVSS 4.0-6.9)', 'Low (CVSS 0.1-3.9)', 'Unspecified'],
          datasets: [{{
            data: [{ds_risks['Critical']}, {ds_risks['High']}, {ds_risks['Medium']}, {ds_risks['Low']}, {ds_risks['Unspecified']}],
            backgroundColor: ['#ff5252', '#ff7b72', '#d29922', '#3fb950', '#8b949e']
          }}]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          plugins: {{ legend: {{ position: 'right' }} }}
        }}
      }});

      // Chart 3: Top 15 CWE Classes with Stacked Language Breakdown
      new Chart(document.getElementById('chartTopCWE'), {{
        type: 'bar',
        data: {{
          labels: {json.dumps(top_cwe_bar_labels)},
          datasets: [
            {{
              label: 'Python',
              data: {json.dumps(top_cwe_bar_py)},
              backgroundColor: '#58a6ff'
            }},
            {{
              label: 'JavaScript',
              data: {json.dumps(top_cwe_bar_js)},
              backgroundColor: '#f0db4f'
            }},
            {{
              label: 'TypeScript',
              data: {json.dumps(top_cwe_bar_ts)},
              backgroundColor: '#3178c6'
            }}
          ]
        }},
        options: {{
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          scales: {{
            x: {{
              stacked: true,
              title: {{ display: true, text: 'Sample Count' }}
            }},
            y: {{
              stacked: true
            }}
          }},
          plugins: {{
            legend: {{ position: 'top' }},
            tooltip: {{
              callbacks: {{
                afterBody: function(context) {{
                  const dataIndex = context[0].dataIndex;
                  const py = {json.dumps(top_cwe_bar_py)}[dataIndex];
                  const js = {json.dumps(top_cwe_bar_js)}[dataIndex];
                  const ts = {json.dumps(top_cwe_bar_ts)}[dataIndex];
                  return `Total: ${{py + js + ts}} (Python: ${{py}}, JS: ${{js}}, TS: ${{ts}})`;
                }}
              }}
            }}
          }}
        }}
      }});

      // Chart 4: OWASP Distribution
      const owaspLabels = {json.dumps([k[:24] for k, v in ds_owasp.most_common(6)])};
      const owaspCounts = {json.dumps([v for k, v in ds_owasp.most_common(6)])};
      new Chart(document.getElementById('chartOwaspDist'), {{
        type: 'polarArea',
        data: {{
          labels: owaspLabels,
          datasets: [{{
            data: owaspCounts,
            backgroundColor: ['#58a6ff99', '#bc8cff99', '#3fb95099', '#d2992299', '#f8514999', '#39c5cf99']
          }}]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          plugins: {{ legend: {{ position: 'right' }} }}
        }}
      }});

      // Chart 5: Split Sources
      new Chart(document.getElementById('chartSplitSources'), {{
        type: 'pie',
        data: {{
          labels: {json.dumps(list(ds_splits.keys()))},
          datasets: [{{
            data: {json.dumps(list(ds_splits.values()))},
            backgroundColor: ['#58a6ff', '#3fb950', '#d29922', '#bc8cff', '#f85149', '#39c5cf', '#e3b341', '#fd8c73', '#6cb6ff']
          }}]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          plugins: {{ legend: {{ position: 'right' }} }}
        }}
      }});

      // Chart: Dataset Lang Pie
      new Chart(document.getElementById('chartDsLangPie'), {{
        type: 'doughnut',
        data: {{
          labels: ['Python (443)', 'JavaScript (532)', 'TypeScript (233)'],
          datasets: [{{
            data: [443, 532, 233],
            backgroundColor: ['#58a6ff', '#f0db4f', '#3178c6']
          }}]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false
        }}
      }});

      // Chart: CVSS Histogram
      const cvssBins = ['0.0-3.9 (Low)', '4.0-5.9 (Med-L)', '6.0-6.9 (Med-H)', '7.0-7.9 (High-L)', '8.0-8.9 (High-H)', '9.0-9.7 (Crit-L)', '9.8-10.0 (Crit-H)', 'Unspecified'];
      const cvssCounts = [7, 73, 297, 240, 164, 151, 238, 38];
      new Chart(document.getElementById('chartCvssHistogram'), {{
        type: 'bar',
        data: {{
          labels: cvssBins,
          datasets: [{{
            label: 'Sample Count',
            data: cvssCounts,
            backgroundColor: ['#3fb950', '#d29922', '#d29922', '#ff7b72', '#ff7b72', '#ff5252', '#ff5252', '#8b949e'],
            borderRadius: 6
          }}]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false
        }}
      }});

      // Chart: KB Kind Pie
      new Chart(document.getElementById('chartKbKindPie'), {{
        type: 'pie',
        data: {{
          labels: ['With Few-Shot Example Code (67)', 'Definition Only (16)'],
          datasets: [{{
            data: [67, 16],
            backgroundColor: ['#3fb950', '#bc8cff']
          }}]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false
        }}
      }});

      // Chart: KB Patterns
      new Chart(document.getElementById('chartKbPatternsBar'), {{
        type: 'bar',
        data: {{
          labels: ['Source Patterns Defined', 'Sink Patterns Defined', 'Sanitizer Patterns Defined'],
          datasets: [{{
            label: 'KB Entries with Pattern',
            data: [83, 83, 83],
            backgroundColor: '#bc8cff',
            borderRadius: 6
          }}]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          scales: {{ y: {{ max: 100 }} }}
        }}
      }});

      // Chart: KB CWE Stacked by Language
      new Chart(document.getElementById('chartKbCweLangBar'), {{
        type: 'bar',
        data: {{
          labels: {json.dumps(kb_cwe_bar_labels)},
          datasets: [
            {{
              label: 'Python',
              data: {json.dumps(kb_cwe_bar_py)},
              backgroundColor: '#58a6ff'
            }},
            {{
              label: 'JavaScript',
              data: {json.dumps(kb_cwe_bar_js)},
              backgroundColor: '#f0db4f'
            }},
            {{
              label: 'TypeScript',
              data: {json.dumps(kb_cwe_bar_ts)},
              backgroundColor: '#3178c6'
            }}
          ]
        }},
        options: {{
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          scales: {{
            x: {{
              stacked: true,
              title: {{ display: true, text: 'KB Entries Count' }},
              ticks: {{ stepSize: 1 }}
            }},
            y: {{
              stacked: true
            }}
          }},
          plugins: {{
            legend: {{ position: 'top' }},
            tooltip: {{
              callbacks: {{
                afterBody: function(context) {{
                  const dataIndex = context[0].dataIndex;
                  const py = {json.dumps(kb_cwe_bar_py)}[dataIndex];
                  const js = {json.dumps(kb_cwe_bar_js)}[dataIndex];
                  const ts = {json.dumps(kb_cwe_bar_ts)}[dataIndex];
                  return `Total KB: ${{py + js + ts}} (Python: ${{py}}, JS: ${{js}}, TS: ${{ts}})`;
                }}
              }}
            }}
          }}
        }}
      }});

      // Chart: Matrix Coverage Bar
      const matrixLabels = {json.dumps([m['catalogue_id'] + ' (' + m['cwe_id'] + ')' for m in matrix_data])};
      const matrixPy = {json.dumps([m['py_ds'] for m in matrix_data])};
      const matrixJs = {json.dumps([m['js_ds'] for m in matrix_data])};
      const matrixTs = {json.dumps([m['ts_ds'] for m in matrix_data])};

      new Chart(document.getElementById('chartMatrixCoverageBar'), {{
        type: 'bar',
        data: {{
          labels: matrixLabels,
          datasets: [
            {{ label: 'Python Tests', data: matrixPy, backgroundColor: '#58a6ff' }},
            {{ label: 'JavaScript Tests', data: matrixJs, backgroundColor: '#f0db4f' }},
            {{ label: 'TypeScript Tests', data: matrixTs, backgroundColor: '#3178c6' }}
          ]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          scales: {{
            x: {{ stacked: true }},
            y: {{ stacked: true }}
          }}
        }}
      }});

      // Chart: Unmapped CWEs
      const unmappedLabels = {json.dumps([k.split(':')[0] for k, v in unmapped_cwes.most_common(8)])};
      const unmappedCounts = {json.dumps([v for k, v in unmapped_cwes.most_common(8)])};
      new Chart(document.getElementById('chartUnmappedCwes'), {{
        type: 'bar',
        data: {{
          labels: unmappedLabels,
          datasets: [{{
            label: 'Samples Count',
            data: unmappedCounts,
            backgroundColor: '#e3b341',
            borderRadius: 6
          }}]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false
        }}
      }});
    }});
  </script>
</body>
</html>
"""

output_path = VIS_DIR / "codedee_evaluation_rag_dashboard.html"
with open(output_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"Generated dashboard: {output_path}")

artifact_path = ARTIFACT_DIR / "codedee_evaluation_rag_dashboard.html"
with open(artifact_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"Mirrored dashboard to artifact: {artifact_path}")
