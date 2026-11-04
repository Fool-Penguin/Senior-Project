# Selection method: web-application benchmark

This document describes how the 100 repositories used to derive the default metric thresholds were selected.
The thresholds themselves and the measurement rules are described in [`../README.md`](../README.md).

Everything below is produced by [`scripts/sample_webapps.py`](../scripts/sample_webapps.py). The numbers come
from the files in [`data/webapp/`](../data/webapp/).

## 1. Target population

**A deployable web application** is software whose main product is run and used over HTTP. It may be
self-hosted, deployed to a server or serverless platform, or served to a browser. It is used either by people
through a browser UI or by client programs through a web/HTTP API. It is not software that is mainly imported
as a library, extended as a framework, copied as a template or example, or published as static content.

The 100 selected repositories cover these kinds of application:

| Kind | Examples |
|---|---|
| Self-hosted web app (server + browser UI) | paperless-ngx, plane, planka, actual, wger |
| Hosted platform with a web UI | overleaf, documenso, cvat, onyx |
| HTTP/API service without a UI of its own | saleor, gns3-server, veditor, dynamic-image-transformation-for-amazon-cloudfront |
| Web administration UI of a server | AdGuardHome, pritunl, LedFx, viseron |
| Browser client of another service | phanpy, wire-webapp, Expensify/App, standardnotes |
| Browser-only web app | drawdb, jsoncrack.com, pic-smaller, carbon |
| Serverless web app | sublink-worker, Sink, counterscale |
| Dynamic website (accounts, database) | djangoproject.com, kentcdodds.com |

AI applications are allowed if they meet the definition (for example onyx and screenshot-to-code).

**Summary criterion.** We drew a seeded, stratified random sample of 100 GitHub repositories (34 Python,
33 TypeScript, 33 JavaScript). Each one is a deployable web application with these properties:

- it has a web framework among its runtime dependencies, ships a deployment file, is not published as a
  package, and its main product is used through a web UI or a web/HTTP API;
- it has an English README;
- it has at least 1,000 stars and at least 10 contributors;
- it had a commit on main/master since 2026-05-01 and was created before 2024-11-01;
- it is not archived, a fork, or a template;
- it contains at least 3,000 SLOC in its main language.

## 2. Sampling frame

The GitHub search API was queried once per language (`language:Python`, `language:TypeScript`,
`language:JavaScript`). The reference date is 2026-11-01. The query was:

```
language:<L> stars:<range> pushed:>=2026-05-01 created:<=2024-11-01 archived:false fork:false template:false
```

Search returns at most 1,000 results per query, so the star range (starting at `>=1000`) is split in halves
until each slice has 1,000 results or fewer. The union of all slices is saved once as
`data/webapp/search_snapshot.csv`. Later runs reuse this file and do not query GitHub search again, so the
frame is fixed.

| main_language | Repositories in the frame |
|---|---|
| Python | 4,161 |
| TypeScript | 3,156 |
| JavaScript | 2,168 |
| **Total** | **9,485** |

`main_language` is GitHub's primary language for the repository, meaning the language with the most bytes.

## 3. Sampling design

- **Stratified by `main_language`**, with quotas Python 34, TypeScript 33, JavaScript 33. Each language is one
  stratum, so the sample is balanced even though the frame is not.
- **Random order with a fixed seed.** Within each stratum, the candidates are sorted by GitHub repository id
  (a stable key) and then shuffled with `random.Random(f"20261101-{main_language}")`. The seed `20261101` is
  the reference date. It was fixed before any repository was drawn, and it has no other meaning. Any fixed
  value gives an equally valid random sample. Fixing it makes the draw repeatable.
- **Sequential screening.** The sampler walks each stratum in that order. It checks each candidate against
  the rules in section 4 and takes the first ones that pass, until the quota is filled. A rejected candidate
  is replaced by the next one in the random order, never by hand-picking.

## 4. Screening rules

The rules are applied in this order, cheapest check first. A candidate is rejected at the first rule it fails.

