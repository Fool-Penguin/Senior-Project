"""Self-check of metrics.py. Run before measuring: python -I scripts/check_metrics.py

1. Oracle values observed from SonarQube for IDE / ESLint on the probe files of 05_metric_comparison
   (results/sonar_defaults_run.txt, sonar_ts_java_run.txt, ide_diagnostics_all_summary.txt, eslint_metrics.txt).
2. Hand-computed cases for SLOC / CLOC / params / units / imports.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics import measure  # noqa: E402

SAMPLES = Path(__file__).resolve().parents[2] / "05_metric_comparison" / "samples"
failures = []


def units(path, src=None):
    src = src if src is not None else (SAMPLES / path).read_bytes()
    result = measure(path, src)
    assert result is not None, f"parse error in {path}"
    return result, {u.name: u for u in result.units}


def expect(label, got, want):
    ok = got == want
    if not ok:
        failures.append(label)
    print(f"  {'OK  ' if ok else 'FAIL'} {label}: got {got}, expected {want}")


print("1) Oracles (SonarQube for IDE / ESLint)")
for ext in ("py", "js", "ts"):
    _, fns = units(f"probe_cc.{ext}")
    for n in range(4, 23):
        if f"cc_{n}" in fns:
            u = fns[f"cc_{n}"]
            if (u.cyclomatic, u.cognitive) != (n, n - 1):
                expect(f"probe_cc.{ext} cc_{n} (cyclomatic, cognitive)", (u.cyclomatic, u.cognitive), (n, n - 1))
    print(f"  checked probe_cc.{ext}: cc_N -> cyclomatic N, cognitive N-1")
for ext in ("py", "js"):
    expect(f"probe_nest.{ext} nest_6 cognitive", units(f"probe_nest.{ext}")[1]["nest_6"].cognitive, 21)
expect("probe_brain.py process_orders cognitive", units("probe_brain.py")[1]["process_orders"].cognitive, 55)

# probe_sonar_jsts.{js,ts}: cognitive = SonarQube S3776 run (JS and TS identical); cyclomatic = SonarJS S1541 source
# rules (rule off by default, so not run). See 05_metric_comparison/results/sonar_jsts_rules.txt.
SONAR_JSTS = {  # name: (cyclomatic [SRC], cognitive [RUN])
    "base": (17, 16), "if_else": (18, 18), "else_if": (19, 18), "switch_2case_default": (19, 17),
    "try_catch": (17, 17), "ternary": (18, 17), "and": (18, 17), "or": (18, 16), "nullish": (18, 16),
    "and_or_mixed": (19, 17), "and_and_same": (19, 17), "and_assign": (17, 16), "nullish_assign": (17, 16),
    "optional_chain": (17, 16), "for": (18, 17), "for_of": (18, 17), "for_in": (18, 17), "while": (18, 17),
    "do_while": (18, 17), "nested_arrow_ternary": (17, 16), "nested_function_if": (17, 16), "callback_if": (17, 16),
    "labelled_break": (20, 23), "nested_if_in_for": (19, 19), "default_param": (17, 16), "recursion": (17, 16)}
for ext in ("js", "ts"):
    _, fns = units(f"probe_sonar_jsts.{ext}")
    bad = {n: ((fns[f"sj_{n}"].cyclomatic, fns[f"sj_{n}"].cognitive), want) for n, want in SONAR_JSTS.items()
           if (fns[f"sj_{n}"].cyclomatic, fns[f"sj_{n}"].cognitive) != want}
    expect(f"probe_sonar_jsts.{ext}: {len(SONAR_JSTS)} constructs match SonarQube (mismatches)", bad, {})
# probe_sonar_nest.{js,py}: SonarQube for IDE S3776 [RUN 2026-11-05], base = 16 sequential ifs + one construct.
# See 05_metric_comparison/results/sonar_nesting_probe.txt.
SONAR_NEST = {
    "js": {"if_or": 17, "if_and_or": 18, "for_header_ternary": 18, "while_cond_ternary": 18, "do_cond_ternary": 18,
           "forof_iter_ternary": 18, "switch_value_ternary": 18, "ternary_test_ternary": 18,
           "ternary_branch_ternary": 19, "for_body_ternary": 19, "catch_body_if": 19},
    "py": {"for_iter_ternary": 18, "while_cond_ternary": 18, "ternary_cond_ternary": 19, "lambda_ternary": 17,
           "match": 16, "try_else": 18, "except_expr_ternary": 18, "wrapper": 19, "not_wrapper": 37,
           "class_in_def": 20}}
for ext, want in SONAR_NEST.items():
    _, fns = units(f"probe_sonar_nest.{ext}")
    expect(f"probe_sonar_nest.{ext}: {len(want)} nesting constructs match SonarQube (mismatches)",
           {n: (fns[f"sn_{n}"].cognitive, w) for n, w in want.items() if fns[f"sn_{n}"].cognitive != w}, {})
_, fns = units("probe_sonar_retry.py")  # decorator factory, SonarQube [RUN] 2026-11-05: retry 16, decorator none
expect("probe_sonar_retry.py (retry, decorator) cognitive", (fns["retry"].cognitive, fns["decorator"].cognitive), (16, None))
_, fns = units("g.py", b"def g(a):\n    match a:\n        case 1 if a > 0:\n            return [x for x in a if x]\n")
expect("py `case` guard is not a cyclomatic decision, comprehension if is (Sonar [SRC])", fns["g"].cyclomatic, 2)
_, fns = units("probe_sonar_py_extra.py")  # SonarQube S3776 run: recursion not counted, and/or counted
expect("probe_sonar_py_extra.py cognitive", {n: u.cognitive for n, u in fns.items()},
       {"py_base": 16, "py_recursion": 16, "py_or": 17, "py_and": 17, "py_and_or": 18})

print("2) Hand-computed cases")
py = b'''#!/usr/bin/env python
# Copyright 2024 ACME. Licensed under MIT.
"""Module docstring."""
import os
from . import sibling
from ..pkg.mod import name as alias
#
# real comment
x = 1  # trailing


def f(self, a, b=1, *args, c, **kw):
    """Doc
    more doc
    """
    if a and b or c:          # cognitive +1 if, +2 sequence | cyclomatic: if, and, or
        return [i for i in a if i]   # cyclomatic: comprehension if (not for)
    elif a:                   # cognitive +1 | cyclomatic: elif not counted (Sonar)
        pass
    try:
        pass
    except ValueError:        # cognitive +1 | cyclomatic: except not counted (Sonar)
        pass
    g = lambda y: y if y else 0   # lambda belongs to f: cyclomatic +1, cognitive +1 (no nesting, Sonar [RUN])
    return f(self, a)         # recursion: nothing (SonarQube)


class C:
    def m(cls, a):
        match a:
            case 1:
                return 1
            case _:
                return 0
'''
r, fns = units("t.py", py)
expect("py SLOC", r.sloc, 22)            # rows 4-6, 9, 12, 16-25, 28-34 (shebang excluded)
expect("py CLOC", r.cloc, 11)            # 3 (module doc), 8, 9, 13, 14 (docstring), 16, 17, 18, 22, 24, 25
expect("units (lambda is not a unit)", sorted(fns), ["f", "m"])
expect("f params (self excluded)", fns["f"].params, 5)
expect("f cyclomatic (Sonar: if, and, or, comprehension if, lambda ternary)", fns["f"].cyclomatic, 6)
expect("f cognitive", fns["f"].cognitive, 6)  # if 1, sequence 2, elif 1, except 1, lambda ternary 1
expect("f SLOC (docstring excluded)", fns["f"].sloc, 11)
expect("m cyclomatic (match/case not counted, Sonar)", fns["m"].cyclomatic, 1)
expect("m cognitive (match adds 0, Sonar [RUN])", fns["m"].cognitive, 0)
expect("m params (cls excluded)", fns["m"].params, 1)
expect("py imports", r.imports, [(0, "os", []), (1, "", ["sibling"]), (2, "pkg.mod", ["name"])])

ts = b'''/**
 * SPDX-License-Identifier: Apache-2.0
 */
import type { A } from "./a";
export * from "../b";
// ----
// note: explain
function outer(this: Window, a: number, b = 1, ...rest: number[]) {
  if (a && b) {               // +1, && run +1
    for (const x of rest) {   // +2 (nesting 1)
      if (x ?? b) break;      // +3 (nesting 2), ?? adds nothing (SonarJS)
    }
  } else if (b || a) {        // +1, || adds nothing (SonarJS)
  } else {                    // +1
  }
  const cb = (y) => y ? 1 : 2;
  return a > 0 ? 1 : outer(a - 1, b);  // ternary +1, recursion nothing
}
const z = require("c");
'''
r, fns = units("t.ts", ts)
expect("ts SLOC", r.sloc, 14)
expect("ts CLOC (license block excluded, '// ----' not significant)", r.cloc, 7)
u = fns["outer"]
expect("outer params (this excluded)", u.params, 3)
expect("outer cognitive", u.cognitive, 10)
expect("outer cyclomatic", u.cyclomatic, 9)  # if, &&, for, if, ??, else-if, ||, ternary
expect("cb unit", (fns["cb"].params, fns["cb"].cyclomatic, fns["cb"].cognitive), (1, 2, 1))
expect("ts imports", r.imports, ["./a", "../b", "c"])

_, fns = units("k.js", b"function a(x){ if (x) { return 1; } return 0; }\nconst b = function(y){ return y; };\n")
expect("`function` keyword is not a unit", sorted(fns), ["a", "b"])

# SonarQube for IDE values [RUN 2026-11-02] for three rules found on real web-app code
# (05_metric_comparison/results/sonar_real_code_check.txt)
_, fns = units("n.py", b"def outer(a, b):\n    if a:\n        pass\n    def inner(x):\n        if x:\n"
                       b"            for i in x:\n                pass\n    return inner\n")
expect("py nested def folds into outer, +1 nesting (cognitive [RUN])", fns["outer"].cognitive, 1 + 2 + 3)
expect("py nested def is its own unit for cyclomatic/SLOC/params, no cognitive (outer, inner)",
       [(n, u.cyclomatic, u.sloc, u.params, u.cognitive) for n, u in sorted(fns.items())],
       [("inner", 3, 4, 1, None), ("outer", 2, 4, 2, 6)])
expect("cognitive_sloc = outer + inner rows, each row once (outer, inner)",
       (fns["outer"].cognitive_sloc, fns["inner"].cognitive_sloc), (8, None))
_, fns = units("probe_sonar_nest.py")
expect("cognitive_sloc: method of a class inside a def goes to the def; plain def = sloc",
       [(n, fns[n].sloc, fns[n].cognitive_sloc) for n in ("sn_class_in_def", "m", "sn_match")],
       [("sn_class_in_def", 5, 42), ("m", 37, None), ("sn_match", 38, 38)])
_, fns = units("c.ts", b"function o(a) {\n  const f = (x) => {\n    return x;\n  };\n  return f(a);\n}\n")
expect("cognitive_sloc JS/TS = sloc (nested functions are not folded; rows 2 and 4 belong to both o and f)",
       [(n, u.sloc, u.cognitive_sloc) for n, u in sorted(fns.items())], [("f", 3, 3), ("o", 5, 5)])
_, fns = units("b.py", b"def g1(a, b, c, d):\n    if a and (b or c) and d:\n        return 1\n"
                       b"def g2(a, b, c, d):\n    if a and b or c and d:\n        return 1\n")
expect("py parenthesized boolean group is its own chain (g1, g2)", (fns["g1"].cognitive, fns["g2"].cognitive), (3, 4))
_, fns = units("q.js", b"""function p2(x, y, g) { const f = x ? () => g() : null; const b = y ? 1 : 2; return [f, b]; }
function q3(a, b, c, g) { const f1 = a ? () => g() : null; const f2 = b ? () => g() : null; return c ? 1 : 2; }
function q4(a, b, c, g) { const f = a ? () => g() : null; if (b) { return c ? f : null; } return null; }
function q5(a, b, c, g) { if (a) { const f = b ? () => g() : null; g(f); } return c ? 1 : 2; }
function q6(a, g) { const r = (() => a)() ? 1 : 2; const s = g ? 3 : 4; return [r, s]; }
function r1(a, b, g) { const f = a ? g(() => 1) : null; const r = b ? 1 : 2; return [f, r]; }
function r4(a, b, g) { const f = a ? null : () => g(); const r = b ? 1 : 2; return [f, r]; }
""")
expect("SonarJS: ternary with a function branch adds nesting afterwards",
       {n: fns[n].cognitive for n in ("p2", "q3", "q4", "q5", "q6", "r1", "r4")},
       {"p2": 3, "q3": 6, "q4": 6, "q5": 5, "q6": 2, "r1": 2, "r4": 3})

tsx = b'''export function Card(a: boolean, b: boolean, c: boolean) {
  return <div>{a && b && c}{a && b || c}<i x={(a && b)} /></div>;
}
'''
_, fns = units("t.tsx", tsx)  # SonarJS: single-operator chain in JSX adds 0; mixed chain counts normally (&& run +1)
expect("tsx JSX short-circuit (cyclomatic, cognitive)", (fns["Card"].cyclomatic, fns["Card"].cognitive), (6, 1))

print("3) Python import resolution and exclusions (measure.py)")
from measure import path_reason, python_targets  # noqa: E402

py_paths = {"pkg/__init__.py", "pkg/a.py", "pkg/sub/__init__.py", "pkg/sub/b.py", "src/lib/__init__.py",
            "src/lib/c.py", "scripts/run.py", "scripts/helper.py"}
roots = ["", "src"]
expect("relative `from . import a` + `from .sub.b import x`",
       sorted(python_targets("pkg/sub/__init__.py", [(2, "", ["a"]), (1, "b", ["x"])], py_paths, roots)),
       ["pkg/a.py", "pkg/sub/b.py"])
expect("absolute via src/ root + package fallback",
       sorted(python_targets("pkg/a.py", [(0, "lib.c", []), (0, "pkg.sub", ["missing_name"])], py_paths, roots)),
       ["pkg/sub/__init__.py", "src/lib/c.py"])
expect("script dir import", python_targets("scripts/run.py", [(0, "helper", []), (0, "os", [])], py_paths, roots),
       {"scripts/helper.py"})
expect("exclusions", [path_reason(p) for p in ("src/tests/x.py", "a/test_x.py", "web/x.spec.tsx", "docs/conf.py",
                                               "x/types.d.ts", ".github/s.js", "src/app.ts")],
       ["test", "test", "test", "example_docs", "generated_vendored", "hidden_dir", None])

from measure import content_reason  # noqa: E402

expect("vendored JS/TS detection", [content_reason(d, p) for d, p in (
    (b"/*! jQuery v3.7.1 | (c) OpenJS Foundation */\nfunction a(){}", "static/jquery.js"),
    (b"/**\n * @licstart The following is the entire license notice\n */", "web/pdf.mjs"),
    (b"var Module = typeof Module != 'undefined' ? Module : {};", "src/GifWasmModule.js"),
    (b"// app entry\nexport function main() {}", "src/app.ts"),
    (b"# @license is fine in Python\n", "app/x.py"),
    (b"/*!\n * Copyright (c) 2024 PLANKA Software GmbH\n * Licensed under the Fair Use License\n */\nimport R", "a.jsx"),
    (b'!function(e,t){"object"==typeof exports?module.exports=t():"function"==typeof define&&define.amd?define(t)', "l.js"),
    (b"import { Directory, Module } from './types';\nif (typeof module !== 'undefined') {}", "sandbox.ts"))],
    ["vendored_library", "vendored_library", "vendored_library", None, None, None, "vendored_library", None])
expect("vendored dirs", [path_reason(p) for p in ("cps/static/js/libs/pdf.mjs", "__generated/rr/rr.js", "src/lib/a.ts")],
       ["generated_vendored", "generated_vendored", None])

print("4) Web-app sampling: runtime web dependencies only (sample_webapps.py)")
from sample_webapps import english_share, keyword_reason, py_deps, MIN_ENGLISH_SHARE  # noqa: E402

expect("README language rule (English, Portuguese, Chinese)", [english_share(t) >= MIN_ENGLISH_SHARE for t in (
    "PwnDoc is a pentest reporting application making it simple and easy to write your findings.",
    "A BrasilAPI tem como objetivo centralizar e disponibilizar endpoints modernos com baixo tempo de resposta.",
    "学之思开源考试系统是一款 java + vue 的前后端分离的考试系统。")], [True, False, False])

expect("py_deps", [py_deps(*a) for a in (
    ("pyproject.toml", '[project]\ndependencies=["click"]\n[project.optional-dependencies]\nhttp=["fastapi"]'),
    ("pyproject.toml", '[tool.poetry.dependencies]\nDjango="^5"\n[tool.poetry.group.dev.dependencies]\nflask="*"'),
    ("requirements-dev.txt", "flask\n"), ("requirements.txt", "Flask==3.0\n"),
    ("setup.py", 'install_requires=["requests"],\nextras_require={"web": ["flask"]}'),
    ("setup.cfg", "[options]\ninstall_requires =\n    django\n[options.extras_require]\nx = flask\n"),
    ("Pipfile", '[packages]\nfastapi="*"\n[dev-packages]\nflask="*"'))],
    [set(), {"django"}, set(), {"flask"}, set(), {"django"}, {"fastapi"}])
expect("keyword_reason", [keyword_reason({"topics": t, "description": d, "full_name": f"o/{n}"}) for t, d, n in (
    ("", "A sample app for RAG", "x"), ("orm;python", "", "x"), ("", "", "django-allauth"), ("self-hosted", "Wiki", "y"))],
    ["non-app description: sample", "non-app topic: orm", "framework / framework plugin name", None])

print("5) Snippets: bare JS/TS class method (metrics.measure_snippet)")
from metrics import measure_snippet  # noqa: E402

for p, src in (("m.js", b"// note\nf(a, b) {\n  if (a && b) return 1;\n  return 0;\n}\n"),
               ("m.ts", b"// note\nf(a: number, b: number): number {\n  if (a && b) return 1;\n  return 0;\n}")):
    r = measure_snippet(p, src)
    expect(f"{p} bare method (sloc, cloc, unit)", r and (r.sloc, r.cloc, [(u.name, u.start_line, u.end_line, u.sloc,
           u.cyclomatic, u.cognitive, u.params) for u in r.units]), (4, 1, [("f", 2, 5, 4, 3, 2, 2)]))
expect("broken snippet", measure_snippet("m.js", b"f(a) { if ( }"), None)

print("6) License header blocks and type-only import flags (metrics.py)")
expect("CLOC: license comment excluded, following @file comment counts",
       measure("h.ts", b"/* Copyright 2024 X */\n/** @file Does things */\nexport const a = 1;\n").cloc, 1)
expect("CLOC: run of # lines with a licence line is one header block",
       measure("h.py", b"# Copyright 2024 X\n# you may not use this file\n\n# real comment\nx = 1\n").cloc, 1)
expect("CLOC: Python module docstring holding a license is a header",
       measure("d.py", b'"""Copyright 2024 ACME. Licensed under MIT."""\n# real\nx = 1\n').cloc, 1)
expect("TS type-only flags", measure("i.ts", b"""import type { A } from './a';
import { type B } from './b';
import D, { type C } from './c';
export type { E } from './e';
import x from './x';
""").type_only, [True, True, False, True, False])
expect("Python TYPE_CHECKING flags (else branch runs normally)", measure("i.py", b"""if TYPE_CHECKING:
    import a
