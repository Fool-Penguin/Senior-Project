# 05 — Deriving default metric thresholds

Default thresholds for the static-analysis VS Code extension (Python, JavaScript, TypeScript). They are derived
from a benchmark of **100 open-source web applications** with two benchmark-based methods:

- **Alves et al. (2010)**, *Deriving Metric Thresholds from Benchmark Data*: cyclomatic, cognitive, parameter
  count, function SLOC, file SLOC, Ce, Ca.
- **Vale et al. (2019)**, *On the proposal and evaluation of a benchmark-based threshold derivation method*:
  comment density (information only).

How the 100 repositories were chosen is described in
[`reports/selection_method.md`](reports/selection_method.md).

## Run

```bash
pip install -r requirements.txt          # exact versions: results depend on the parser grammar
npm ci                                   # exact TypeScript version (module resolver)
python -I scripts/check_metrics.py       # self-check against SonarQube values and hand-computed cases
python -I scripts/sample_webapps.py      # step 1: sample 100 web apps, pin commits, measure them (needs GITHUB_TOKEN in ../.env)
python -I scripts/measure.py --jobs=4    # step 2 (optional): re-measure selected repos that have no summary.json
python -I scripts/derive.py              # step 3: thresholds -> results/webapp/
```

`sample_webapps.py` calls `measure.py` for every candidate that reaches the size rule, so step 2 is needed only
after deleting measurements. Both `measure.py` and `derive.py` take `--dataset=NAME` (default `webapp`).

## Files

| Path | Content |
|---|---|
| `scripts/sample_webapps.py` | Systematic sampler (search snapshot, seeded stratified order, screening rules) |
| `scripts/measure.py` | Fetch the pinned commit, exclude files, measure, resolve imports |
| `scripts/metrics.py` | Metric definitions (tree-sitter) |
| `scripts/resolve_imports.mjs` | JS/TS import resolution with the TypeScript module resolver |
| `scripts/derive.py` | Alves / Vale derivation, quality profiles, sensitivity, shipped defaults |
| `scripts/check_metrics.py` | Self-check of the metric and sampling rules |
| `data/webapp/search_snapshot.csv` | Sampling frame: 9,485 repositories from GitHub search (fixed) |
| `data/webapp/screening_cache.json` | Cached facts per candidate (contributors, pinned commit, dependencies, README score, SLOC) |
| `data/webapp/manual_exclusions.csv` | Manual review exclusions (`key,reason`) |
| `data/webapp/screening_results.csv` | Every examined candidate with its decision and reason (2,630) |
| `data/webapp/selected_repos.csv` | The 100 selected repositories with pinned commit SHA |
| `data/webapp/manual_review_sheet.csv` | Review sheet: kept and excluded repositories with GitHub facts and notes |
| `data/webapp/repo_metrics/<key>/` | Measurements of a selected repository: `files.csv`, `functions.csv`, `summary.json` |
| `data/webapp/repo_metrics_rejected/` | Measurements of candidates that were measured and then rejected |
| `results/webapp/default_thresholds.json` | What the extension ships |
| `results/webapp/thresholds.md` | Summary of all thresholds, quality profiles and sensitivity |
| `results/webapp/*.csv` | `thresholds`, `quality_profiles`, `benchmark_systems`, `system_outliers`, `min_size_sensitivity` |
| `reports/selection_method.md` | Repository selection method |

## Reproducibility

Running the pipeline again gives byte-identical output.

- The sampling frame (`search_snapshot.csv`) is saved once and reused. Every fetched fact is cached, and the
  decisions are recomputed from the cache, the rules and `manual_exclusions.csv`. A rerun selects the same 100
  repositories.
- `selected_repos.csv` pins one commit SHA per repository. `measure.py` fetches exactly that commit
  (`git fetch --depth 1 <sha>`), never the latest main. The fetch is partial (`--filter=blob:limit=1m`): files of
  1 MB or more are not downloaded, and they would be excluded anyway.
