"""Step 3: derive default thresholds from data/webapp/repo_metrics/* (repos listed in selected_repos.csv).

Usage: python -I scripts/derive.py   -> results/webapp/
Alves et al. (2010): weight = entity SLOC; weights normalised per system (every system counts equally);
  threshold at quantile p = smallest metric value whose cumulative weight reaches p.
  70/80/90 for all seven metrics. Alves Table IV uses 80/90/95 for parameters because their variability stays small
  until the 80% quantile; that does not hold for Python here, so parameters use 70/80/90 too (decided 2026-11-02).
Vale et al. (2019): every entity (file) weighs the same, pooled over the benchmark; 3/15/90/95 for comment density.
  Sensitivity variant "vale_per_system": same, but each system's files are normalised to equal system weight.
System = one repository restricted to one language group. Systems below MIN_SYSTEM_SLOC are left out
(Alves' smallest system had just over 3K LOC). Optional data/webapp/outlier_exclusions.csv (key,group,reason)
removes systems after expert review (Alves section V); candidates are listed in results/system_outliers.csv.
Exact fractions are used, so results do not depend on floating point summation order.
"""
import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# --dataset=NAME reads data/NAME/ and writes results/NAME/; default = the web-app benchmark
DATASET = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--dataset=")), "webapp")
DATA = ROOT / "data" / DATASET / "repo_metrics"
SELECTED = ROOT / "data" / DATASET / "selected_repos.csv"
RESULTS = ROOT / "results" / DATASET
MIN_SYSTEM_SLOC = 3000
SENSITIVITY_MINS = (0, 1000, 3000, 10000)  # how much the thresholds move with the minimum system size
GROUPS = {"python": ["python"], "javascript": ["javascript", "js_ts"], "typescript": ["typescript", "js_ts"]}
GROUP_ORDER = ["python", "javascript", "typescript", "js_ts"]
ALVES = {"cyclomatic": (70, 80, 90), "cognitive": (70, 80, 90), "params": (70, 80, 90),
         "function_sloc": (70, 80, 90), "file_sloc": (70, 80, 90), "ce": (70, 80, 90), "ca": (70, 80, 90)}
VALE = {"comment_density": (3, 15, 90, 95)}
# Threshold set the extension ships per file language (decided 2026-11-01): .js files use the pooled JS+TS set,
# because JS is mostly a side language in the benchmark and the JS-only set is unstable.
EXTENSION_SETS = {"python": "python", "javascript": "js_ts", "typescript": "typescript"}
# Single default per metric (decided 2026-11-01): the middle Alves quantile = start of the "high risk" band
# (t80). Flag when value > default.
DEFAULT_INDEX = 1


def load():
    """hist[(group, key)][metric] = Counter(value -> summed weight); weight = SLOC (Alves) or 1 (Vale)."""
    hist = defaultdict(lambda: defaultdict(Counter))
    sloc = Counter()
    with SELECTED.open(encoding="utf-8", newline="") as f:  # only the selected repos
        keys = {r["key"] for r in csv.DictReader(f)}
    for repo in sorted(p for p in DATA.iterdir() if p.name in keys and (p / "summary.json").exists()):
        key = repo.name
        with (repo / "files.csv").open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                s, c = int(r["sloc"]), int(r["cloc"])
                for g in GROUPS[r["language"]]:
                    sloc[(g, key)] += s
                    if s:
                        h = hist[(g, key)]
                        h["file_sloc"][s] += s
                        h["ce"][int(r["ce"])] += s
                        h["ca"][int(r["ca"])] += s
                        h["comment_density"][Fraction(100 * c, s + c)] += 1
        with (repo / "functions.csv").open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                s = int(r["sloc"])
                for g in GROUPS[r["language"]]:
                    h = hist[(g, key)]
                    h["function_sloc"][s] += s
                    for m in ("cyclomatic", "params"):
                        h[m][int(r[m])] += s
                    if r["cognitive"] != "":  # blank: Python nested def, counted in its enclosing function
                        # weight = rows the score covers (own + folded nested defs); old CSVs: sloc
                        h["cognitive"][int(r["cognitive"])] += int(r.get("cognitive_sloc") or s)
    return hist, sloc


def distribution(systems, hist, metric, per_system=True):
    """Sorted [(value, weight)] with total weight 1."""
    agg = Counter()
    used = [s for s in systems if hist[s][metric]]
    if per_system:
        for s in used:
            total = sum(hist[s][metric].values())
            for v, w in hist[s][metric].items():
                agg[v] += Fraction(w, total * len(used))
    else:
        for s in used:
            agg.update(hist[s][metric])
        total = sum(agg.values())
        agg = Counter({v: Fraction(w, total) for v, w in agg.items()})
    return sorted(agg.items())


