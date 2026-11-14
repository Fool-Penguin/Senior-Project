"""
CodeDEE Comprehensive Dataset Visualizer
Generates:
1. High-Resolution Publication-Quality PNGs for LaTeX & Slides:
   - datasets_overview_comparison.png (All 5 datasets: V1, V2, V3, V4, CyberSecEval)
   - dataset_v4_comprehensive_analysis.png (V4: Safe vs Vuln, Language, CWE taxonomy, SLOC/Char length)
   - dataset_cyberseceval_analysis.png (CyberSecEval: Language, CWE distribution, length)
   - dataset_comparison_v4_vs_cyberseceval.png (Side-by-side CWE overlap and distribution)
2. Interactive All-in-One HTML Dashboard:
   - visualizations/codedee_all_datasets_dashboard.html (Rich Chart.js interactive charts, filters, metrics)
"""

import json
import pathlib
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).parent.parent
DATA_DIR = ROOT / "datasets" / "combined"
VIZ_DIR = ROOT / "visualizations"
VIZ_DIR.mkdir(parents=True, exist_ok=True)

# Datasets definition
DATASETS_INFO = [
    {
        "id": "v1",
        "name": "Version 1 (Raw Unfiltered)",
        "file": DATA_DIR / "dataset_v1_raw_unfiltered_1208.jsonl",
        "badge": "1,208 samples",
        "desc": "Original raw benchmark samples before cleaning"
    },
    {
        "id": "v2",
        "name": "Version 2 (Single-Function Clean)",
        "file": DATA_DIR / "dataset_v2_filtered_30to4000_vuln_only_928.jsonl",
        "badge": "928 samples",
        "desc": "Filtered 30-4,000 chars, 28 Taxonomy CWEs, 100% vulnerable"
    },
    {
        "id": "v3",
        "name": "Version 3 (Multi-Function Clean)",
        "file": DATA_DIR / "dataset_v3_multifunc_30to20000_vuln_only_967.jsonl",
        "badge": "967 samples",
        "desc": "Filtered 30-20,000 chars (up to ~320 lines), retains 39 multi-function files"
    },
    {
        "id": "v4",
        "name": "Version 4 (Paired Vuln + Safe Controls)",
        "file": DATA_DIR / "dataset_v4_multifunc_with_safe_patches_1911.jsonl",
        "badge": "1,911 samples",
        "desc": "967 vulnerable + 944 developer-patched safe code (CWE-NONE) controls"
    },
    {
        "id": "cyberseceval",
        "name": "Meta PurpleLlama CyberSecEval",
        "file": DATA_DIR / "dataset_cyberseceval_external_507.jsonl",
        "badge": "507 samples",
        "desc": "External real-world benchmark extracted from Meta CyberSecEval repo (Python/JS)"
    }
]

def load_dataset(filepath):
    records = []
    if not filepath.exists():
        print(f"Warning: {filepath} not found.")
        return records
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records