- Files are read from git objects, not from a checkout, so line-ending settings, Windows path limits and
  untracked files cannot change the content.
- Exact versions: tree-sitter 0.26.0, tree-sitter-language-pack 1.12.5, typescript 6.0.3. They are recorded in each
  `summary.json`.
- All outputs are sorted. Thresholds are computed with exact fractions, so the order of floating-point
  summation cannot move a quantile.

The per-entity CSVs in `data/webapp/repo_metrics/` are the dataset. Archive them, because a repository that is
later deleted or force-pushed cannot be fetched again.

## File exclusions (`scripts/measure.py`)

Alves removed test and generated code before deriving thresholds. Examples and docs were also removed by decision.

| Reason | Rule |
|---|---|
| test | directories `test(s)`, `__tests__`, `testing`, `spec(s)`, `__mocks__`, `__snapshots__`, `e2e`, `fixtures`, `__fixtures__`, `qa`; files `test_*.py`, `*_test.py`, `test(s).py`, `conftest.py`, `*.test.*`, `*.spec.*`, `*.e2e.*`, `*.cy.*` |
| generated_vendored | directories `node_modules`, `bower_components`, `vendor(s)`, `third_party`, `third-party`, `3rdparty`, `3rd-party`, `external(s)`, `libs`, `dist`, `build`, `.next`, `coverage`, `venv`, `site-packages`, `migrations`, `generated`, `__generated__`, …; files `*.min.js`, `*.bundle.js`, `*.d.ts`, `*_pb2.py`, `*.generated.*`, `*.gen.*`; a header with `@generated` / `auto-generated` / `do not edit`; minified (a line > 1000 chars and > 200 bytes per line on average); file > 1 MB |
| vendored_library | JS/TS only: third-party code copied into the repository. Detected from a release banner with a version (`/*! jQuery v3.7.1`), a UMD wrapper (`define.amd`), a `@license` / `@licstart` tag, or Emscripten glue code. A plain `/*! Copyright <company>` banner is not enough, because some projects put it on their own files |
| data_file | JS/TS file with at least 1,000 SLOC and no function (dictionaries, word lists, fixtures) |
| example_docs | directories `example(s)`, `doc(s)`, `demo(s)`, `sample(s)`, `cookbook(s)`, `tutorial(s)`, `playground`; `*.stories.*` |
| hidden_dir | any directory starting with `.` (`.github`, `.vscode`, …): CI and tooling scripts |
| parse_error | tree-sitter reports a syntax error (e.g. Python 2 files). The file is skipped, not guessed |

Counts per reason and repository are in each `summary.json`.

## Metric definitions (`scripts/metrics.py`)

All three languages are parsed with tree-sitter. The extension can run the same grammars (web-tree-sitter/WASM),
so it can measure exactly what the thresholds were derived from. Alves VII-D: the same tool should derive the
thresholds and apply them.

**Unit (function).** Python `def`/`async def` (a `lambda` belongs to its enclosing `def`, as in SonarQube);
JS/TS function declarations and expressions, arrow functions, generators, methods. For cyclomatic, SLOC and
parameter count, each line and decision belongs to its innermost unit, so it is counted exactly once.
- **Python nested `def`, as SonarQube does it.** Cyclomatic: per function, nested defs measured separately
  (sonar-python cyclomatic rule). Cognitive: nested defs folded into the enclosing function (sonar-python
  cognitive rule); nested defs have no cognitive value (blank in `functions.csv`, skipped by `derive.py`).

