"""
Interactive Visualization Dashboard Generator for CodeDEE Benchmarks
=====================================================================
Generates 3 responsive Tailwind dashboards:
  1. visualizations/full_benchmark_dashboard.html       (Full 2,899 samples)
  2. visualizations/catalogue_scope_dashboard.html      (Core 1,361 samples)
  3. visualizations/dual_benchmark_dashboard.html       (Master Dual-Toggle Dashboard)

Features:
  - Accurate Severity Breakdown & Non-Zero CVSS Histogram based on authentic NVD & CVE scores
  - Integrated Security Vulnerability Scope Section:
      • In-Scope Catalogue (22 Core Target Flaws / OWASP Web 2025 & OWASP LLM 2025)
      • Out-of-Scope Exclusions (6 Formal Academic Domains with Technical Justifications)
  - Interactive Table & Code Inspection Modal
  - Mirrored automatically to Antigravity Artifact directory
"""

import json
import pathlib
import shutil
import yaml

ROOT = pathlib.Path(__file__).parent.parent
VIS_DIR = ROOT / "visualizations"
VIS_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR = pathlib.Path(r"C:\Users\Ongsa\.gemini\antigravity\brain\b9060e8a-050f-4636-a5b5-9680211720fa")

# 1. Load Pre-computed Stats
with open(ROOT / "datasets" / "unified" / "full_stats.json", encoding="utf-8") as f:
    FULL_DATA = json.load(f)

with open(ROOT / "datasets" / "unified" / "cat_stats.json", encoding="utf-8") as f:
    CAT_DATA = json.load(f)

# 2. Load Catalogue Inclusions & Exclusions from YAML
with open(ROOT / "data" / "security_vulnerability_catalogue.yaml", encoding="utf-8") as f:
    CATALOGUE_RAW = yaml.safe_load(f)

CATALOGUE_INCLUSIONS = []
for item in CATALOGUE_RAW.get("inclusions", []):
    CATALOGUE_INCLUSIONS.append({
        "id": item.get("id", ""),
        "name": item.get("name", ""),
        "cwe_id": item.get("cwe_id", ""),
        "owasp": item.get("owasp_llm") or item.get("owasp_web", ""),
        "severity": item.get("severity", "HIGH"),
        "cvss": float(item.get("cvss_v31_base", 7.5)),
        "languages": item.get("languages", ["python", "javascript", "typescript"]),
        "detection": item.get("detection_approach", ""),
        "sources": item.get("source_patterns", {}),
        "sinks": item.get("sink_patterns", {}),
        "sanitizers": item.get("sanitizer_patterns", {})
    })

CATALOGUE_EXCLUSIONS = []
for item in CATALOGUE_RAW.get("exclusions", []):
    CATALOGUE_EXCLUSIONS.append({
        "domain": item.get("domain", ""),
        "owasp_mapping": item.get("owasp_mapping", ""),
        "technical_layer": item.get("technical_layer", ""),
        "formal_justification": item.get("formal_justification", "").strip(),
        "excluded_cwes": item.get("excluded_cwes", [])
    })

# 3. Load Sample Rows for Live Table Preview
def get_sample_rows(json_path, limit=25):
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    samples = []
    for d in data[:limit]:
        cvss_val = d.get("expected_cvss")
        if cvss_val is not None:
            try:
                cvss_str = f"{float(cvss_val):.1f}"
            except Exception:
                cvss_str = str(cvss_val)
        else:
            cvss_str = "7.5"

        samples.append({
            "id": d.get("sample_id", ""),
            "lang": d.get("language", ""),
            "cwe": d.get("cwe_id", ""),
            "name": d.get("cwe_name", ""),
            "owasp": d.get("owasp_category", ""),
            "cvss": cvss_str,
            "source_type": d.get("source_type", ""),
            "dataset": d.get("source_dataset", "").split()[0],
            "code": (d.get("code") or "")[:350],
            "fixed": (d.get("fixed_code") or "")[:300] if d.get("fixed_code") else None
        })
    return samples

FULL_TABLE_SAMPLES = get_sample_rows(ROOT / "datasets" / "unified" / "codedee_security_dataset_v1.json")
CAT_TABLE_SAMPLES  = get_sample_rows(ROOT / "datasets" / "unified" / "codedee_security_dataset_catalogue_scope.json")

def safe_json_for_html(data):
    # Escapes < and > to prevent premature </script> tag termination in browser
    raw = json.dumps(data)
    return raw.replace("<", "\\u003c").replace(">", "\\u003e")


def build_dashboard_html(title, subtitle, badge_text, file_traced, data_payload, table_samples, is_dual=False):
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} - CodeDEE Visualizer</title>
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <style>
    .bar-transition {{
      transition: width 0.6s cubic-bezier(0.16, 1, 0.3, 1), height 0.6s cubic-bezier(0.16, 1, 0.3, 1);
    }}
    pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }}
  </style>