def threshold(dist, p):
    target, cum = Fraction(p, 100), 0
    for value, weight in dist:
        cum += weight
        if cum >= target:
            return value
    return dist[-1][0]


def fmt(v):
    return str(v) if isinstance(v, int) else f"{float(v):.2f}"


def profile(h, cuts):
    """% of a system's weight per band: <= t1, (t1, t2], (t2, t3], > t3 (Alves quality profile)."""
    total = sum(h.values())
    bands = [0, 0, 0, 0]
    for v, w in h.items():
        bands[sum(v > t for t in cuts)] += w
    return [100 * b / total for b in bands]


def write_csv(name, header, rows):
    with (RESULTS / name).open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main():
    hist, sloc = load()
    excluded = set()
    if (ROOT / "data" / DATASET / "outlier_exclusions.csv").exists():
        with (ROOT / "data" / DATASET / "outlier_exclusions.csv").open(encoding="utf-8", newline="") as f:
            excluded = {(r["group"], r["key"]) for r in csv.DictReader(f)}
    RESULTS.mkdir(parents=True, exist_ok=True)
    thr_rows, prof_rows, out_rows, md = [], [], [], []
    md += ["# Derived default thresholds", "",
           "Generated by `scripts/derive.py`; see README.md for the method. Do not edit by hand.", "",
           f"System = repository x language group, kept if SLOC >= {MIN_SYSTEM_SLOC}.", ""]
    for g in GROUP_ORDER:
        all_systems = sorted(s for s in sloc if s[0] == g)
        systems = [s for s in all_systems if sloc[s] >= MIN_SYSTEM_SLOC and s not in excluded]
        if not systems:
            continue
        n_files = sum(sum(hist[s]["comment_density"].values()) for s in systems)
        n_funcs = sum(w // v for s in systems for v, w in hist[s]["function_sloc"].items())  # w = v * count
        md += [f"## {g}", "",
               f"{len(systems)} systems (of {len(all_systems)} with code; {len(excluded & set(all_systems))} excluded "
               f"as outliers), {sum(sloc[s] for s in systems):,} SLOC, {n_files:,} files, {n_funcs:,} functions.", "",
               "| Metric | Method | Quantiles | Thresholds | Quality profile check (median % of SLOC per band) |",
               "|---|---|---|---|---|"]
        for metric, qs in ALVES.items():
            dist = distribution(systems, hist, metric)
            cuts = [threshold(dist, q) for q in qs]
            profiles = {s: profile(hist[s][metric], cuts) for s in systems if hist[s][metric]}
            medians = [statistics.median(p[i] for p in profiles.values()) for i in range(4)]
            for q, t in zip(qs, cuts):
                thr_rows.append([g, metric, "alves", q, fmt(t), len(profiles)])
            for s, p in profiles.items():
                prof_rows.append([g, metric, s[1]] + [f"{x:.2f}" for x in p])
            md.append(f"| {metric} | Alves | {'/'.join(map(str, qs))} | {' / '.join(map(fmt, cuts))} | "
                      f"{' / '.join(f'{m:.1f}' for m in medians)} |")
            # outlier candidates: system median above upper fence of all system medians (Alves section V)
            medians_by_system = {s: threshold(distribution([s], hist, metric), 50) for s in profiles}
            q1, _, q3 = statistics.quantiles([float(v) for v in medians_by_system.values()], n=4, method="inclusive")
            fence = q3 + 1.5 * (q3 - q1)
            out_rows += [[g, metric, s[1], fmt(v), f"{fence:.2f}"] for s, v in medians_by_system.items() if v > fence]
        for metric, qs in VALE.items():
            for method, per_system in (("vale", False), ("vale_per_system", True)):
                dist = distribution(systems, hist, metric, per_system)
                cuts = [threshold(dist, q) for q in qs]
                for q, t in zip(qs, cuts):
                    thr_rows.append([g, metric, method, q, fmt(t), len(systems)])
                md.append(f"| {metric} (%) | {'Vale' if not per_system else 'Vale, per-system normalised'} | "
                          f"{'/'.join(map(str, qs))} | {' / '.join(map(fmt, cuts))} | |")
        md.append("")
    md += ["Quality profile check: share of each system's SLOC in low / moderate / high / very high bands. "
           "If the thresholds represent the benchmark, medians sit near 70/10/10/10.", ""]

    # sensitivity to the minimum system size
    sens_rows = []
    md += ["## Sensitivity to the minimum system size", "",
           "Thresholds when systems below N SLOC are left out (outlier exclusions applied).", ""]
    for g in GROUP_ORDER:
        sets = {n: [s for s in sloc if s[0] == g and sloc[s] >= max(n, 1) and s not in excluded]
                for n in SENSITIVITY_MINS}
        if not sets[0]:
            continue
        md += [f"**{g}**", "", "| Metric | " + " | ".join(f">= {n:,} SLOC ({len(sets[n])} systems)"
                                                       for n in SENSITIVITY_MINS) + " |",
               "|---|" + "---|" * len(SENSITIVITY_MINS)]
        for metric, qs in list(ALVES.items()) + list(VALE.items()):
            cells = []
            for n in SENSITIVITY_MINS:
                if not sets[n]:
                    cells.append("-")
                    continue
                cuts = [threshold(distribution(sets[n], hist, metric, metric in ALVES), q) for q in qs]
                sens_rows += [[g, metric, n, len(sets[n]), q, fmt(t)] for q, t in zip(qs, cuts)]
                cells.append(" / ".join(map(fmt, cuts)))
            md.append(f"| {metric} | " + " | ".join(cells) + " |")
        md.append("")
    write_csv("min_size_sensitivity.csv", ["group", "metric", "min_system_sloc", "systems", "quantile", "threshold"],
              sens_rows)

    # which repository x language systems feed the thresholds
    with SELECTED.open(encoding="utf-8", newline="") as f:
        label = {r["key"]: r["main_language"] for r in csv.DictReader(f)}
    write_csv("benchmark_systems.csv", ["group", "key", "main_language", "sloc", "used", "reason"],
              [[g, k, label.get(k, ""), sloc[(g, k)], (g, k) not in excluded and sloc[(g, k)] >= MIN_SYSTEM_SLOC,
                "outlier_exclusion" if (g, k) in excluded else
                (f"below {MIN_SYSTEM_SLOC} SLOC" if sloc[(g, k)] < MIN_SYSTEM_SLOC else "")]
               for g, k in sorted(sloc, key=lambda s: (GROUP_ORDER.index(s[0]), s[1].lower()))])
    write_csv("thresholds.csv", ["group", "metric", "method", "quantile", "threshold", "systems"], thr_rows)

    # default thresholds for the extension: Alves for 7 metrics, Vale (pooled) for comment density
    defaults = {}
    for language, group in EXTENSION_SETS.items():
        entry = {"derived_from_group": group}
        for metric, qs in list(ALVES.items()) + list(VALE.items()):
            method = "alves" if metric in ALVES else "vale"
            values = [r[4] for r in thr_rows if r[0] == group and r[1] == metric and r[2] == method]
            entry[metric] = {"method": method, "quantiles": list(qs),
                             "thresholds": [float(v) if "." in v else int(v) for v in values]}
            if method == "alves":
                entry[metric]["default"] = entry[metric]["thresholds"][DEFAULT_INDEX]
                entry[metric]["default_quantile"] = qs[DEFAULT_INDEX]
            else:  # decided 2026-11-01: comment density is shown as information only, never flagged
                entry[metric]["default"] = None
        defaults[language] = entry
    (RESULTS / "default_thresholds.json").write_text(json.dumps(defaults, indent=2) + "\n", encoding="utf-8")
    md += ["## Single default per metric (shipped)", "",
           "Flag when value > default. Default = start of Alves' high-risk band (t80).", "",
           "| Metric | " + " | ".join(f".{ {'python': 'py', 'javascript': 'js', 'typescript': 'ts'}[k]} "
                                    f"({v['derived_from_group']})" for k, v in defaults.items()) + " |",
           "|---|" + "---|" * len(defaults)]
    md += [f"| {m} | " + " | ".join(str(defaults[k][m]["default"]) for k in defaults) + " |" for m in ALVES]
    md += [f"| {m} | " + " | ".join("information only" for _ in defaults) + " |" for m in VALE]
    md.append("")
    write_csv("quality_profiles.csv", ["group", "metric", "key", "low", "moderate", "high", "very_high"], prof_rows)
    write_csv("system_outliers.csv", ["group", "metric", "key", "system_median", "upper_fence"], out_rows)
    (RESULTS / "thresholds.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