else:
    import b
if typing.TYPE_CHECKING:
    from c import d
""").type_only, [True, False, True])

print("7) Import graph on fake repo trees (measure.import_graph)")
from measure import import_graph  # noqa: E402


def graph_of(sources, configs, extra=()):
    measured = {p: measure(p, s.encode()) for p, s in sources.items()}
    graph, stats = import_graph(sorted([*sources, *configs, *extra]), measured, configs)
    return {p: sorted(t) for p, t in graph.items() if t}, stats


py_graph, py_stats = graph_of({
    "backend/myapp/__init__.py": "", "backend/myapp/models.py": "x = 1", "backend/myapp/types.py": "T = 1",
    "backend/utils.py": "x = 1", "utils.py": "x = 1", "site/mysite/__init__.py": "",
    "site/mysite/settings.py": "x = 1", "site/mysite/wsgi.py": "x = 1",
    "backend/myapp/views.py": "from typing import TYPE_CHECKING\nimport myapp.models\nimport utils\n"
                              "from .missing import x\nimport myapp.nothere\nimport os\n"
                              "if TYPE_CHECKING:\n    from myapp import types\n",
    "other/y.py": "import mysite.settings\n",
}, {}, extra=["backend/manage.py", "docs/requirements.txt"])
expect("py edges (manage.py root, wsgi.py root, root-marker order)", py_graph, {
    "backend/myapp/views.py": ["backend/myapp/models.py", "backend/myapp/types.py", "backend/utils.py"],
    "other/y.py": ["site/mysite/settings.py"]})
expect("py stats (ambiguous `utils`, unresolved relative + `myapp.nothere`, TYPE_CHECKING edge)",
       {k: v for k, v in py_stats.items() if k.startswith("py_")},
       {"py_imports_ambiguous": 1, "py_imports_unresolved": 2, "py_type_only_import_edges": 1})
expect("py ancestor-dir fallback (no root marker)", graph_of(
    {"app/core/__init__.py": "", "app/core/db.py": "x = 1", "app/core/api/v.py": "import core.db\n"}, {})[0],
    {"app/core/api/v.py": ["app/core/db.py"]})

js_graph, js_stats = graph_of({
    "web/src/main.ts": "import { u } from '#app/util';\nimport B from '@/comp/Button';\nimport L from './legacy';\n"
                       "import ui from 'ui';\nimport type { T } from './types';\nexport type { V } from './v';\n"
                       "import n from '@/nothere';\nimport r from 'react';\n",
    "web/src/util.ts": "export const u = 1;", "web/src/comp/Button.tsx": "export default 1;",
    "web/src/legacy.js": "export default 1;", "web/src/types.ts": "export type T = 1;",
    "web/src/v.ts": "export type V = 1;", "packages/ui/src/index.ts": "export default 1;",
    "examples/ui/index.ts": "export default 1;", "admin/src/a.js": "import b from '~/b';\n",
    "admin/src/b.js": "export default 1;", "packages/esm/lib/main.ts": "export default 1;",
    "svc/src/s.ts": "import e from 'esm-only';\n",
    "nx/app/utils/api.ts": "import t from '@/types';\n", "nx/app/types/index.ts": "export type T = 1;",
}, {
    "nx/nuxt.config.ts": "export default defineNuxtConfig({})\n", "nx/vitest.config.ts": "export default {}\n",
    "web/tsconfig.json": '{"files": [], "references": [{"path": "./tsconfig.app.json"}, {"path": "./tsconfig.node.json"}]}',
    "web/tsconfig.app.json": '{"compilerOptions": {"paths": {"#app/*": ["./src/*"]}}, "include": ["src"]}',
    "web/tsconfig.node.json": '{"include": ["vite.config.ts"]}',
    "web/vite.config.ts": "import { fileURLToPath, URL } from 'node:url'\nexport default defineConfig({\n"
                          "  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },\n})\n",
    "admin/webpack.config.js": "module.exports = { entry: './src/a.js' };\n",
    "examples/ui/package.json": '{"name": "ui"}', "apps/x/ui/package.json": '{"name": "ui"}',
    "packages/ui/package.json": '{"name": "ui"}',
    "packages/esm/package.json": '{"name": "esm-only", "exports": {".": {"import": "./lib/main.ts"}}}',
    "svc/tsconfig.json": '{"compilerOptions": {"module": "NodeNext", "moduleResolution": "NodeNext"}}',
}, extra=["web/src/legacy.d.ts"])
expect("js edges (references, vite alias, .d.ts sibling, shallowest workspace, @/ ~/ fallback, Bundler retry)",
       js_graph, {"admin/src/a.js": ["admin/src/b.js"], "svc/src/s.ts": ["packages/esm/lib/main.ts"],
                  "nx/app/utils/api.ts": ["nx/app/types/index.ts"],
                  "web/src/main.ts": ["packages/ui/src/index.ts", "web/src/comp/Button.tsx", "web/src/legacy.js",
                                      "web/src/types.ts", "web/src/util.ts", "web/src/v.ts"]})
expect("js stats (type-only edges, alias unresolved)",
       {k: v for k, v in js_stats.items() if k.startswith("js_")},
       {"js_alias_imports_unresolved": 1, "js_relative_imports_unresolved": 0, "js_type_only_import_edges": 2})

print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} FAILED'}")
sys.exit(1 if failures else 0)