def generate_png_visualizations(ds_data):
    # Set clean aesthetic styling
    plt.rcParams.update({
        'font.sans-serif': 'Arial, DejaVu Sans, Helvetica',
        'font.family': 'sans-serif',
        'axes.edgecolor': '#cbd5e1',
        'axes.linewidth': 1.2,
        'grid.color': '#f1f5f9',
        'grid.linestyle': '--',
        'grid.alpha': 0.7
    })

    # =========================================================================
    # FIG 1: Datasets Overview & Progression Comparison (All 5 Datasets)
    # =========================================================================
    fig, axes = plt.subplots(1, 3, figsize=(18, 6), dpi=300)
    fig.patch.set_facecolor('#ffffff')
    
    names = [d["name"].split(" (")[0] for d in DATASETS_INFO]
    counts = [len(ds_data[d["id"]]) for d in DATASETS_INFO]
    vuln_counts = [sum(1 for r in ds_data[d["id"]] if r.get("is_vulnerable", True)) for d in DATASETS_INFO]
    safe_counts = [sum(1 for r in ds_data[d["id"]] if not r.get("is_vulnerable", True)) for d in DATASETS_INFO]

    # Subplot 1A: Stacked Bar of Sample Composition
    ax = axes[0]
    ax.set_facecolor('#ffffff')
    p1 = ax.bar(names, vuln_counts, label="Vulnerable Samples", color="#ef4444", width=0.55, edgecolor="#b91c1c")
    p2 = ax.bar(names, safe_counts, bottom=vuln_counts, label="Safe Patched Controls (CWE-NONE)", color="#10b981", width=0.55, edgecolor="#047857")
    ax.set_title("A. Dataset Volume & Vulnerability Split", fontsize=13, fontweight='bold', pad=12, color="#0f172a")
    ax.set_ylabel("Total Samples", fontsize=11, fontweight='bold', color="#334155")
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=25, ha="right", fontsize=9, fontweight='medium')
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    ax.legend(frameon=True, facecolor="#ffffff", edgecolor="#e2e8f0", loc='upper left', fontsize=9)
    for i, total in enumerate(counts):
        ax.text(i, total + 30, f"{total:,}", ha='center', va='bottom', fontsize=10, fontweight='bold', color="#0f172a")

    # Subplot 1B: Language Distribution across Datasets
    ax = axes[1]
    ax.set_facecolor('#ffffff')
    langs = ["python", "javascript", "typescript"]
    colors = {"python": "#3b82f6", "javascript": "#f59e0b", "typescript": "#8b5cf6"}
    bar_width = 0.25
    x_indices = range(len(names))
    
    for idx, lang in enumerate(langs):
        lang_counts = [sum(1 for r in ds_data[d["id"]] if str(r.get("language","")).lower() == lang) for d in DATASETS_INFO]
        offset = (idx - 1) * bar_width
        bars = ax.bar([xi + offset for xi in x_indices], lang_counts, width=bar_width, label=lang.capitalize(), color=colors[lang], edgecolor="#64748b")
        for b in bars:
            h = b.get_height()
            if h > 0:
                ax.text(b.get_x() + b.get_width()/2., h + 15, f"{int(h)}", ha='center', va='bottom', fontsize=8, color="#1e293b", rotation=90)
                
    ax.set_title("B. Language Coverage by Dataset", fontsize=13, fontweight='bold', pad=12, color="#0f172a")
    ax.set_xticks(list(x_indices))
    ax.set_xticklabels(names, rotation=25, ha="right", fontsize=9, fontweight='medium')
    ax.set_ylabel("Number of Samples", fontsize=11, fontweight='bold', color="#334155")
    ax.legend(frameon=True, facecolor="#ffffff", edgecolor="#e2e8f0", loc='upper right', fontsize=9)
    ax.grid(axis='y', linestyle='--', alpha=0.5)
    ax.set_ylim(0, 950)

    # Subplot 1C: Character Length Median & Bounds
    ax = axes[2]
    ax.set_facecolor('#ffffff')
    box_data = []
    for d in DATASETS_INFO:
        lens = [len(r.get("original_code", "")) for r in ds_data[d["id"]]]
        box_data.append(lens)
    
    bp = ax.boxplot(box_data, tick_labels=names, patch_artist=True, showfliers=False,
                    medianprops=dict(color="#b91c1c", linewidth=2),
                    whiskerprops=dict(color="#475569", linewidth=1.2),
                    capprops=dict(color="#475569", linewidth=1.2))
    
    palette = ['#e2e8f0', '#bfdbfe', '#c7d2fe', '#bbf7d0', '#fed7aa']
    for patch, color in zip(bp['boxes'], palette):
        patch.set_facecolor(color)
        patch.set_edgecolor('#475569')

    ax.set_title("C. Code Length Distribution (Excl. Outliers)", fontsize=13, fontweight='bold', pad=12, color="#0f172a")
    ax.set_xticks(range(1, len(names) + 1))
    ax.set_xticklabels(names, rotation=25, ha="right", fontsize=9, fontweight='medium')
    ax.set_ylabel("Code Length (Characters)", fontsize=11, fontweight='bold', color="#334155")
    ax.grid(axis='y', linestyle='--', alpha=0.5)

    plt.tight_layout()
    out1 = VIZ_DIR / "datasets_overview_comparison.png"
    plt.savefig(out1, dpi=300)
    plt.close()
    print(f"Saved: {out1}")

    # =========================================================================
    # FIG 2: Dataset Version 4 Comprehensive Analysis (1,911 samples)
    # =========================================================================
    fig = plt.figure(figsize=(18, 11), dpi=300)
    fig.patch.set_facecolor('#ffffff')
    gs = fig.add_gridspec(2, 3, height_ratios=[1, 1.4])

    v4_records = ds_data["v4"]

    # 2A: Donut Chart: Vulnerable vs Safe
    ax2a = fig.add_subplot(gs[0, 0])
    v_counts = [sum(1 for r in v4_records if r.get("is_vulnerable", True)),
                sum(1 for r in v4_records if not r.get("is_vulnerable", True))]
    v_labels = [f"Vulnerable\n({v_counts[0]:,} / {v_counts[0]/len(v4_records):.1%})",
                f"Safe Patched Controls\n({v_counts[1]:,} / {v_counts[1]/len(v4_records):.1%})"]
    wedges, texts = ax2a.pie(v_counts, labels=v_labels, colors=['#ef4444', '#10b981'],
                             startangle=140, textprops=dict(color="#0f172a", fontsize=10, fontweight='bold'),
                             wedgeprops=dict(width=0.42, edgecolor='#ffffff', linewidth=2))
    ax2a.set_title("A. V4 Benchmark Class Balance", fontsize=12, fontweight='bold', pad=10, color="#0f172a")

    # 2B: Donut Chart: Language Breakdown
    ax2b = fig.add_subplot(gs[0, 1])
    l_counts = Counter(r.get("language") for r in v4_records)
    langs_order = ['javascript', 'python', 'typescript']
    l_vals = [l_counts[k] for k in langs_order]
    l_labels = [f"{k.capitalize()}\n({l_counts[k]:,} / {l_counts[k]/len(v4_records):.1%})" for k in langs_order]
    ax2b.pie(l_vals, labels=l_labels, colors=['#f59e0b', '#3b82f6', '#8b5cf6'],
             startangle=90, textprops=dict(color="#0f172a", fontsize=10, fontweight='bold'),
             wedgeprops=dict(width=0.42, edgecolor='#ffffff', linewidth=2))
    ax2b.set_title("B. V4 Language Distribution", fontsize=12, fontweight='bold', pad=10, color="#0f172a")

    # 2C: Code Length Distribution (Lines of Code vs Char count)
    ax2c = fig.add_subplot(gs[0, 2])
    ax2c.set_facecolor('#ffffff')
    slocs = [r.get("original_code", "").count('\n') + 1 for r in v4_records]
    ax2c.hist(slocs, bins=35, color='#6366f1', edgecolor='#4338ca', alpha=0.85)
    ax2c.axvline(x=sum(slocs)/len(slocs), color='#ef4444', linestyle='--', linewidth=2, label=f'Mean SLOC: {sum(slocs)/len(slocs):.1f}')
    ax2c.axvline(x=sorted(slocs)[len(slocs)//2], color='#10b981', linestyle='-', linewidth=2, label=f'Median SLOC: {sorted(slocs)[len(slocs)//2]}')
    ax2c.set_title("C. V4 Code Length (SLOC Distribution)", fontsize=12, fontweight='bold', pad=10, color="#0f172a")
    ax2c.set_xlabel("Source Lines of Code (SLOC)", fontsize=10, fontweight='bold', color="#334155")
    ax2c.set_ylabel("Number of Samples", fontsize=10, fontweight='bold', color="#334155")
    ax2c.legend(frameon=True, facecolor="#ffffff", edgecolor="#e2e8f0", fontsize=9)
    ax2c.grid(axis='y', linestyle='--', alpha=0.5)

    # 2D: CWE Taxonomy Distribution per Programming Language
    ax2d = fig.add_subplot(gs[1, :])
    ax2d.set_facecolor('#ffffff')

    # Aggregate vulnerable samples by CWE and language
    vuln_v4 = [r for r in v4_records if r.get("is_vulnerable", True)]
    cwe_by_lang = defaultdict(lambda: Counter())
    for r in vuln_v4:
        cwe = r.get("cwe_id", "Unknown")
        lang = str(r.get("language", "python")).lower()
        cwe_by_lang[cwe][lang] += 1

    # Sort CWEs by total frequency
    cwe_totals = {cwe: sum(counts.values()) for cwe, counts in cwe_by_lang.items()}
    sorted_cwes = sorted(cwe_totals.keys(), key=lambda c: cwe_totals[c], reverse=True)

    x = range(len(sorted_cwes))
    py_vals = [cwe_by_lang[c]["python"] for c in sorted_cwes]
    js_vals = [cwe_by_lang[c]["javascript"] for c in sorted_cwes]
    ts_vals = [cwe_by_lang[c]["typescript"] for c in sorted_cwes]

    bar_w = 0.65
    b_py = ax2d.bar(x, py_vals, bar_w, label='Python', color='#3b82f6', edgecolor='#1d4ed8')
    b_js = ax2d.bar(x, js_vals, bar_w, bottom=py_vals, label='JavaScript', color='#f59e0b', edgecolor='#b45309')
    bottom_ts = [p + j for p, j in zip(py_vals, js_vals)]
    b_ts = ax2d.bar(x, ts_vals, bar_w, bottom=bottom_ts, label='TypeScript', color='#8b5cf6', edgecolor='#6d28d9')

    # Labels on bars
    for i, total in enumerate([cwe_totals[c] for c in sorted_cwes]):
        ax2d.text(i, total + 3, str(total), ha='center', va='bottom', fontsize=8, fontweight='bold', color='#0f172a')

    ax2d.set_title("D. CodeDEE Version 4 Vulnerability Breakdown across 28 Taxonomy CWEs (Vulnerable Subset: 967 Samples)",
                   fontsize=13, fontweight='bold', pad=12, color="#0f172a")
    ax2d.set_xticks(list(x))
    ax2d.set_xticklabels(sorted_cwes, rotation=45, ha='right', fontsize=9, fontweight='medium')
    ax2d.set_ylabel("Vulnerability Sample Count", fontsize=11, fontweight='bold', color="#334155")
    ax2d.legend(frameon=True, facecolor="#ffffff", edgecolor="#e2e8f0", loc='upper right', fontsize=10)
    ax2d.grid(axis='y', linestyle='--', alpha=0.5)
    ax2d.set_ylim(0, max(cwe_totals.values()) + 25)

    plt.tight_layout()
    out2 = VIZ_DIR / "dataset_v4_comprehensive_analysis.png"
    plt.savefig(out2, dpi=300)
    plt.close()
    print(f"Saved: {out2}")

    # =========================================================================
    # FIG 3: Meta PurpleLlama CyberSecEval Deep Analysis (507 Samples)
    # =========================================================================
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5), dpi=300)
    fig.patch.set_facecolor('#ffffff')

    cs_records = ds_data["cyberseceval"]

    # 3A: CyberSecEval Language Split
    ax = axes[0]
    cs_langs = Counter(r.get("language") for r in cs_records)
    cs_l_labels = [f"Python\n({cs_langs['python']:,} / {cs_langs['python']/len(cs_records):.1%})",
                   f"JavaScript\n({cs_langs['javascript']:,} / {cs_langs['javascript']/len(cs_records):.1%})"]
    ax.pie([cs_langs['python'], cs_langs['javascript']], labels=cs_l_labels,
           colors=['#3b82f6', '#f59e0b'], startangle=110,
           textprops=dict(color="#0f172a", fontsize=10, fontweight='bold'),
           wedgeprops=dict(width=0.42, edgecolor='#ffffff', linewidth=2))
    ax.set_title("A. Language Distribution in CyberSecEval", fontsize=12, fontweight='bold', pad=10, color="#0f172a")

    # 3B: CyberSecEval CWEs by Language
    ax = axes[1]
    ax.set_facecolor('#ffffff')
    cs_cwe_lang = defaultdict(lambda: Counter())
    for r in cs_records:
        cs_cwe_lang[r.get("cwe_id", "Unknown")][r.get("language")] += 1

    cs_cwe_totals = {c: sum(cs_cwe_lang[c].values()) for c in cs_cwe_lang}
    sorted_cs_cwes = sorted(cs_cwe_totals.keys(), key=lambda c: cs_cwe_totals[c], reverse=True)

    x_cs = range(len(sorted_cs_cwes))
    cs_py = [cs_cwe_lang[c]["python"] for c in sorted_cs_cwes]
    cs_js = [cs_cwe_lang[c]["javascript"] for c in sorted_cs_cwes]

    ax.bar(x_cs, cs_py, 0.6, label="Python", color="#3b82f6", edgecolor="#1d4ed8")
    ax.bar(x_cs, cs_js, 0.6, bottom=cs_py, label="JavaScript", color="#f59e0b", edgecolor="#b45309")
    for i, t in enumerate([cs_cwe_totals[c] for c in sorted_cs_cwes]):
        ax.text(i, t + 1.5, str(t), ha='center', va='bottom', fontsize=8, fontweight='bold', color='#0f172a')

    ax.set_title("B. CWE Distribution by Language", fontsize=12, fontweight='bold', pad=10, color="#0f172a")
    ax.set_xticks(list(x_cs))
    ax.set_xticklabels(sorted_cs_cwes, rotation=35, ha='right', fontsize=9, fontweight='medium')
    ax.set_ylabel("Sample Count", fontsize=10, fontweight='bold', color="#334155")
    ax.legend(frameon=True, facecolor="#ffffff", edgecolor="#e2e8f0", loc='upper right', fontsize=9)
    ax.grid(axis='y', linestyle='--', alpha=0.5)

    # 3C: CyberSecEval Code Length (SLOC)
    ax = axes[2]
    ax.set_facecolor('#ffffff')
    cs_slocs = [r.get("original_code", "").count('\n') + 1 for r in cs_records]
    ax.hist(cs_slocs, bins=30, color='#0284c7', edgecolor='#0369a1', alpha=0.85)
    ax.axvline(x=sum(cs_slocs)/len(cs_slocs), color='#ef4444', linestyle='--', linewidth=2, label=f'Mean SLOC: {sum(cs_slocs)/len(cs_slocs):.1f}')
    ax.axvline(x=sorted(cs_slocs)[len(cs_slocs)//2], color='#10b981', linestyle='-', linewidth=2, label=f'Median SLOC: {sorted(cs_slocs)[len(cs_slocs)//2]}')
    ax.set_title("C. CyberSecEval Code Length (SLOC)", fontsize=12, fontweight='bold', pad=10, color="#0f172a")
    ax.set_xlabel("Source Lines of Code (SLOC)", fontsize=10, fontweight='bold', color="#334155")
    ax.set_ylabel("Number of Samples", fontsize=10, fontweight='bold', color="#334155")
    ax.legend(frameon=True, facecolor="#ffffff", edgecolor="#e2e8f0", fontsize=9)
    ax.grid(axis='y', linestyle='--', alpha=0.5)

    plt.tight_layout()
    out3 = VIZ_DIR / "dataset_cyberseceval_analysis.png"
    plt.savefig(out3, dpi=300)
    plt.close()
    print(f"Saved: {out3}")

    # =========================================================================
    # FIG 4: Side-by-Side Comparison: CodeDEE V4 vs Meta CyberSecEval
    # =========================================================================
    fig, axes = plt.subplots(1, 2, figsize=(18, 6), dpi=300)
    fig.patch.set_facecolor('#ffffff')

    # 4A: Top Shared CWE Comparison
    ax = axes[0]
    ax.set_facecolor('#ffffff')
    
    # Get all common CWEs in CyberSecEval
    all_cwes_set = sorted(set(cs_cwe_totals.keys()))
    x_idx = range(len(all_cwes_set))
    bar_w = 0.35

    v4_counts_for_common = [cwe_totals.get(c, 0) for c in all_cwes_set]
    cs_counts_for_common = [cs_cwe_totals.get(c, 0) for c in all_cwes_set]

    ax.bar([i - bar_w/2 for i in x_idx], v4_counts_for_common, bar_w, label='CodeDEE V4 (Our Benchmark)', color='#6366f1', edgecolor='#4338ca')
    ax.bar([i + bar_w/2 for i in x_idx], cs_counts_for_common, bar_w, label='Meta CyberSecEval (External)', color='#0ea5e9', edgecolor='#0284c7')

    for i in x_idx:
        ax.text(i - bar_w/2, v4_counts_for_common[i] + 2, str(v4_counts_for_common[i]), ha='center', va='bottom', fontsize=8, fontweight='bold', color='#4338ca')
        ax.text(i + bar_w/2, cs_counts_for_common[i] + 2, str(cs_counts_for_common[i]), ha='center', va='bottom', fontsize=8, fontweight='bold', color='#0284c7')

    ax.set_title("A. Side-by-Side CWE Frequency in CyberSecEval Overlap", fontsize=12, fontweight='bold', pad=12, color="#0f172a")
    ax.set_xticks(list(x_idx))
    ax.set_xticklabels(all_cwes_set, rotation=35, ha='right', fontsize=9, fontweight='medium')
    ax.set_ylabel("Number of Samples", fontsize=10, fontweight='bold', color="#334155")
    ax.legend(frameon=True, facecolor="#ffffff", edgecolor="#e2e8f0", loc='upper left', fontsize=9)
    ax.grid(axis='y', linestyle='--', alpha=0.5)

    # 4B: SLOC Density / CDF Comparison
    ax = axes[1]
    ax.set_facecolor('#ffffff')
    v4_slocs_sorted = sorted(slocs)
    cs_slocs_sorted = sorted(cs_slocs)

    # Plot empirical CDFs
    y_v4 = [i / len(v4_slocs_sorted) for i in range(len(v4_slocs_sorted))]
    y_cs = [i / len(cs_slocs_sorted) for i in range(len(cs_slocs_sorted))]

    ax.plot(v4_slocs_sorted, y_v4, label=f"CodeDEE V4 (Median: {sorted(slocs)[len(slocs)//2]} SLOC)", color="#6366f1", linewidth=2.5)
    ax.plot(cs_slocs_sorted, y_cs, label=f"CyberSecEval (Median: {sorted(cs_slocs)[len(cs_slocs)//2]} SLOC)", color="#0ea5e9", linewidth=2.5, linestyle="--")

    ax.set_title("B. Cumulative Code Complexity / Length (SLOC CDF)", fontsize=12, fontweight='bold', pad=12, color="#0f172a")
    ax.set_xlabel("Source Lines of Code (SLOC)", fontsize=10, fontweight='bold', color="#334155")
    ax.set_ylabel("Cumulative Probability (CDF)", fontsize=10, fontweight='bold', color="#334155")
    ax.set_xlim(0, 250)
    ax.set_ylim(0, 1.02)
    ax.legend(frameon=True, facecolor="#ffffff", edgecolor="#e2e8f0", loc='lower right', fontsize=10)
    ax.grid(True, linestyle='--', alpha=0.5)

    plt.tight_layout()
    out4 = VIZ_DIR / "dataset_comparison_v4_vs_cyberseceval.png"
    plt.savefig(out4, dpi=300)
    plt.close()
    print(f"Saved: {out4}")

def generate_interactive_dashboard(ds_data):
    """Generate high-impact, modern interactive HTML dashboard with Chart.js."""
    dashboard_path = VIZ_DIR / "codedee_all_datasets_dashboard.html"

    # Precompute statistics for embed
    stats = {}
    for d in DATASETS_INFO:
        did = d["id"]
        records = ds_data[did]
        total = len(records)
        vuln = sum(1 for r in records if r.get("is_vulnerable", True))
        safe = sum(1 for r in records if not r.get("is_vulnerable", True))
        langs = Counter(str(r.get("language","")).lower() for r in records)
        cwes = Counter(r.get("cwe_id","Unknown") for r in records)
        slocs = [r.get("original_code","").count('\n')+1 for r in records]
        chars = [len(r.get("original_code","")) for r in records]
        
        stats[did] = {
            "name": d["name"],
            "total": total,
            "vuln": vuln,
            "safe": safe,
            "languages": dict(langs),
            "cwes": dict(cwes.most_common(20)),
            "all_cwes": dict(cwes),
            "avg_sloc": round(sum(slocs)/total, 1) if total else 0,
            "median_sloc": sorted(slocs)[total//2] if total else 0,
            "max_sloc": max(slocs) if total else 0,
            "avg_chars": round(sum(chars)/total, 1) if total else 0,
            "median_chars": sorted(chars)[total//2] if total else 0,
            "max_chars": max(chars) if total else 0
        }

    stats_json = json.dumps(stats, ensure_ascii=False)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CodeDEE - Multi-Dataset & Benchmark Intelligence Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #0b0f19;
            --surface: #111827;
            --surface-card: #1f2937;
            --surface-border: #374151;
            --primary: #6366f1;
            --primary-hover: #4f46e5;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-yellow: #f59e0b;
            --accent-blue: #3b82f6;
            --accent-purple: #8b5cf6;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }}
        body {{
            background: var(--bg);
            color: var(--text-main);
            padding: 24px 32px;
            min-height: 100vh;
        }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--surface-border);
            padding-bottom: 20px;
            margin-bottom: 24px;
        }}
        .brand {{
            display: flex;
            align-items: center;
            gap: 14px;
        }}
        .brand-badge {{
            background: linear-gradient(135deg, #4f46e5, #06b6d4);
            color: white;
            font-size: 13px;
            font-weight: 700;
            padding: 6px 12px;
            border-radius: 8px;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }}
        h1 {{
            font-size: 24px;
            font-weight: 800;
            letter-spacing: -0.5px;
        }}
        .subtitle {{
            color: var(--text-muted);
            font-size: 14px;
            margin-top: 4px;
        }}
        .header-meta {{
            text-align: right;
            font-size: 13px;
            color: var(--text-muted);
        }}
        .header-meta span {{
            color: var(--primary);
            font-weight: 600;
        }}

        /* Dataset Selector Nav */
        .dataset-tabs {{
            display: flex;
            gap: 12px;
            margin-bottom: 24px;
            overflow-x: auto;
            padding-bottom: 4px;
        }}
        .tab-btn {{
            background: var(--surface);
            border: 1px solid var(--surface-border);
            color: var(--text-muted);
            padding: 12px 20px;
            border-radius: 10px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
            transition: all 0.2s ease;
        }}
        .tab-btn:hover {{
            background: var(--surface-card);
            color: var(--text-main);
            border-color: var(--primary);
        }}
        .tab-btn.active {{
            background: rgba(99, 102, 241, 0.15);
            border-color: var(--primary);
            color: white;
            box-shadow: 0 0 15px rgba(99, 102, 241, 0.25);
        }}
        .pill-count {{
            background: rgba(255, 255, 255, 0.1);
            padding: 2px 8px;
            border-radius: 20px;
            font-size: 12px;
            font-family: 'JetBrains Mono', monospace;
        }}

        /* Summary Metric Cards */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .metric-card {{
            background: var(--surface);
            border: 1px solid var(--surface-border);
            border-radius: 12px;
            padding: 18px 20px;
            position: relative;
            overflow: hidden;
        }}
        .metric-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: var(--primary);
        }}
        .metric-card.green::before {{ background: var(--accent-green); }}
        .metric-card.red::before {{ background: var(--accent-red); }}
        .metric-card.yellow::before {{ background: var(--accent-yellow); }}
        .metric-card.blue::before {{ background: var(--accent-blue); }}
        
        .metric-title {{
            font-size: 12px;
            text-transform: uppercase;
            font-weight: 700;
            color: var(--text-muted);
            letter-spacing: 0.5px;
        }}
        .metric-value {{
            font-size: 28px;
            font-weight: 800;
            margin-top: 6px;
            font-family: 'JetBrains Mono', monospace;
            color: #fff;
        }}
        .metric-desc {{
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 4px;
        }}

        /* Charts Layout */
        .charts-row {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 24px;
        }}
        .charts-row.triple {{
            grid-template-columns: 1fr 1fr 1fr;
        }}
        .charts-row.full {{
            grid-template-columns: 1fr;
        }}
        .chart-box {{
            background: var(--surface);
            border: 1px solid var(--surface-border);
            border-radius: 14px;
            padding: 20px 22px;
            display: flex;
            flex-direction: column;
        }}
        .chart-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }}
        .chart-title {{
            font-size: 16px;
            font-weight: 700;
            color: #fff;
        }}
        .chart-badge {{
            font-size: 11px;
            background: var(--surface-card);
            border: 1px solid var(--surface-border);
            padding: 4px 10px;
            border-radius: 6px;
            color: var(--text-muted);
        }}
        .canvas-container {{
            position: relative;
            flex-grow: 1;
            min-height: 280px;
        }}

        /* Table of CWE Distribution */
        .cwe-table-container {{
            max-height: 340px;
            overflow-y: auto;
            border: 1px solid var(--surface-border);
            border-radius: 8px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            text-align: left;
        }}
        th {{
            background: var(--surface-card);
            padding: 10px 14px;
            color: var(--text-muted);
            font-weight: 600;
            position: sticky;
            top: 0;
            z-index: 2;
        }}
        td {{
            padding: 10px 14px;
            border-bottom: 1px solid var(--surface-border);
        }}
        tr:hover td {{
            background: rgba(255, 255, 255, 0.03);
        }}
        .cwe-tag {{
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            color: var(--primary);
            background: rgba(99, 102, 241, 0.1);
            padding: 2px 6px;
            border-radius: 4px;
        }}
        .pct-bar {{
            height: 6px;
            background: var(--primary);
            border-radius: 3px;
        }}

        /* Export Bar */
        .footer-bar {{
            margin-top: 30px;
            padding: 16px 20px;
            background: var(--surface);
            border: 1px solid var(--surface-border);
            border-radius: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .footer-note {{
            font-size: 13px;
            color: var(--text-muted);
        }}
    </style>
</head>
<body>

    <header>
        <div class="brand">
            <div class="brand-badge">CodeDEE Intelligence</div>
            <div>
                <h1>Benchmark Datasets & Taxonomy Dashboard</h1>
                <div class="subtitle">Multi-Language Vulnerability Benchmark (Python, JavaScript, TypeScript) & CyberSecEval Overlap</div>
            </div>
        </div>
        <div class="header-meta">
            Academic Year: <span>2026 (Semester 1)</span><br>
            Official Taxonomy: <span>28 Vulnerabilities / 27 Unique CWEs</span>
        </div>
    </header>

    <!-- Dataset Selection Navigation -->
    <div class="dataset-tabs">
        <button class="tab-btn" onclick="selectDataset('all')">
            🌐 All Datasets Comparison
            <span class="pill-count">5 Datasets</span>
        </button>
        <button class="tab-btn active" onclick="selectDataset('v4')">
            ⭐ Version 4 (Vuln + Safe Patches)
            <span class="pill-count">1,911</span>
        </button>
        <button class="tab-btn" onclick="selectDataset('v3')">
            📂 Version 3 (Multi-Function Vuln)
            <span class="pill-count">967</span>
        </button>
        <button class="tab-btn" onclick="selectDataset('v2')">
            📄 Version 2 (Single-Function Clean)
            <span class="pill-count">928</span>
        </button>
        <button class="tab-btn" onclick="selectDataset('v1')">
            📦 Version 1 (Raw Unfiltered)
            <span class="pill-count">1,208</span>
        </button>
        <button class="tab-btn" onclick="selectDataset('cyberseceval')">
            🛡️ Meta CyberSecEval External
            <span class="pill-count">507</span>
        </button>
    </div>

    <!-- Dynamic Metrics Cards -->
    <div class="metrics-grid" id="metricsContainer">
        <!-- Injected via JavaScript -->
    </div>

    <!-- Main Dynamic Visualizations -->
    <div id="viewsContainer">
        <!-- Injected dynamically based on active tab -->
    </div>

    <div class="footer-bar">
        <div class="footer-note">
            🚀 <strong>CodeDEE Dual-Lens Engine:</strong> All datasets conform to the official 28 CWE Taxonomy and can be benchmarked via <code>python scripts/run_full_scale_benchmark.py --dataset &lt;v1|v2|v3|v4|cyberseceval&gt;</code>.
        </div>
        <div>
            <span style="font-size:12px; color:var(--text-muted);">Generated High-Res PNG Figures saved to <code>visualizations/*.png</code></span>
        </div>
    </div>

    <script>
        const stats = {stats_json};
        let currentTab = 'v4';
        let charts = {{}};

        function selectDataset(key) {{
            currentTab = key;
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            event.currentTarget.classList.add('active');
            renderDashboard();
        }}

        function destroyCharts() {{
            Object.values(charts).forEach(c => {{
                if (c) c.destroy();
            }});
            charts = {{}};
        }}

        function renderDashboard() {{
            destroyCharts();
            const metricsDiv = document.getElementById('metricsContainer');
            const viewsDiv = document.getElementById('viewsContainer');

            if (currentTab === 'all') {{
                renderAllComparison(metricsDiv, viewsDiv);
            }} else {{
                renderSingleDataset(currentTab, metricsDiv, viewsDiv);
            }}
        }}

        function renderAllComparison(metricsDiv, viewsDiv) {{
            metricsDiv.innerHTML = `
                <div class="metric-card blue">
                    <div class="metric-title">Total Benchmark Corpus</div>
                    <div class="metric-value">5,521</div>
                    <div class="metric-desc">Aggregate samples across 5 datasets</div>
                </div>
                <div class="metric-card green">
                    <div class="metric-title">Master Production Set (V4)</div>
                    <div class="metric-value">1,911</div>
                    <div class="metric-desc">Paired vulnerable + safe controls</div>
                </div>
                <div class="metric-card red">
                    <div class="metric-title">Pure Vulnerable Corpus (V3)</div>
                    <div class="metric-value">967</div>
                    <div class="metric-desc">Multi-function snippets (<=320 lines)</div>
                </div>
                <div class="metric-card yellow">
                    <div class="metric-title">External CyberSecEval Corpus</div>
                    <div class="metric-value">507</div>
                    <div class="metric-desc">Meta PurpleLlama Real-World Python/JS</div>
                </div>
            `;

            viewsDiv.innerHTML = `
                <div class="charts-row">
                    <div class="chart-box">
                        <div class="chart-header">
                            <div class="chart-title">A. Dataset Sample Volume & Composition Comparison</div>
                            <div class="chart-badge">Volume Comparison</div>
                        </div>
                        <div class="canvas-container">
                            <canvas id="allVolChart"></canvas>
                        </div>
                    </div>
                    <div class="chart-box">
                        <div class="chart-header">
                            <div class="chart-title">B. Language Distribution across Datasets</div>
                            <div class="chart-badge">Python / JS / TS</div>
                        </div>
                        <div class="canvas-container">
                            <canvas id="allLangChart"></canvas>
                        </div>
                    </div>
                </div>
                <div class="charts-row full">
                    <div class="chart-box">
                        <div class="chart-header">
                            <div class="chart-title">C. Side-by-Side CWE Overlap: CodeDEE V4 vs Meta CyberSecEval</div>
                            <div class="chart-badge">Taxonomy Overlap</div>
                        </div>
                        <div class="canvas-container" style="min-height:360px;">
                            <canvas id="overlapChart"></canvas>
                        </div>
                    </div>
                </div>
            `;

            // Chart A: Volume
            const ctxA = document.getElementById('allVolChart').getContext('2d');
            const dKeys = ['v1', 'v2', 'v3', 'v4', 'cyberseceval'];
            const labels = dKeys.map(k => stats[k].name.split(' (')[0]);
            const vulns = dKeys.map(k => stats[k].vuln);
            const safes = dKeys.map(k => stats[k].safe);

            charts['allVol'] = new Chart(ctxA, {{
                type: 'bar',
                data: {{
                    labels: labels,
                    datasets: [
                        {{ label: 'Vulnerable Samples', data: vulns, backgroundColor: '#ef4444' }},
                        {{ label: 'Safe Patched Controls (CWE-NONE)', data: safes, backgroundColor: '#10b981' }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        x: {{ stacked: true, grid: {{ color: '#1f2937' }} }},
                        y: {{ stacked: true, grid: {{ color: '#1f2937' }} }}
                    }}
                }}
            }});

            // Chart B: Languages
            const ctxB = document.getElementById('allLangChart').getContext('2d');
            const pyData = dKeys.map(k => stats[k].languages['python'] || 0);
            const jsData = dKeys.map(k => stats[k].languages['javascript'] || 0);
            const tsData = dKeys.map(k => stats[k].languages['typescript'] || 0);

            charts['allLang'] = new Chart(ctxB, {{
                type: 'bar',
                data: {{
                    labels: labels,
                    datasets: [
                        {{ label: 'Python', data: pyData, backgroundColor: '#3b82f6' }},
                        {{ label: 'JavaScript', data: jsData, backgroundColor: '#f59e0b' }},
                        {{ label: 'TypeScript', data: tsData, backgroundColor: '#8b5cf6' }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        x: {{ grid: {{ color: '#1f2937' }} }},
                        y: {{ grid: {{ color: '#1f2937' }} }}
                    }}
                }}
            }});

            // Chart C: Overlap
            const ctxC = document.getElementById('overlapChart').getContext('2d');
            const csCwes = Object.keys(stats['cyberseceval'].all_cwes);
            const v4CweCounts = csCwes.map(c => stats['v4'].all_cwes[c] || 0);
            const csCweCounts = csCwes.map(c => stats['cyberseceval'].all_cwes[c] || 0);

            charts['overlap'] = new Chart(ctxC, {{
                type: 'bar',
                data: {{
                    labels: csCwes,
                    datasets: [
                        {{ label: 'CodeDEE Version 4 (Ours)', data: v4CweCounts, backgroundColor: '#6366f1' }},
                        {{ label: 'Meta CyberSecEval (External)', data: csCweCounts, backgroundColor: '#0ea5e9' }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        x: {{ grid: {{ color: '#1f2937' }} }},
                        y: {{ grid: {{ color: '#1f2937' }} }}
                    }}
                }}
            }});
        }}

        function renderSingleDataset(key, metricsDiv, viewsDiv) {{
            const d = stats[key];

            metricsDiv.innerHTML = `
                <div class="metric-card blue">
                    <div class="metric-title">Total Samples</div>
                    <div class="metric-value">${{d.total.toLocaleString()}}</div>
                    <div class="metric-desc">${{d.name}}</div>
                </div>
                <div class="metric-card red">
                    <div class="metric-title">Vulnerable Samples</div>
                    <div class="metric-value">${{d.vuln.toLocaleString()}}</div>
                    <div class="metric-desc">${{((d.vuln/d.total)*100).toFixed(1)}}% of dataset</div>
                </div>
                <div class="metric-card green">
                    <div class="metric-title">Safe Patched Controls</div>
                    <div class="metric-value">${{d.safe.toLocaleString()}}</div>
                    <div class="metric-desc">${{((d.safe/d.total)*100).toFixed(1)}}% (CWE-NONE)</div>
                </div>
                <div class="metric-card yellow">
                    <div class="metric-title">Code Length Profile</div>
                    <div class="metric-value">${{d.median_sloc}} <span style="font-size:16px;">SLOC</span></div>
                    <div class="metric-desc">Mean: ${{d.avg_sloc}} | Max: ${{d.max_sloc}} SLOC</div>
                </div>
            `;

            viewsDiv.innerHTML = `
                <div class="charts-row">
                    <div class="chart-box">
                        <div class="chart-header">
                            <div class="chart-title">Class & Language Proportion</div>
                            <div class="chart-badge">Donut Breakdown</div>
                        </div>
                        <div class="canvas-container" style="display:flex; justify-content:center; align-items:center;">
                            <canvas id="singleDonutChart"></canvas>
                        </div>
                    </div>
                    <div class="chart-box">
                        <div class="chart-header">
                            <div class="chart-title">Top Vulnerability CWE Distribution</div>
                            <div class="chart-badge">Frequency Ranking</div>
                        </div>
                        <div class="canvas-container">
                            <canvas id="singleCweChart"></canvas>
                        </div>
                    </div>
                </div>

                <div class="charts-row full">
                    <div class="chart-box">
                        <div class="chart-header">
                            <div class="chart-title">Detailed Vulnerability Catalog Breakdown (${{Object.keys(d.all_cwes).length}} Unique CWEs)</div>
                            <div class="chart-badge">Data Table</div>
                        </div>
                        <div class="cwe-table-container">
                            <table>
                                <thead>
                                    <tr>
                                        <th>CWE ID</th>
                                        <th>Sample Count</th>
                                        <th>Percentage</th>
                                        <th>Visual Bar</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${{Object.entries(d.all_cwes).sort((a,b) => b[1] - a[1]).map(([cwe, count]) => `
                                        <tr>
                                            <td><span class="cwe-tag">${{cwe}}</span></td>
                                            <td><strong>${{count}}</strong> samples</td>
                                            <td>${{((count/d.total)*100).toFixed(1)}}%</td>
                                            <td style="width: 40%;">
                                                <div class="pct-bar" style="width: ${{Math.min(100, Math.max(3, (count/d.total)*100*2))}}%;"></div>
                                            </td>
                                        </tr>
                                    `).join('')}}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            `;

            // Single Donut: Languages
            const ctxDonut = document.getElementById('singleDonutChart').getContext('2d');
            const lKeys = Object.keys(d.languages);
            const lVals = Object.values(d.languages);
            const lColors = lKeys.map(k => k === 'python' ? '#3b82f6' : (k === 'javascript' ? '#f59e0b' : '#8b5cf6'));

            charts['singleDonut'] = new Chart(ctxDonut, {{
                type: 'doughnut',
                data: {{
                    labels: lKeys.map(k => k.toUpperCase()),
                    datasets: [{{
                        data: lVals,
                        backgroundColor: lColors,
                        borderWidth: 2,
                        borderColor: '#111827'
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ position: 'bottom', labels: {{ color: '#94a3b8' }} }}
                    }}
                }}
            }});

            // Single CWE Bar
            const ctxBar = document.getElementById('singleCweChart').getContext('2d');
            const topCwes = Object.entries(d.cwes).filter(([k]) => k !== 'CWE-NONE').slice(0, 10);
            charts['singleBar'] = new Chart(ctxBar, {{
                type: 'bar',
                data: {{
                    labels: topCwes.map(c => c[0]),
                    datasets: [{{
                        label: 'Vulnerability Count',
                        data: topCwes.map(c => c[1]),
                        backgroundColor: '#6366f1'
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        x: {{ grid: {{ color: '#1f2937' }} }},
                        y: {{ grid: {{ color: '#1f2937' }} }}
                    }}
                }}
            }});
        }}

        // Initialize with default tab (V4)
        renderDashboard();
    </script>
</body>
</html>
"""

    dashboard_path.write_text(html_content, encoding="utf-8")
    print(f"Saved: {dashboard_path}")

def main():
    print("Loading all 5 benchmark datasets...")
    ds_data = {}
    for d in DATASETS_INFO:
        records = load_dataset(d["file"])
        ds_data[d["id"]] = records
        print(f"  {d['name']}: {len(records)} samples loaded.")

    print("\nGenerating publication-quality PNG figures for LaTeX / presentation...")
    generate_png_visualizations(ds_data)

    print("\nGenerating interactive HTML dashboard...")
    generate_interactive_dashboard(ds_data)
    print("\nDone! Visualizations generated successfully.")

if __name__ == "__main__":
    main()