| Metric | Level | Definition |
|---|---|---|
| Cyclomatic | function | 1 + decision points, as SonarQube counts them. **Python** (sonar-python `ComplexityVisitor`): `if` (not `elif`), `for`, `while`, conditional expression, each `and`/`or`, comprehension `if`. Not counted: `elif`, `except`, `case` (and its `if` guard), `else`, comprehension `for`. **JS/TS** (SonarJS S1541): `if` (each `else if` too), `for`, `for…in/of`, `while`, `do`, `case` (not `default`), ternary, each `&&`/`\|\|`/`??`. Not counted: `catch`, `&&=`/`\|\|=`/`??=`, `?.`, default parameters |
| Cognitive | function | SonarSource white paper (G. A. Campbell) as SonarQube implements it. +1 for `if`, `else if`/`elif`, `else` (Python: also loop and `try` `else`), ternary, `switch`, loops, `catch`/`except`, labelled `break`/`continue`; + nesting level for nested `if`/ternary/`switch`/loops/`catch`. Only bodies nest (loop body, ternary branches, switch cases, `catch`/`except` body); a loop header, ternary test, switch value and `except` value stay at the current level. Python (sonar-python): a conditional expression nests its condition too, a `lambda` adds no nesting, `match` adds 0 but case bodies nest. Logical operators: Python +1 per run of identical `and`/`or`, and a parenthesised group starts its own run; JS/TS (SonarJS) only `&&` runs count, so `\|\|` and `??` add nothing anywhere, and a single-operator chain directly in JSX (`{a && b}`) adds nothing. Recursion adds nothing. Python nested `def`: part of the outer function, one nesting level deeper; a "wrapper" def (the outer function's other statements are only `return <name>`) keeps the outer level, and a def directly in a class body starts at 0. JS/TS: a ternary whose branch is a function adds +1 nesting to the structures after it (SonarJS). Evidence: `05_metric_comparison/results/sonar_nesting_probe.txt` |
| Parameter count | function | Declared parameters; `*args`/`**kwargs`/`...rest`, defaults and destructuring count 1 each; Python `self`/`cls` (first parameter) and TS `this:` are not counted |
| Function SLOC | function | Rows with a code token of the unit (comments, blank lines, docstrings and nested units excluded) |
| File SLOC | file | Rows with at least one code token. A shebang is not code. Python docstrings are comments |
| Ce | file | Number of distinct measured files of the same repository that the file imports |
| Ca | file | Number of distinct measured files of the same repository that import the file |
| Comment density | file | CLOC / (SLOC + CLOC) × 100. CLOC = rows with comment text containing a letter or digit (Sonar `comment_lines`: `#`, `// ----`, `*/` do not count). Python docstrings and commented-out code count. A leading licence header does not: the leading comments are split into blocks (one `/* */` comment, the Python module docstring, or a run of line comments on consecutive rows), and only blocks that mention copyright/licence are excluded. A row with code and a trailing comment counts in both. Files with SLOC = 0 are skipped |

**Validation against SonarQube.**
- `check_metrics.py` asserts our values on SonarQube probes from `05_metric_comparison/samples`. The JS/TS
  cyclomatic rules come from the SonarJS S1541 source, because that rule is off by default.
- On real code, cyclomatic and cognitive match SonarQube for IDE on 432 of 432 functions sampled from the
  benchmark repositories, and on all 18 functions of `metrics.py` itself.
- The comparison found four rules that are now implemented and tested:
  - the Python nested `def`;
  - the Python parenthesised boolean group;
  - the SonarJS ternary-with-function nesting;
  - the `function` keyword token, which must not count as a unit.
- Evidence: `05_metric_comparison/results/sonar_real_code_check.txt`, `sonar_jsts_rules.txt`,
  `comprehension_probe.txt`.

**Import resolution.**
- **Python.** Relative imports resolve from the file's package. Absolute imports are tried against the
  project roots enclosing the file (deepest first), the other project roots, the file's own directory, then
  every other ancestor directory of the file (deepest first); the first match wins. A project root is the
  repository root, a directory holding `pyproject.toml`, `setup.py`, `setup.cfg`, `manage.py` or
  `requirements*.txt`, its `src/`, and the directory above the package of a `wsgi.py`/`asgi.py` (its own
  directory when it is not in a package). Markers inside excluded directories are ignored. `from m import a`
  links to `m/a.py` if it exists, else to `m`.
- **JS/TS.** The TypeScript module resolver with the nearest `tsconfig.json`/`jsconfig.json` (paths, baseUrl,
  `.js`→`.ts`, index files).
  - A solution config (`files: []` + `references`, as in Vite) covers no file: the referenced config whose
    `include`/`files` covers the importing file is used, else the first one with `paths`.
  - Node16/NodeNext without a resolution mode resolves like CommonJS; when it fails, Bundler is tried once
    (e.g. a package whose `exports` has only an `import` condition).
  - An import that lands on a `.d.ts` (not measured) goes to the source file with the same stem.
  - Workspace packages (a `package.json` name inside the repository, not under an excluded directory; on
    duplicate names the shallowest wins) resolve to their folder, falling back to `src/index` when `exports`
    points at build output.
  - **Bundler aliases (heuristic).** Used only when TypeScript resolution fails. Read with regexes from
    `vite`/`vitest`/`webpack`/`vue`/`next`/`nuxt`/`babel` config files and `.babelrc`, simple string forms only:
    `'@': path.resolve(__dirname, 'src')` (or `path.join`), `'@': fileURLToPath(new URL('./src', import.meta.url))`,
    `'@': '/src'` or `'./src'` inside an `alias: {…}` object, `{ find: '@', replacement: … }`, and
    `alias['@'] = …`. A config directory with none of these maps `@/` and `~/` to `<config dir>/src/`
    (Nuxt: then `app/`, then the directory itself). Aliases apply to files under the config's directory.
- Type-only imports (Python `if TYPE_CHECKING:`, TS `import type` / `export type` / every name `type`) count
  as edges. Imports by tests do not, because tests are not measured.
- `summary.json` import counters: `js_relative_imports_unresolved`, `js_alias_imports_unresolved` (unresolved
  `@/`, `~/`, `src/`, tsconfig `paths` prefixes, bundler alias keys, workspace package names),
  `js_type_only_import_edges`, `py_imports_ambiguous` (more than one base matched; the first wins),
  `py_imports_unresolved` (relative imports, and absolute imports whose top-level name is a repository
  directory or `.py` file), `py_type_only_import_edges` (edges that exist only through type-only imports).

## Derivation (`scripts/derive.py`)

- **System** = one repository restricted to one language group: `python`, `javascript`, `typescript`, and
  `js_ts` (JS and TS pooled). A system is kept if it has at least 3,000 SLOC. Alves gives every system equal
  weight, so some minimum is needed; without one, a 150-line helper script would count as much as a 500K-line
  codebase. 3,000 follows Alves' benchmark, whose systems *"range from over 3K LOC to near 800K LOC"*
  (Sec. V). `results/webapp/min_size_sensitivity.csv` shows the thresholds at 0 / 1K / 3K / 10K.
- **Alves:** entity weight = SLOC, normalised per system so every system weighs the same. The threshold at p is
  the smallest metric value whose cumulative weight reaches p. Quantiles are 70/80/90 for all seven metrics
  (parameter count included; see Decisions).
- **Vale:** every file weighs the same, pooled over the benchmark, at quantiles 3/15/90/95 (very low / low /
  high / very high). Vale has no per-system normalisation, so big repositories dominate. `vale_per_system`
  gives each system equal weight as a sensitivity check.
- **Validation (Alves Sec. VI-D, Fig. 7b):** per-system quality profiles. If the thresholds represent the
  benchmark, the median share of SLOC per band is close to 70/10/10/10.
- **Outliers (Alves Sec. V):** systems whose median metric value exceeds Q3 + 1.5·IQR of all system medians are
  listed in `results/webapp/system_outliers.csv`. They are removed only after expert review, by adding them to
  `data/webapp/outlier_exclusions.csv` (`key,group,reason`).

### Benchmark

| Group | Systems | SLOC | Functions |
|---|---|---|---|
| python | 45 | 2,399,985 | 115,014 |
| javascript | 54 | 1,802,588 | 137,744 |
| typescript | 54 | 7,147,542 | 438,575 |
| js_ts | 84 | 8,974,559 | 577,808 |

### Shipped defaults (`results/webapp/default_thresholds.json`)

Flag when value > default.

| Metric | `.py` (python) | `.js` (js_ts) | `.ts` (typescript) |
|---|---|---|---|
| Cyclomatic | 11 | 10 | 10 |
| Cognitive | 17 | 8 | 8 |
| Parameter count | 3 | 2 | 2 |
| Function SLOC | 63 | 88 | 97 |
| File SLOC | 1029 | 707 | 578 |
| Ce | 9 | 9 | 11 |
| Ca | 4 | 2 | 3 |
| Comment density | information only | information only | information only |

All 70/80/90 values are in `results/webapp/thresholds.md`.

### Decisions on the results

- **Single default per metric = t80.** This is the start of Alves' high-risk band;
  flag when value > default. t90 (very-high risk) was judged too loose, e.g. cyclomatic 18 in all three
  languages and cognitive 32 for Python. The full bands are stored alongside the default.
- **`.js` uses the pooled js_ts set.** The JS-only systems are small and uneven: the median system is 10.5K SLOC,
  and 21 of 54 are the JS part of a Python or TS repository. Its file SLOC and Ce thresholds shift with the
  minimum system size, and its file-SLOC quality profile has empty top bands. Alves also pooled two languages
  (Java and C#) into one benchmark. Full argument: [`reports/selection_method.md`](reports/selection_method.md) §9.
- **Parameter count uses 70/80/90, not Alves' 80/90/95.** Alves chose 80/90/95 because parameter count
  *"variability is relative small until the 80% quantile"* (Sec. VIII). That holds for JS/TS but not for
  Python, where the share of code with ≤ 2 / ≤ 3 parameters is 71% / 83%. With 80/90/95 the Python quality
  profile was 85 / 10 / 1.6 / 4 (high band far below Alves' ~5%); with 70/80/90 it is 73 / 12 / 10 / 5, close
  to 70/10/10/10. The JS/TS default is 2 under either set; Python goes from 5 to 3.
- **Parameter count JS/TS thresholds = 1 / 2 / 2.** The 80% and 90% quantiles are both 2, so the high band is
  empty: three effective bands, a consequence of a whole-number metric. Ca (t70 = t80) has the same effect in
  the `.js` set.
- **No outlier systems removed.** 78 metric × system flags (55 systems) are listed in
  `results/webapp/system_outliers.csv`. All systems are kept, following Alves Sec. VII-C: the method is
  resilient to outliers.
- **Comment density has no default (information only).** At least 15% of files have no comments, so Vale's
  very-low and low bounds are both 0 in all three languages and cannot separate files. A high density is not a
  defect by itself. The extension shows the value and Vale's band (`default: null`; the 3/15/90/95 thresholds
  stay alongside for the band label).
- **Thresholds are not rounded.** Whole-number metrics give whole-number thresholds. Comment density keeps two
  decimals.

## Known limits

- Imports through computed names (`importlib.import_module(var)`, `require(var)`), `sys.path` changes, and bundler
  aliases written in a form other than the simple ones above are not resolved and count as external. Ce/Ca are
  lower bounds. The Python ancestor-directory fallback can also link a module that Python would only find with
  a matching `sys.path`; `py_imports_ambiguous` shows how often more than one candidate existed.
- Cognitive is weighted by `cognitive_sloc` (the rows its score covers: own rows plus folded Python nested defs), every other function metric by its own SLOC.
- Python comprehensions: for cyclomatic, a comprehension `if` counts as a decision and the comprehension `for`
  does not, so a comprehension can score 1 lower than the same logic written as a loop. This follows SonarQube.
  CodeScene does the opposite, and radon counts both. For cognitive, comprehensions add nothing, as in
  SonarQube (verified by run).
- Generated and vendored code detection is based on paths, headers and minification; generated files without
  any of these markers stay in.