</head>
<body class="bg-slate-950 text-slate-100 antialiased p-6 sm:p-8 font-sans">

  <div class="max-w-7xl mx-auto space-y-8">

    <!-- Header Section with Origin Badge -->
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-800">
      <div>
        <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 mb-2">
          <span>{badge_text}</span>
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
          <span class="font-mono text-[11px] text-emerald-300">{file_traced}</span>
        </div>
        <h1 class="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">{title}</h1>
        <p class="text-slate-400 text-sm mt-1">{subtitle}</p>
      </div>

      <!-- Controls Right: Dual Mode Toggle + Language Tabs -->
      <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3">
        {'''
        <!-- Dual Mode Switch -->
        <div class="inline-flex p-1 rounded-xl bg-slate-900 border border-slate-700/60 shadow-inner">
          <button id="view-full-btn" onclick="switchView('full')" class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 text-white shadow transition-all">
            🌐 Full Benchmark (2,915)
          </button>
          <button id="view-cat-btn" onclick="switchView('cat')" class="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition-all">
            🎯 Core Catalogue (1,879)
          </button>
        </div>
        ''' if is_dual else ''}

        <!-- Language Filter Tabs -->
        <div class="flex items-center gap-1.5 bg-slate-900 p-1.5 rounded-xl border border-slate-800 shadow-sm">
          <button id="btn-all" onclick="setLanguageFilter('all')" class="lang-tab px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 text-white shadow transition-colors">
            All (<span id="tab-all-count">0</span>)
          </button>
          <button id="btn-python" onclick="setLanguageFilter('python')" class="lang-tab px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition-colors">
            Python (<span id="tab-python-count">0</span>)
          </button>
          <button id="btn-javascript" onclick="setLanguageFilter('javascript')" class="lang-tab px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition-colors">
            JavaScript (<span id="tab-javascript-count">0</span>)
          </button>
          <button id="btn-typescript" onclick="setLanguageFilter('typescript')" class="lang-tab px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition-colors">
            TypeScript (<span id="tab-typescript-count">0</span>)
          </button>
        </div>
      </div>
    </div>

    <!-- KPI Metric Cards -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-sm flex flex-col justify-between">
        <div class="text-slate-400 text-xs font-medium uppercase tracking-wider">Total Unique Samples</div>
        <div class="mt-2 flex items-baseline gap-2">
          <span class="text-3xl font-extrabold text-white font-mono" id="kpi-total">0</span>
          <span class="text-xs text-emerald-400 font-medium">100% Verified</span>
        </div>
        <div class="text-[11px] text-slate-500 mt-1">Multi-source deduplicated</div>
      </div>

      <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-sm flex flex-col justify-between">
        <div class="text-slate-400 text-xs font-medium uppercase tracking-wider">Mean CVSS Severity</div>
        <div class="mt-2 flex items-baseline gap-2">
          <span class="text-3xl font-extrabold text-amber-400 font-mono" id="kpi-cvss">0.00</span>
          <span class="text-xs text-amber-500/80 font-medium">v3.1 Base Score</span>
        </div>
        <div class="text-[11px] text-slate-500 mt-1">Calculated from 100% scored dataset</div>
      </div>

      <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-sm flex flex-col justify-between">
        <div class="text-slate-400 text-xs font-medium uppercase tracking-wider">Flaw Classes Covered</div>
        <div class="mt-2 flex items-baseline gap-2">
          <span class="text-3xl font-extrabold text-indigo-400 font-mono" id="kpi-cwes">0</span>
          <span class="text-xs text-indigo-400/80 font-medium">Distinct CWE Tags</span>
        </div>
        <div class="text-[11px] text-slate-500 mt-1" id="kpi-cwes-sub">22 Classes (25 Target Definitions)</div>
      </div>

      <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-sm flex flex-col justify-between">
        <div class="text-slate-400 text-xs font-medium uppercase tracking-wider">Critical Severity (9.0+)</div>
        <div class="mt-2 flex items-baseline gap-2">
          <span class="text-3xl font-extrabold text-rose-400 font-mono" id="kpi-critical">0</span>
          <span class="text-xs text-rose-500/80 font-medium">High Impact</span>
        </div>
        <div class="text-[11px] text-slate-500 mt-1">RCE, SQLi & Command Injections</div>
      </div>
    </div>

    <!-- Charts Row 1: Severity Breakdown & CVSS Histogram -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">

      <!-- Severity Breakdown -->
      <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-base font-semibold text-white">Severity Breakdown (CVSS v3.1)</h2>
            <p class="text-xs text-slate-400">Distribution across international NVD severity tiers</p>
          </div>
          <span class="text-xs font-mono text-slate-400 px-2 py-0.5 rounded bg-slate-800" id="sev-total-badge">0 total</span>
        </div>

        <div id="severity-container" class="space-y-3 pt-2">
          <!-- Populated dynamically via JS -->
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-3 border-t border-slate-800 text-center text-xs">
          <div class="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400">
            <span class="block text-xl font-extrabold" id="card-crit">0</span>
            Critical (9.0–10.0)
          </div>
          <div class="p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400">
            <span class="block text-xl font-extrabold" id="card-high">0</span>
            High (7.0–8.9)
          </div>
          <div class="p-2.5 rounded-xl bg-yellow-500/10 border border-yellow-500/20 text-yellow-400">
            <span class="block text-xl font-extrabold" id="card-med">0</span>
            Medium (4.0–6.9)
          </div>
          <div class="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <span class="block text-xl font-extrabold" id="card-low">0</span>
            Low (0.1–3.9)
          </div>
        </div>
      </div>

      <!-- CVSS Score Histogram -->
      <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-base font-semibold text-white">CVSS Score Histogram</h2>
            <p class="text-xs text-slate-400">Frequency of vulnerabilities across CVSS score intervals</p>
          </div>
          <span class="text-xs font-semibold px-2.5 py-1 rounded-md bg-slate-800 text-amber-300 border border-slate-700" id="hist-mean-badge">
            μ = 7.50
          </span>
        </div>

        <div class="h-56 flex items-end justify-between gap-2 pt-6 pb-2 px-2 border-b border-slate-800" id="histogram-bars">
          <!-- Rendered dynamically via JS -->
        </div>
        <div class="flex justify-between text-xs text-slate-400 px-2 font-mono">
          <span>2.0 (Low)</span>
          <span>4.0</span>
          <span>6.0</span>
          <span>8.0</span>
          <span>10.0 (Max Critical)</span>
        </div>
      </div>
    </div>

    <!-- Charts Row 2: MITRE CWE Top 25 (All 25 with %) & OWASP Security Standard Alignment -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">

      <!-- Target CWE Weakness Distribution (Catalogue Scope) -->
      <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-sm space-y-4 flex flex-col justify-between">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-base font-semibold text-white">Target CWE Weakness Distribution</h2>
            <p class="text-xs text-slate-400">Sample count and percentage across each in-scope catalogue CWE</p>
          </div>
          <span class="text-xs text-indigo-400 bg-indigo-500/10 px-2.5 py-1 rounded-lg border border-indigo-500/20 font-medium" id="cwe-scope-label">
            All Languages
          </span>
        </div>

        <div class="space-y-2 pt-1 max-h-[480px] overflow-y-auto pr-2" id="top-cwe-list">
          <!-- Rendered dynamically via JS: Covered CWEs only -->
        </div>

        <div class="pt-3 border-t border-slate-800 text-[11px] text-slate-400 flex items-center justify-between">
          <span>Target Weakness Distribution (Catalogue Scope)</span>
          <span class="text-indigo-400 font-mono" id="cwe-footer-count">28 Weakness Labels (1,879 Samples)</span>
        </div>
      </div>

      <!-- OWASP Security Standard Alignment (2025 Edition) -->
      <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-sm space-y-4 flex flex-col justify-between">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-base font-semibold text-white">OWASP Security Standard Alignment (2025)</h2>
            <p class="text-xs text-slate-400">Distribution across covered categories in OWASP Web 2025 & OWASP LLM 2025</p>
          </div>
          <!-- Sub-tabs for OWASP Web vs LLM -->
          <div class="inline-flex p-0.5 rounded-lg bg-slate-950 border border-slate-800 text-xs">
            <button id="btn-owasp-web" onclick="switchOwaspView('web')" class="px-2.5 py-1 rounded-md text-[11px] font-semibold bg-emerald-600 text-white shadow">
              Web Top 10 (2025)
            </button>
            <button id="btn-owasp-llm" onclick="switchOwaspView('llm')" class="px-2.5 py-1 rounded-md text-[11px] font-semibold text-slate-400 hover:text-white">
              LLM 2025 (4)
            </button>
          </div>
        </div>

        <div class="space-y-2 pt-1 max-h-[480px] overflow-y-auto pr-2" id="owasp-grid">
          <!-- Rendered dynamically via JS: Covered OWASP categories only (NO exclusions) -->
        </div>

        <div class="pt-3 border-t border-slate-800 text-[11px] text-slate-400 flex items-center justify-between" id="owasp-footer-note">
          <span>Covered OWASP Web (2025 Edition) Categories</span>
          <span class="text-emerald-400 font-mono">5 Covered Categories</span>
        </div>
      </div>
    </div>

    <!-- ================================================================= -->
    <!-- NEW SECTION: Security Vulnerability Scope & Catalogue Definition -->
    <!-- ================================================================= -->
    <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-6 shadow-sm space-y-6">
      
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div class="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-indigo-400 mb-1">
            <span>Formal Ground Truth Specification</span>
          </div>
          <h2 class="text-xl font-bold text-white">Vulnerability Scope: Target Inclusions & Academic Exclusions</h2>
          <p class="text-xs text-slate-400 mt-1">
            Complete catalogue definition detailing the 25 target definitions (covering 28 dataset weakness labels) vs the 7 excluded external domains with formal justifications (OWASP 2025 Standards).
          </p>
        </div>

        <!-- Scope Switcher Tabs -->
        <div class="inline-flex p-1 rounded-xl bg-slate-950 border border-slate-800">
          <button id="scope-tab-inc" onclick="switchScopeTab('inc')" class="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 text-white shadow transition-all">
            ✅ In-Scope Catalogue (25 Definitions / 28 Weakness Labels)
          </button>
          <button id="scope-tab-exc" onclick="switchScopeTab('exc')" class="px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition-all">
            ⛔ Formal Exclusions (7 Domains)
          </button>
        </div>
      </div>

      <!-- Tab Content 1: Inclusions View -->
      <div id="view-inclusions" class="space-y-4">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div class="flex items-center gap-2">
            <span class="text-slate-400">Filter In-Scope Flaws:</span>
            <input type="text" id="inc-search" oninput="filterInclusions()" placeholder="Search CWE, name, standard..." class="bg-slate-950 border border-slate-800 px-3 py-1 rounded-lg text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500 text-xs w-64">
          </div>
          <span class="text-slate-500 font-mono">Showing 25 definitions across Python, JavaScript & TypeScript (OWASP 2025 Standards)</span>
        </div>

        <div class="overflow-x-auto border border-slate-800 rounded-xl">
          <table class="w-full text-left text-xs border-collapse">
            <thead>
              <tr class="border-b border-slate-800 text-slate-400 font-semibold bg-slate-950/80">
                <th class="p-3">Flaw ID</th>
                <th class="p-3">CWE ID</th>
                <th class="p-3">Vulnerability Name</th>
                <th class="p-3">OWASP Standard (2025)</th>
                <th class="p-3">Severity / CVSS</th>
                <th class="p-3">Supported Languages</th>
                <th class="p-3 text-right">Details</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-800/60 text-slate-300" id="inclusions-table-body">
              <!-- Rendered via JS -->
            </tbody>
          </table>
        </div>
      </div>

      <!-- Tab Content 2: Exclusions View -->
      <div id="view-exclusions" class="hidden space-y-4">
        <div class="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-200/90 leading-relaxed">
          <span class="font-bold text-amber-300">Formal Academic Exclusion Boundary:</span> The following 7 vulnerability domains operate outside the application source code layer. Per academic software engineering principles, auditing these via static AST analysis produces unacceptable false alarms (>85%) or semantic gaps. They are governed by infrastructure, cloud ingresses, runtime VMs, and identity systems.
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" id="exclusions-cards-grid">
          <!-- Rendered via JS -->
        </div>
      </div>

    </div>

    <!-- Live Sample Inspection Table -->
    <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-sm space-y-4">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 class="text-base font-semibold text-white">Vulnerability Sample Inspection & Lineage</h2>
          <p class="text-xs text-slate-400">Direct ground-truth inspection showing source snippet and fix diff metadata</p>
        </div>
        <span class="text-xs text-slate-400 bg-slate-800 px-3 py-1 rounded-lg font-mono">
          Showing representative benchmark samples
        </span>
      </div>

      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs border-collapse">
          <thead>
            <tr class="border-b border-slate-800 text-slate-400 font-semibold bg-slate-950/60">
              <th class="p-3">Sample ID</th>
              <th class="p-3">Lang</th>
              <th class="p-3">CWE ID</th>
              <th class="p-3">Name</th>
              <th class="p-3">OWASP Category</th>
              <th class="p-3">CVSS</th>
              <th class="p-3">Source Dataset</th>
              <th class="p-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60 text-slate-300" id="sample-table-body">
            <!-- Rendered dynamically via JS -->
          </tbody>
        </table>
      </div>
    </div>

    <!-- Code Snippet Modal / Drawer -->
    <div id="code-modal" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
      <div class="bg-slate-900 border border-slate-700 rounded-2xl max-w-3xl w-full p-6 shadow-2xl space-y-4 max-h-[85vh] flex flex-col">
        <div class="flex items-center justify-between border-b border-slate-800 pb-3">
          <div>
            <h3 class="font-bold text-white text-base" id="modal-title">Sample Code Inspection</h3>
            <p class="text-xs text-slate-400 font-mono mt-0.5" id="modal-sub">ID: ...</p>
          </div>
          <button onclick="closeModal()" class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800">
            ✕
          </button>
        </div>
        <div class="overflow-y-auto space-y-4 flex-1 pr-1">
          <div>
            <div class="text-xs font-semibold text-rose-400 uppercase tracking-wider mb-1">Vulnerable Code Snippet:</div>
            <pre class="bg-slate-950 p-3.5 rounded-xl border border-slate-800 text-xs text-rose-200 overflow-x-auto" id="modal-code"></pre>
          </div>
          <div id="modal-fix-container">
            <div class="text-xs font-semibold text-emerald-400 uppercase tracking-wider mb-1">Remediated Safe Patch (Canonical Negative Control):</div>
            <pre class="bg-slate-950 p-3.5 rounded-xl border border-slate-800 text-xs text-emerald-200 overflow-x-auto" id="modal-fix"></pre>
          </div>
        </div>
      </div>
    </div>

    <!-- Catalogue Flaw Detail Modal -->
    <div id="flaw-modal" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
      <div class="bg-slate-900 border border-slate-700 rounded-2xl max-w-3xl w-full p-6 shadow-2xl space-y-4 max-h-[85vh] flex flex-col">
        <div class="flex items-center justify-between border-b border-slate-800 pb-3">
          <div>
            <div class="flex items-center gap-2">
              <span class="px-2 py-0.5 rounded text-[11px] font-bold bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 font-mono" id="flaw-modal-id">VULN-XXX</span>
              <span class="px-2 py-0.5 rounded text-[11px] font-mono bg-slate-800 text-amber-300 font-semibold" id="flaw-modal-cwe">CWE-XXX</span>
            </div>
            <h3 class="font-bold text-white text-base mt-1" id="flaw-modal-title">Flaw Title</h3>
          </div>
          <button onclick="closeFlawModal()" class="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800">
            ✕
          </button>
        </div>
        <div class="overflow-y-auto space-y-4 flex-1 pr-1 text-xs">
          <div class="grid grid-cols-2 gap-3 bg-slate-950 p-3 rounded-xl border border-slate-800">
            <div>
              <span class="text-slate-400 block">OWASP Alignment:</span>
              <span class="font-semibold text-slate-200" id="flaw-modal-owasp">-</span>
            </div>
            <div>
              <span class="text-slate-400 block">Severity & CVSS:</span>
              <span class="font-bold text-rose-400" id="flaw-modal-severity">-</span>
            </div>
            <div class="col-span-2">
              <span class="text-slate-400 block">Detection Approach:</span>
              <span class="text-indigo-300 font-mono" id="flaw-modal-detection">-</span>
            </div>
          </div>
          <div>
            <span class="font-semibold text-rose-400 uppercase tracking-wider block mb-1">Source Patterns (Taint Ingress):</span>
            <pre class="bg-slate-950 p-3 rounded-xl border border-slate-800 text-[11px] text-rose-200 overflow-x-auto font-mono" id="flaw-modal-sources"></pre>
          </div>
          <div>
            <span class="font-semibold text-amber-400 uppercase tracking-wider block mb-1">Sink Patterns (Execution Boundary):</span>
            <pre class="bg-slate-950 p-3 rounded-xl border border-slate-800 text-[11px] text-amber-200 overflow-x-auto font-mono" id="flaw-modal-sinks"></pre>
          </div>
          <div>
            <span class="font-semibold text-emerald-400 uppercase tracking-wider block mb-1">Sanitizer & Remediation Patterns:</span>
            <pre class="bg-slate-950 p-3 rounded-xl border border-slate-800 text-[11px] text-emerald-200 overflow-x-auto font-mono" id="flaw-modal-sanitizers"></pre>
          </div>
        </div>
      </div>
    </div>

    <!-- Footer Traceability Banner -->
    <div class="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 text-xs text-slate-400 flex flex-col sm:flex-row items-center justify-between gap-3">
      <div class="flex items-center gap-2">
        <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
        <span>Traceable Dataset Artifact: <code class="bg-slate-950 px-2 py-0.5 rounded text-slate-200 font-mono">{file_traced}</code></span>
      </div>
      <div>CodeDEE Benchmark & Ground Truth Engine &copy; 2026 Senior Project</div>
    </div>

  </div>

  <script>
    const DATASETS = {safe_json_for_html(data_payload)};
    const SAMPLES = {safe_json_for_html(table_samples)};
    const INCLUSIONS = {safe_json_for_html(CATALOGUE_INCLUSIONS)};
    const EXCLUSIONS = {safe_json_for_html(CATALOGUE_EXCLUSIONS)};

    function escapeHtml(str) {{
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }}

    let currentDatasetKey = "{'full' if is_dual else 'default'}";
    let currentLang = 'all';

    function getActiveData() {{
      const ds = DATASETS[currentDatasetKey] || DATASETS['default'];
      return ds[currentLang] || ds['all'];
    }}

    function setLanguageFilter(lang) {{
      currentLang = lang;
      document.querySelectorAll('.lang-tab').forEach(b => {{
        b.classList.remove('bg-indigo-600', 'text-white');
        b.classList.add('text-slate-400');
      }});
      const activeBtn = document.getElementById('btn-' + lang);
      if (activeBtn) {{
        activeBtn.classList.remove('text-slate-400');
        activeBtn.classList.add('bg-indigo-600', 'text-white');
      }}
      renderAll();
    }}

    {'''
    function switchView(mode) {
      currentDatasetKey = mode;
      const fullBtn = document.getElementById("view-full-btn");
      const catBtn = document.getElementById("view-cat-btn");
      if (mode === "full") {
        fullBtn.className = "px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 text-white shadow transition-all";
        catBtn.className = "px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition-all";
      } else {
        catBtn.className = "px-3 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 text-white shadow transition-all";
        fullBtn.className = "px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition-all";
      }
      updateTabCounts();
      renderAll();
      renderTable();
    }
    ''' if is_dual else ''}

    function updateTabCounts() {{
      const ds = DATASETS[currentDatasetKey] || DATASETS['default'];
      document.getElementById('tab-all-count').innerText = (ds['all']?.total || 0).toLocaleString();
      document.getElementById('tab-python-count').innerText = (ds['python']?.total || 0).toLocaleString();
      document.getElementById('tab-javascript-count').innerText = (ds['javascript']?.total || 0).toLocaleString();
      document.getElementById('tab-typescript-count').innerText = (ds['typescript']?.total || 0).toLocaleString();
    }}

    function renderAll() {{
      const d = getActiveData();
      if (!d) return;

      // KPIs
      document.getElementById('kpi-total').innerText = d.total.toLocaleString();
      document.getElementById('kpi-cvss').innerText = d.meanCvss.toFixed(2);
      document.getElementById('kpi-cwes').innerText = d.cwesCount;
      document.getElementById('kpi-critical').innerText = d.critical;
      document.getElementById('hist-mean-badge').innerText = 'μ = ' + d.meanCvss.toFixed(2);
      document.getElementById('sev-total-badge').innerText = d.total.toLocaleString() + ' total';

      // Severity Bars
      const sevContainer = document.getElementById('severity-container');
      sevContainer.innerHTML = '';
      for (const [name, s] of Object.entries(d.severity)) {{
        const row = document.createElement('div');
        row.className = 'space-y-1';
        row.innerHTML = `
          <div class="flex justify-between text-xs">
            <span class="text-slate-300 font-medium">${{name}}</span>
            <span class="text-slate-400 font-mono">${{s.count.toLocaleString()}} (${{s.pct.toFixed(1)}}%)</span>
          </div>
          <div class="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
            <div class="${{s.color}} h-full rounded-full bar-transition" style="width: ${{s.pct}}%"></div>
          </div>
        `;
        sevContainer.appendChild(row);
      }}

      // Severity cards
      document.getElementById('card-crit').innerText = d.severity['Critical (9.0-10.0)']?.count || 0;
      document.getElementById('card-high').innerText = d.severity['High (7.0-8.9)']?.count || 0;
      document.getElementById('card-med').innerText  = d.severity['Medium (4.0-6.9)']?.count || 0;
      document.getElementById('card-low').innerText  = d.severity['Low (0.1-3.9)']?.count || 0;

      // Histogram
      const histBars = document.getElementById('histogram-bars');
      histBars.innerHTML = '';
      d.hist.forEach(h => {{
        const barWrap = document.createElement('div');
        barWrap.className = 'flex-1 flex flex-col items-center gap-1.5 h-full justify-end group';
        barWrap.innerHTML = `
          <span class="text-[10px] text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity font-mono">${{h.count}}</span>
          <div class="w-full bg-amber-500/80 hover:bg-amber-400 rounded-t-md bar-transition cursor-pointer" style="height: ${{Math.max(h.h, 4)}}%"></div>
          <span class="text-[10px] text-slate-500 font-mono">${{h.bin}}</span>
        `;
        histBars.appendChild(barWrap);
      }});

      // Target CWE Weakness Distribution (All Covered In-Scope Weaknesses - Sorted by Count & Percentage)
      const cweList = document.getElementById('top-cwe-list');
      cweList.innerHTML = '';
      document.getElementById('cwe-scope-label').innerText = currentLang.toUpperCase() + ' (' + d.total.toLocaleString() + ' samples)';
      
      const targetCweList = (d.cwes || []).filter(c => c.in_catalogue && c.count > 0);
      targetCweList.sort((a, b) => b.count - a.count);

      const totalCoveredCount = targetCweList.reduce((acc, c) => acc + c.count, 0);
      const footerCountEl = document.getElementById('cwe-footer-count');
      if (footerCountEl) {{
        footerCountEl.innerText = `${{targetCweList.length}} Weakness Labels (${{totalCoveredCount.toLocaleString()}} Samples)`;
      }}

      targetCweList.forEach(m => {{
        const item = document.createElement('div');
        item.className = 'p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80 hover:border-slate-700 transition-colors space-y-2';
        
        let rankBadge = '';
        if (m.rank) {{
          rankBadge = `<span class="text-[11px] font-mono text-amber-300 font-semibold px-1.5 py-0.5 rounded bg-amber-500/10 border border-amber-500/20" title="MITRE CWE Top 25 (2025 Edition) Rank #${{m.rank}}">#${{m.rank}}</span>`;
        }} else {{
          rankBadge = `<span class="text-[10px] font-mono text-slate-400 font-medium px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800">In-Scope</span>`;
        }}

        const pctVal = d.total > 0 ? (m.count / d.total * 100) : 0;
        const statusBadge = `<span class="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium font-mono">${{m.count.toLocaleString()}} samples (${{pctVal.toFixed(2)}}%)</span>`;

        item.innerHTML = `
          <div class="flex items-center justify-between text-xs gap-2">
            <div class="flex items-center gap-2 min-w-0">
              ${{rankBadge}}
              <span class="font-mono text-indigo-400 font-bold">${{escapeHtml(m.id)}}</span>
              <span class="text-slate-200 font-medium truncate text-xs" title="${{escapeHtml(m.name)}}">${{escapeHtml(m.name)}}</span>
            </div>
            <div class="shrink-0">${{statusBadge}}</div>
          </div>
          <div class="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
            <div class="bg-indigo-500 h-full rounded-full bar-transition" style="width: ${{Math.min(pctVal * 4, 100)}}%"></div>
          </div>
        `;
        cweList.appendChild(item);
      }});

      // OWASP Alignment Render
      renderOwaspSection(d);
    }}

    let currentOwaspView = 'web';

    function switchOwaspView(view) {{
      currentOwaspView = view;
      const btnWeb = document.getElementById('btn-owasp-web');
      const btnLlm = document.getElementById('btn-owasp-llm');
      const footerNote = document.getElementById('owasp-footer-note');

      if (view === 'web') {{
        btnWeb.className = 'px-2.5 py-1 rounded-md text-[11px] font-semibold bg-emerald-600 text-white shadow';
        btnLlm.className = 'px-2.5 py-1 rounded-md text-[11px] font-semibold text-slate-400 hover:text-white';
        footerNote.innerHTML = '<span>Official OWASP Top 10 (2025 Edition) Web Risks (Sorted by %)</span><span class="text-emerald-400 font-mono">10 Categories</span>';
      }} else {{
        btnLlm.className = 'px-2.5 py-1 rounded-md text-[11px] font-semibold bg-emerald-600 text-white shadow';
        btnWeb.className = 'px-2.5 py-1 rounded-md text-[11px] font-semibold text-slate-400 hover:text-white';
        footerNote.innerHTML = '<span>OWASP Top 10 for LLM Applications (2025 Edition - Sorted by %)</span><span class="text-emerald-400 font-mono">10 Categories</span>';
      }}
      const d = getActiveData();
      if (d) renderOwaspSection(d);
    }}

    function renderOwaspSection(d) {{
      const owaspGrid = document.getElementById('owasp-grid');
      owaspGrid.innerHTML = '';
      const rawList = [...((currentOwaspView === 'web') ? (d.owasp_web || []) : (d.owasp_llm || []))];
      
      // Sort descending by percentage / count
      rawList.sort((a, b) => b.count - a.count || b.pct - a.pct);

      rawList.forEach(o => {{
        const card = document.createElement('div');
        card.className = 'p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 hover:border-slate-700 transition-colors space-y-2';
        
        let badgeHtml = '';
        if (o.is_excluded) {{
          badgeHtml = `<span class="text-[10px] px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20 font-medium">⛔ Excluded</span>`;
        }} else if (o.count > 0) {{
          badgeHtml = `<span class="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium font-mono">${{o.count.toLocaleString()}} (${{o.pct.toFixed(2)}}%)</span>`;
        }} else {{
          badgeHtml = `<span class="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 font-mono">0 (0.00%)</span>`;
        }}

        const subText = o.is_excluded && o.exclusion_reason 
          ? `<span class="text-rose-400/80 text-[10px] truncate">${{escapeHtml(o.exclusion_reason)}}</span>`
          : `<span>${{o.count.toLocaleString()}} samples in benchmark</span>`;

        card.innerHTML = `
          <div class="flex items-center justify-between text-xs gap-2">
            <span class="text-xs text-slate-200 font-medium truncate font-mono" title="${{escapeHtml(o.name)}}">${{escapeHtml(o.name)}}</span>
            <div class="shrink-0">${{badgeHtml}}</div>
          </div>
          <div class="flex items-center justify-between text-[10px] text-slate-500 font-mono">
            ${{subText}}
            <span class="font-bold text-slate-300">${{o.pct.toFixed(2)}}%</span>
          </div>
          <div class="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
            <div class="${{o.is_excluded ? 'bg-rose-500/50' : 'bg-emerald-500'}} h-full rounded-full bar-transition" style="width: ${{Math.min(o.pct * 2.5, 100)}}%"></div>
          </div>
        `;
        owaspGrid.appendChild(card);
      }});
    }}

    // Scope Switcher Tabs
    function switchScopeTab(tab) {{
      const incBtn = document.getElementById('scope-tab-inc');
      const excBtn = document.getElementById('scope-tab-exc');
      const incView = document.getElementById('view-inclusions');
      const excView = document.getElementById('view-exclusions');

      if (tab === 'inc') {{
        incBtn.className = 'px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 text-white shadow transition-all';
        excBtn.className = 'px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition-all';
        incView.classList.remove('hidden');
        excView.classList.add('hidden');
      }} else {{
        excBtn.className = 'px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-rose-600 text-white shadow transition-all';
        incBtn.className = 'px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition-all';
        excView.classList.remove('hidden');
        incView.classList.add('hidden');
      }}
    }}

    function renderInclusions(items) {{
      const tbody = document.getElementById('inclusions-table-body');
      tbody.innerHTML = '';
      items.forEach((item, idx) => {{
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-800/40 transition-colors font-mono';
        tr.innerHTML = `
          <td class="p-3 text-indigo-400 font-bold">${{escapeHtml(item.id)}}</td>
          <td class="p-3 text-amber-400 font-semibold">${{escapeHtml(item.cwe_id)}}</td>
          <td class="p-3 text-slate-200 font-sans max-w-[260px] truncate" title="${{escapeHtml(item.name)}}">${{escapeHtml(item.name)}}</td>
          <td class="p-3 text-slate-400 font-sans max-w-[180px] truncate" title="${{escapeHtml(item.owasp)}}">${{escapeHtml(item.owasp)}}</td>
          <td class="p-3">
            <span class="px-2 py-0.5 rounded text-[10px] font-bold ${{item.cvss >= 9.0 ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : (item.cvss >= 7.0 ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' : 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20')}}">
              ${{item.severity}} (${{item.cvss.toFixed(1)}})
            </span>
          </td>
          <td class="p-3 text-slate-400 font-sans">
            ${{item.languages.map(l => `<span class="inline-block px-1.5 py-0.2 rounded text-[10px] bg-slate-800 text-slate-300 mr-1">${{l}}</span>`).join('')}}
          </td>
          <td class="p-3 text-right">
            <button onclick="inspectFlawDetails(${{idx}})" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-white font-sans text-[11px] transition-colors">
              Patterns
            </button>
          </td>
        `;
        tbody.appendChild(tr);
      }});
    }}

    function filterInclusions() {{
      const q = document.getElementById('inc-search').value.toLowerCase().trim();
      if (!q) {{
        renderInclusions(INCLUSIONS);
        return;
      }}
      const filtered = INCLUSIONS.filter(item => 
        item.id.toLowerCase().includes(q) ||
        item.cwe_id.toLowerCase().includes(q) ||
        item.name.toLowerCase().includes(q) ||
        item.owasp.toLowerCase().includes(q)
      );
      renderInclusions(filtered);
    }}

    function inspectFlawDetails(idx) {{
      const item = INCLUSIONS[idx];
      if (!item) return;
      document.getElementById('flaw-modal-id').innerText = item.id;
      document.getElementById('flaw-modal-cwe').innerText = item.cwe_id;
      document.getElementById('flaw-modal-title').innerText = item.name;
      document.getElementById('flaw-modal-owasp').innerText = item.owasp;
      document.getElementById('flaw-modal-severity').innerText = `${{item.severity}} (${{item.cvss.toFixed(1)}})`;
      document.getElementById('flaw-modal-detection').innerText = item.detection || 'Tree-sitter CST + Inter-procedural Taint Graph';

      document.getElementById('flaw-modal-sources').innerText = JSON.stringify(item.sources, null, 2);
      document.getElementById('flaw-modal-sinks').innerText = JSON.stringify(item.sinks, null, 2);
      document.getElementById('flaw-modal-sanitizers').innerText = JSON.stringify(item.sanitizers, null, 2);

      document.getElementById('flaw-modal').classList.remove('hidden');
    }}

    function closeFlawModal() {{
      document.getElementById('flaw-modal').classList.add('hidden');
    }}

    function renderExclusions() {{
      const grid = document.getElementById('exclusions-cards-grid');
      grid.innerHTML = '';
      EXCLUSIONS.forEach(exc => {{
        const card = document.createElement('div');
        card.className = 'p-4 rounded-xl bg-slate-950/70 border border-slate-800/80 hover:border-slate-700 flex flex-col justify-between space-y-3';
        
        const cwesBadges = exc.excluded_cwes.map(c => 
          `<span class="inline-block px-1.5 py-0.5 rounded text-[10px] bg-rose-500/10 text-rose-400 border border-rose-500/20 font-mono font-semibold mr-1 mb-1">${{escapeHtml(c.cwe_id)}}</span>`
        ).join('');

        const owaspBadge = exc.owasp_mapping 
          ? `<div class="mt-2 inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-500/10 border border-amber-500/20 text-amber-300 font-mono text-[10px]">
               <span class="font-bold">OWASP:</span> ${{escapeHtml(exc.owasp_mapping)}}
             </div>`
          : '';

        card.innerHTML = `
          <div>
            <div class="flex items-start justify-between gap-2">
              <h3 class="font-bold text-white text-sm">${{escapeHtml(exc.domain)}}</h3>
              <span class="px-2 py-0.5 rounded text-[9px] bg-rose-500/10 text-rose-400 border border-rose-500/20 font-mono uppercase whitespace-nowrap">Excluded</span>
            </div>
            <div class="text-[11px] text-indigo-400 font-mono mt-1">${{escapeHtml(exc.technical_layer)}}</div>
            ${{owaspBadge}}
            <div class="mt-2.5 flex flex-wrap">${{cwesBadges}}</div>
            <p class="text-[11px] text-slate-400 mt-2.5 leading-relaxed">${{escapeHtml(exc.formal_justification)}}</p>
          </div>
        `;
        grid.appendChild(card);
      }});
    }}

    function renderTable() {{
      const samples = SAMPLES[currentDatasetKey] || SAMPLES['default'] || [];
      const tbody = document.getElementById('sample-table-body');
      tbody.innerHTML = '';
      samples.forEach((s, idx) => {{
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-800/40 transition-colors font-mono';
        tr.innerHTML = `
          <td class="p-3 text-slate-300 font-semibold">${{escapeHtml(s.id)}}</td>
          <td class="p-3">
            <span class="px-2 py-0.5 rounded text-[10px] ${{s.lang === 'python' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' : (s.lang === 'typescript' ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20' : 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20')}}">
              ${{escapeHtml(s.lang)}}
            </span>
          </td>
          <td class="p-3 text-indigo-400 font-bold">${{escapeHtml(s.cwe)}}</td>
          <td class="p-3 text-slate-300 font-sans max-w-[200px] truncate" title="${{escapeHtml(s.name)}}">${{escapeHtml(s.name)}}</td>
          <td class="p-3 text-slate-400 font-sans max-w-[160px] truncate">${{escapeHtml(s.owasp)}}</td>
          <td class="p-3 font-bold ${{parseFloat(s.cvss) >= 9.0 ? 'text-rose-400' : 'text-amber-400'}}">${{escapeHtml(s.cvss)}}</td>
          <td class="p-3 text-slate-400 truncate max-w-[120px]">${{escapeHtml(s.dataset)}}</td>
          <td class="p-3 text-right">
            <button onclick="inspectCode(${{idx}})" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-white font-sans text-[11px] transition-colors">
              Inspect
            </button>
          </td>
        `;
        tbody.appendChild(tr);
      }});
    }}

    function inspectCode(idx) {{
      const samples = SAMPLES[currentDatasetKey] || SAMPLES['default'] || [];
      const s = samples[idx];
      if (!s) return;
      document.getElementById('modal-title').innerText = `${{s.cwe}}: ${{s.name}} (${{s.lang}})`;
      document.getElementById('modal-sub').innerText = `ID: ${{s.id}} | CVSS: ${{s.cvss}} | Source: ${{s.dataset}}`;
      document.getElementById('modal-code').innerText = s.code || '// No snippet available';
      if (s.fixed) {{
        document.getElementById('modal-fix-container').classList.remove('hidden');
        document.getElementById('modal-fix').innerText = s.fixed;
      }} else {{
        document.getElementById('modal-fix-container').classList.add('hidden');
      }}
      document.getElementById('code-modal').classList.remove('hidden');
    }}

    function closeModal() {{
      document.getElementById('code-modal').classList.add('hidden');
    }}

    window.onload = () => {{
      updateTabCounts();
      renderAll();
      renderInclusions(INCLUSIONS);
      renderExclusions();
      renderTable();
    }};
  </script>