| # | Rule | Criterion | Why |
|---|---|---|---|
| 1 | Previous sample | Not one of the 170 repositories of the earlier agentic benchmark (matched by GitHub id, which survives renames) | Independent dataset |
| 2 | Archived / fork / template | None of these | Already excluded by the search query; kept as a safety check |
| 3 | Keywords | No non-application topic (e.g. `library`, `framework`, `sdk`, `template`, `boilerplate`, `cli`, `plugin`, `awesome-list`, `tutorial`, `example`, `demo`). No such word in the description (e.g. *library*, *framework*, *starter*, *template*, *toolkit*, *wrapper*, *samples*, *reference implementation*). Repository name is not a framework name and not a framework plugin (`django-*`, `flask-*`, `pytest-*`, …) | Removes libraries, frameworks, templates and learning material cheaply |
| 4 | Contributors | At least 10, anonymous contributors included (GitHub contributors API) | Team-developed software |
| 5 | Branch | Default branch if it is `main` or `master`, else `main`, else `master`. The commit at its head is pinned | Main branch only; fixed commit |
| 6 | Activity | Last commit on that branch on or after 2026-05-01 | Maintained in the last 6 months (the search's `pushed` date also counts other branches) |
| 7 | Web framework | A web framework among the **runtime** dependencies (Python: `pyproject.toml` `[project] dependencies` / Poetry, `Pipfile` `[packages]`, `requirements*.txt` except dev/test/doc/lint/ci/example/bench/optional/extra files, `setup.py`/`setup.cfg` `install_requires`; JS/TS: `dependencies` or `devDependencies` of any `package.json`, because bundled front ends often list their UI framework as a dev dependency). Manifests in test, example, docs or vendored folders are ignored | Software built on a web stack |
| 8 | Deployment file | Dockerfile, compose file, `Procfile`, `fly.toml`, `render.yaml`, `vercel.json`, `netlify.toml`, `wrangler.toml`, `app.yaml`, `railway.json`, `firebase.json`, Helm `Chart.yaml`, or Django `manage.py` | Software meant to be deployed and run |
| 9 | Not a published package | The root `package.json` (or a monorepo package named after the repository) is not `private` and declares an entry point (`main`/`module`/`exports`/`types`) | Removes libraries that ship a demo site |
| 10 | English README | Share of common English function words among the README's Latin-letter words ≥ 0.05 (section 6) | The extension and the thesis target English-language projects |
| 11 | Manual review | Main product is used through a web UI or a web/HTTP API (section 5) | Rules 3–9 cannot judge what the main product is |
| 12 | Size | At least 3,000 SLOC in the repository's `main_language`, after the file exclusions of `measure.py` (tests, generated, vendored, examples/docs) | Alves et al. (2010): their smallest benchmark system had just over 3K LOC. Each system has equal weight, so a tiny system must not count as much as a large one |

Recognised web frameworks:

| Language | Frameworks |
|---|---|
| Python | django, flask, fastapi, starlette, tornado, aiohttp, sanic, quart, litestar, bottle, pyramid, falcon, streamlit, gradio, dash, reflex, nicegui, python-fasthtml |
| JS/TS UI | react, react-dom, vue, svelte, @angular/core, solid-js, preact, next, nuxt, @sveltejs/kit, @remix-run/react, ember-source, @builder.io/qwik, astro |
| JS/TS server | express, koa, fastify, @nestjs/core, hono, @hapi/hapi, @adonisjs/core, h3, elysia |

## 5. Manual review

**Rule.** Keep a repository if its main product is used through a web UI or a web/HTTP API. Exclude it if the
web part is secondary, for example a demo, a log viewer, or one of several interfaces of a CLI tool. Also
exclude it if the repository is mainly a library, framework, SDK, plugin, desktop app, educational
collection, or content website.

**Evidence checked.** README opening and screenshots, top-level folders (frontend/backend), release
artefacts, homepage or demo site, and Docker/deployment instructions.

**Record.** Every exclusion is written to `data/webapp/manual_exclusions.csv` (key, reason). The sampler
reads that file and replaces each excluded repository with the next candidate in the random order. The
review was repeated until a pass produced no new exclusions. `data/webapp/manual_review_sheet.csv` lists
every kept and excluded repository with its GitHub facts, the reason, and the reviewer notes.

The file holds 54 exclusions. 47 of them decide the outcome. For the other 7, an earlier automatic rule
rejects the repository first: 6 by the English rule (one of them, mindskip/xzs, is also a near-duplicate of
another repository) and 1 by the published-package rule (sugar-high).

| Reason | n | Examples |
|---|---|---|
| Library, framework, SDK or engine (including agent frameworks whose web UI is a demo or log viewer) | 20 | flet, titiler, data-juicer, mui-x, bull-board, composio, duktape, XAgent, RD-Agent |
| Web part is secondary to a CLI tool, daemon, bot or other server | 9 | mitmproxy, dnsrecon, qbit_manage, errbot, routr, DeepCamera |
| Educational or collection repository | 7 | 30-Days-Of-Python, react-play, frontend-mini-challenges, epicweb-dev workshops, remix-run/examples, angular-challenges |
| Desktop, firmware or OS | 4 | Signal-Desktop, Beaver-Notes, X1Plus, MentraOS |
| Content or documentation website | 3 | nodejs.org, strapi/documentation, awesome-uses |
| Other (plugin, userscripts, measured code is not the product) | 2 | frigate-hass-integration, GM_script |
| Main language code is not the product | 2 | triton-inference-server (Python is 79% QA tests; the server is C++), convex-backend (TypeScript is mostly client SDK) |

## 6. English-README rule

**Measure.** The README is taken at the pinned commit, with code blocks, HTML tags, link targets and URLs
removed. The score is the share of its Latin-letter words that are one of 33 common English function words:

> the, and, to, of, is, for, with, you, your, this, that, it, on, are, be, can, as, or, by, from, an, will,
> not, use, using, have, has, which, all, more, our, we, if, at

"a" and "in" are left out because they are also common in Portuguese, German and other languages. A
Chinese or Japanese README has almost no Latin words, so its score is near 0.

**Calibration.** The threshold was set using the READMEs that the reviewer had labelled "not English" during
manual review. These scored at most 0.0073, and the English ones scored at least 0.0755. The threshold 0.05
lies in that gap. In the final screening run, 186 candidates reached this rule:

| Group | n | Score |
|---|---|---|
| Rejected as not English | 16 | max 0.0388 |
| Passed the rule | 170 | min 0.0677 |
| Selected | 100 | min 0.0755 |

All 16 rejected READMEs were checked by hand: they are written in Chinese, Japanese, Portuguese or Spanish.

The rule runs after the web-application rules, so it only judges repositories that would otherwise qualify.

## 7. Screening results

Candidates examined until all three quotas were filled: 2,630 (Python 797, TypeScript 478, JavaScript 1,355).

| # | Rejected by | Python | TypeScript | JavaScript | Total |
|---|---|---|---|---|---|
| 1 | Previous (agentic) sample | 4 | 1 | 1 | 6 |
| 2 | Archived / fork / template | 0 | 0 | 0 | 0 |
| 3 | Keyword: topic | 78 | 78 | 188 | 344 |
| 3 | Keyword: description | 150 | 91 | 209 | 450 |
| 3 | Keyword: framework name | 18 | 0 | 5 | 23 |
| 4 | Contributors < 10 | 97 | 41 | 176 | 314 |
| 5 | No `main`/`master` branch | 17 | 4 | 17 | 38 |
| 6 | Last commit before 2026-05-01 | 32 | 23 | 88 | 143 |
| 7 | No web framework dependency | 296 | 64 | 436 | 796 |
| 8 | No deployment file | 33 | 96 | 112 | 241 |
| 9 | Published npm package | 3 | 28 | 58 | 89 |
| 10 | README not in English | 6 | 2 | 8 | 16 |
| 11 | Manual exclusion | 22 | 16 | 9 | 47 |
| 12 | Main-language SLOC < 3,000 | 7 | 1 | 15 | 23 |
| | **Selected** | **34** | **33** | **33** | **100** |

Per-candidate decisions and reasons are in `data/webapp/screening_results.csv`.

## 8. The selected sample

| Property | Min | Median | Max |
|---|---|---|---|
| Stars | 1,040 | 2,786 | 80,962 |
| Contributors | 10 | 61.5 | 2,415 |
| SLOC in main language | 3,199 | 40,314 | 1,096,443 |
| Created | 2010-05-28 | | 2024-10-16 |
| Last commit on pinned branch | 2026-05-18 | | 2026-11-01 |

Branch: `main` 69, `master` 31. Most common licences: MIT 24, other/unrecognised (`NOASSERTION`) 22,
GPL-3.0 17, AGPL-3.0 16, Apache-2.0 14. The full list with pinned commit SHAs is in
`data/webapp/selected_repos.csv`.

## 9. From repositories to benchmark systems

Every Python, JavaScript and TypeScript file of a selected repository is measured, whatever the repository's
`main_language`. A **system** is one repository restricted to one language group: `python`, `javascript`,
`typescript`, or `js_ts` (JavaScript and TypeScript together). A system enters the benchmark if it has at
least 3,000 SLOC (`results/webapp/benchmark_systems.csv`).

| Group | Systems | SLOC | Functions |
|---|---|---|---|
| python | 45 | 2,399,985 | 115,014 |
| javascript | 54 | 1,802,588 | 137,744 |
| typescript | 54 | 7,147,542 | 438,575 |
| js_ts | 84 | 8,974,559 | 577,808 |

### Why `.js` uses the pooled JS+TS set

The extension uses the `python` set for `.py`, the `typescript` set for `.ts`, and the pooled `js_ts` set
for `.js`.

**Pooling has precedent in the method's source.** Alves et al. (2010) derived one set of thresholds from a
single benchmark of two languages: *"100 systems in modern object-oriented technologies (Java and C#)"*. That
was 82 Java systems (11.2M LOC) and 18 C# systems (0.8M LOC) (Sec. V, Table II). The paper does not derive
or compare per-language thresholds.

**The JavaScript-only set is unreliable in this benchmark.**

1. *Uneven systems.* Alves gives every system equal weight: *"every system is represented equally in the
   benchmark, limiting the influence of bigger systems over small systems"* (Sec. VI-C). The JavaScript
   systems are small and uneven. The median system has 10,548 SLOC against 34,088 for Python, and 26 of 54
   are under 10K SLOC. 21 of the 54 are the JavaScript part of a Python or TypeScript repository (median
   4,639 SLOC).
2. *Unstable thresholds.* The file-SLOC t80 for JavaScript is 652 / 1,038 / 1,084 / 685 at minimum system
   sizes of 0 / 1K / 3K / 10K SLOC. The Ce t80 is 2 / 3 / 4 / 6. The pooled values are 681 / 722 / 707 / 664
   and 8 / 8 / 9 / 10 (`results/webapp/min_size_sensitivity.csv`).
3. *Unrepresentative quality profile.* Alves checks that the thresholds are representative with per-system
   quality profiles: *"for low risk we expect to identify around 70% of the code, and for each of the other
   risk categories 10%"* (Sec. VI-D, Fig. 7b). For JavaScript-only file SLOC, the median profile is
   77.6 / 7.7 / 0.0 / 0.0. 29 of 54 systems have no code in the high band and 39 of 54 none in the very-high
   band. The paper warns that a threshold with too much variability *"might fail to identify code in many
   systems"* (Sec. VI-D). The pooled set gives 72.4 / 8.3 / 8.9 / 3.5.
4. *Same measurement.* JavaScript and TypeScript are parsed by the same tree-sitter grammar family and
   measured with identical rules (SonarJS rules for cyclomatic and cognitive). TypeScript is a superset of
   JavaScript, and many repositories mix both.

**Caveat.** TypeScript is about 80% of the pooled SLOC, so the `.js` defaults lean towards TypeScript code.
For reference, the JavaScript-only defaults (t80) would be: cyclomatic 9, cognitive 9,
parameters 2, function SLOC 66, file SLOC 1,084, Ce 4, Ca 1.

## 10. Reproducibility

- The search frame is saved once (`search_snapshot.csv`). Every fetched fact (contributors, pinned commit,
  commit date, dependencies, deployment files, README score, SLOC) is cached in `screening_cache.json`.
  Decisions are recomputed on every run from the cached facts, the rules and `manual_exclusions.csv`.
- Each selected repository is measured at its pinned commit SHA, never at the "latest" main.
- Running `sample_webapps.py` again gives byte-identical `selected_repos.csv` and `screening_results.csv`.
  This was verified after each change to the scripts.
- Re-querying GitHub (`--refresh-search`) gives a different frame, because stars, activity and repositories
  change over time. That would be a new sample, not a rerun.

## 11. Limitations

- **Snapshot in time.** The frame reflects GitHub on 2026-11-01/02. Stars, contributors and activity change,
  and repositories can be renamed, deleted or force-pushed. The pinned SHAs and the measured CSVs in
  `data/webapp/repo_metrics/` are the durable record.
- **Popularity bias.** The 1,000-star and 10-contributor minimums favour successful, team-built projects. The
  thresholds describe that population, not all web code.
- **GitHub's primary language is coarse.** It names only the language with the most bytes. Systems are
  therefore built per language group from all files, not from the stratum label.
- **Keyword rules favour precision over recall.** A web application whose topics or description contain a
  word such as *framework* or *template* is rejected at rule 3, even if it would have qualified. This removes
  some eligible repositories, but it does not admit ineligible ones.
- **Fixed framework list.** A web application built on a framework that is not in the list (section 4) is
  rejected at rule 7.
- **English heuristic.** The README score is a word-frequency heuristic, not a language detector. It was
  calibrated on this sample, and all its rejections were checked by hand.
- **Manual review needs judgement.** Borderline cases, such as a server whose UI is one of several
  interfaces, depend on the review rule in section 5. Every decision is recorded with its reason, so it can
  be audited and changed. A change means rerunning the sampler and the derivation.