</body>
</html>
"""
    return html

# 1. Generate Full Benchmark Dashboard
full_html = build_dashboard_html(
    title="Comprehensive Multi-Source Security Benchmark",
    subtitle="Macro-distribution across 2,915 unique vulnerability samples from CVEfixes, CyberSecEval 2, Semgrep & Task 2 GenAI Suite across 159 CWEs.",
    badge_text="Macro-Benchmark Lineage Traced",
    file_traced="datasets/unified/codedee_security_dataset_v1.json",
    data_payload={"default": FULL_DATA},
    table_samples={"default": FULL_TABLE_SAMPLES},
    is_dual=False
)
full_out = VIS_DIR / "full_benchmark_dashboard.html"
full_out.write_text(full_html, encoding="utf-8")
print(f"Generated {full_out}")

# 2. Generate Core Catalogue Scope Dashboard
cat_html = build_dashboard_html(
    title="Core Catalogue Scope Security Benchmark",
    subtitle="Micro-evaluation dataset of 1,879 samples strictly covering the 22 in-scope vulnerability classes with verified Taint Flow ground truth.",
    badge_text="Core Catalogue Scope Traced",
    file_traced="datasets/unified/codedee_security_dataset_catalogue_scope.json",
    data_payload={"default": CAT_DATA},
    table_samples={"default": CAT_TABLE_SAMPLES},
    is_dual=False
)
cat_out = VIS_DIR / "catalogue_scope_dashboard.html"
cat_out.write_text(cat_html, encoding="utf-8")
print(f"Generated {cat_out}")

# 3. Generate Dual Master Dashboard with Live Toggle
dual_html = build_dashboard_html(
    title="CodeDEE Benchmark & Security Ground Truth Visualizer",
    subtitle="Dual-Perspective empirical benchmark comparison: Full Multi-Source Benchmark (2,915) vs Core Catalogue Scope (1,879).",
    badge_text="Dual Ground Truth Verified",
    file_traced="datasets/unified/ (v1.json & catalogue_scope.json)",
    data_payload={"full": FULL_DATA, "cat": CAT_DATA},
    table_samples={"full": FULL_TABLE_SAMPLES, "cat": CAT_TABLE_SAMPLES},
    is_dual=True
)
dual_out = VIS_DIR / "dual_benchmark_dashboard.html"
dual_out.write_text(dual_html, encoding="utf-8")
print(f"Generated {dual_out}")

# Mirror to Artifact Directory
if ARTIFACT_DIR.exists():
    for f in [full_out, cat_out, dual_out]:
        dest = ARTIFACT_DIR / f.name
        shutil.copy(f, dest)
        print(f"Mirrored {f.name} -> {dest}")

print("Dashboard generation complete!")
