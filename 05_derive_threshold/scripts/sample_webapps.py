"""Step 0 (web-app benchmark): systematic sampling of 100 web-application repositories.

Usage: python -I scripts/sample_webapps.py [--refresh-search]
Needs GITHUB_TOKEN (read from ../.env first, then the environment).

1. Snapshot: GitHub search per primary language (Python / JavaScript / TypeScript) with
   stars >= 1000, pushed since PUSHED_SINCE, created before CREATED_BEFORE, not archived / fork / template.
   Saved once to data/webapp/search_snapshot.csv; later runs reuse it (--refresh-search re-queries).
2. Order: each main_language group (one stratum of the stratified sample) is sorted by repo id, then shuffled with a fixed seed.
3. Walk each group in that order and take the first candidates that pass every check (cheapest first):
     previous   in the agentic sample (02_repo_sampling/data/Repos_Final_Sample.csv), matched by GitHub repo id
     keywords   non-application topic / description / name (library, framework, template, ...)
     contributors >= MIN_CONTRIBUTORS (GitHub contributors API, anonymous included)
     branch     default branch if main/master, else main, else master; last commit on it >= PUSHED_SINCE
     web_app    a web framework dependency (UI or server) AND a deployment file, not a published npm package
     english    README in English: share of common English function words >= MIN_ENGLISH_SHARE
     manual     exclusion in data/webapp/manual_exclusions.csv (key, reason)
     size       >= MIN_SLOC SLOC in its main_language after measure.py's exclusions
4. Every fetched check result is cached in data/webapp/screening_cache.json, so reruns give the same 100 repos.
Outputs (data/webapp/):
  selected_repos.csv      the 100 repos with pinned commit (input of measure.py / derive.py)
  screening_results.csv   every examined candidate with its decision and reason
  repo_metrics/           measurements of the selected repos; repo_metrics_rejected/ = measured, then rejected
"""
import base64
import csv
import json
import os
import random
import re
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
import measure  # noqa: E402
import subprocess  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "webapp"
PREVIOUS = ROOT.parent / "02_repo_sampling" / "data" / "Repos_Final_Sample.csv"
measure.OUT = OUT / "repo_metrics"

PUSHED_SINCE, CREATED_BEFORE = "2026-05-01", "2024-11-01"  # reference date 2026-11-01: active 6 months, age 2 years
MIN_STARS, MIN_CONTRIBUTORS, MIN_SLOC = 1000, 10, 3000
QUOTA = {"Python": 34, "TypeScript": 33, "JavaScript": 33}
SEED = 20261101
MEASURE_LANGUAGE = {"Python": "python", "JavaScript": "javascript", "TypeScript": "typescript"}

NON_APP_TOPICS = {
    "library", "framework", "web-framework", "sdk", "boilerplate", "starter", "starter-kit", "starter-template",
    "template", "templates", "ui-kit", "ui-library", "ui-components", "component-library", "components",
    "react-components", "vue-components", "design-system", "awesome", "awesome-list", "list", "tutorial",
    "tutorials", "course", "examples", "cheatsheet", "book", "cli", "command-line-tool", "vscode-extension",
    "chrome-extension", "browser-extension", "firefox-extension", "plugin", "wordpress-plugin", "npm-package",
    "python-library", "javascript-library", "typescript-library", "react-library", "api-client", "api-wrapper",
    "wrapper", "bindings", "orm", "middleware", "test-framework", "linter", "eslint-plugin", "compiler",
    "bundler", "build-tool", "sample", "samples", "demo", "example", "azd-templates"}
NON_APP_TEXT = re.compile(
    r"\b(librar(y|ies)|frameworks?|sdk|boilerplate|starter|templates?|ui kit|component library|components for|"
    r"plugin|extension|awesome|curated list|tutorials?|course|cheat ?sheet|wrapper|bindings|api client|"
    r"client for|toolkit|samples?|demos?|example apps?|reference (app|implementation))\b", re.I)
PY_PLUGIN_NAME = re.compile(r"^(django|flask|fastapi|starlette|pyramid|sqlalchemy|pytest)[-_]", re.I)

PY_WEB = {"django", "flask", "fastapi", "starlette", "tornado", "aiohttp", "sanic", "quart", "litestar", "bottle",
          "pyramid", "falcon", "streamlit", "gradio", "dash", "reflex", "nicegui", "python-fasthtml"}
JS_WEB = {"react", "react-dom", "vue", "svelte", "@angular/core", "solid-js", "preact", "next", "nuxt",
          "@sveltejs/kit", "@remix-run/react", "ember-source", "@builder.io/qwik", "astro",  # UI
          "express", "koa", "fastify", "@nestjs/core", "hono", "@hapi/hapi", "@adonisjs/core", "h3", "elysia"}
FRAMEWORK_NAMES = {n.split("/")[-1] for n in PY_WEB | JS_WEB} | {"next.js", "angular", "core", "kit", "nest"}
PY_MANIFEST = re.compile(r"(^|/)(requirements[^/]*\.txt|pyproject\.toml|setup\.py|setup\.cfg|pipfile)$", re.I)
DEPLOY_FILE = re.compile(r"(^|/)(dockerfile([.-](?![^/]*\.([cm]?[jt]sx?|py)$)[^/]*)?|[^/]*\.dockerfile|(docker-)?compose[^/]*\.ya?ml|procfile|"
                         r"fly\.toml|render\.ya?ml|vercel\.json|netlify\.toml|wrangler\.(toml|jsonc?)|app\.ya?ml|"
                         r"railway\.(json|toml)|firebase\.json|chart\.ya?ml|manage\.py)$", re.I)
TOKEN = None


def repo_key(url):
    owner, name = url.rstrip("/").removesuffix(".git").split("/")[-2:]
    return f"{owner}__{name}"


def pin(url):
    """(branch, sha, status): the default branch if it is main/master, else main, else master."""
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    run = subprocess.run(["git", "ls-remote", "--symref", url, "HEAD", "refs/heads/main", "refs/heads/master"],
                         capture_output=True, text=True, env=env, timeout=120, check=False)
    if run.returncode:
        return "", "", "unreachable"
    default, heads = None, {}
    for line in run.stdout.splitlines():
        left, ref = line.split("\t")
        if left.startswith("ref: "):
            default = left[5:].removeprefix("refs/heads/")
        elif ref.startswith("refs/heads/"):
            heads[ref.removeprefix("refs/heads/")] = left
    branch = default if default in ("main", "master") else next((b for b in ("main", "master") if b in heads), None)
    return (branch, heads[branch], "ok") if branch in heads else ("", "", "no_main_master")


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def token():
    env_file = ROOT.parent / ".env"
    if env_file.exists():
        m = re.search(r"^GITHUB_TOKEN=(.+)$", env_file.read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1).strip().strip("\"'")
    return os.environ.get("GITHUB_TOKEN")


def http(url, api=True):
    """GET with retry; waits for the rate-limit reset instead of failing. Returns (body, headers) or None on 404."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "threshold-sampling"}
    if api:
        headers["Authorization"] = f"Bearer {TOKEN}"
    for attempt in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r:
                return r.read(), r.headers
        except urllib.error.HTTPError as e:
            if e.code in (404, 409, 451):
                return None
            if e.code in (403, 429) and e.headers.get("X-RateLimit-Remaining") == "0":
                time.sleep(max(1, int(e.headers.get("X-RateLimit-Reset", time.time() + 60)) - time.time()) + 2)
            elif e.code in (403, 429):
                time.sleep(int(e.headers.get("Retry-After", 60)))
            elif e.code >= 500:
                time.sleep(5 * (attempt + 1))
            else:
                raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"giving up on {url}")


def api(path):
    got = http(f"https://api.github.com{path}")
    return (json.loads(got[0]), got[1]) if got else (None, None)


# ---------- 1. snapshot ----------
CAND_FIELDS = ["id", "key", "full_name", "url", "main_language", "stars", "forks", "created_at", "pushed_at", "archived",
               "fork", "is_template", "default_branch", "license", "topics", "description"]


def search_language(lang):
    items = {}

    def query(rng, page):
        q = (f"language:{lang} stars:{rng} pushed:>={PUSHED_SINCE} created:<={CREATED_BEFORE} "
             f"archived:false fork:false template:false")
        time.sleep(2.2)  # search API: 30 requests / minute
        return api("/search/repositories?" + urllib.parse.urlencode(
            {"q": q, "sort": "stars", "order": "desc", "per_page": 100, "page": page}))[0]

    def walk(lo, hi):
        rng = f"{lo}..{hi}" if hi else f">={lo}"
        first = query(rng, 1)
        total = first["total_count"]
        if total > 1000 and (hi is None or hi > lo):  # search returns at most 1000 results: split the star range
            mid = 2 * lo - 1 if hi is None else (lo + hi) // 2
            walk(lo, mid)
            walk(mid + 1, hi)
            return
        pages = [first] + [query(rng, p) for p in range(2, min(10, -(-total // 100)) + 1)]
        for page in pages:
            for it in page["items"]:
                items[it["id"]] = it
        print(f"  {lang} stars {rng}: {total}", flush=True)

    walk(MIN_STARS, None)
    return items.values()


def snapshot():
    path = OUT / "search_snapshot.csv"
    if path.exists() and "--refresh-search" not in sys.argv:
        with path.open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    rows = []
    for lang in QUOTA:
        for it in search_language(lang):
            rows.append({"id": it["id"], "key": repo_key(it["html_url"]), "full_name": it["full_name"],
                         "url": it["html_url"], "main_language": lang, "stars": it["stargazers_count"],
                         "forks": it["forks_count"], "created_at": it["created_at"], "pushed_at": it["pushed_at"],
                         "archived": it["archived"], "fork": it["fork"], "is_template": it.get("is_template", False),
                         "default_branch": it["default_branch"],
                         "license": (it.get("license") or {}).get("spdx_id") or "",
                         "topics": ";".join(sorted(it.get("topics") or [])),
                         "description": " ".join((it.get("description") or "").split())})
    rows.sort(key=lambda r: int(r["id"]))
    write_csv(path, CAND_FIELDS, rows)
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))  # read back so a fresh run and a rerun see identical strings


def previous_ids(facts):
    """GitHub ids of the agentic sample (ids survive renames and transfers)."""
    prev = facts.setdefault("_previous_ids", {})
    with PREVIOUS.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            k = repo_key(r["Repo_URL"])
            if k not in prev:
                owner, name = k.split("__")
                data, _ = api(f"/repos/{owner}/{name}")
                prev[k] = data["id"] if data else None
    return {str(v) for v in prev.values() if v}


# ---------- 3. checks ----------
def keyword_reason(c):
    topics = set(filter(None, c["topics"].split(";")))
    name = c["full_name"].split("/")[1]
    hit = sorted(topics & NON_APP_TOPICS)
    if hit:
        return f"non-app topic: {hit[0]}"
    m = NON_APP_TEXT.search(c["description"])
    if m:
        return f"non-app description: {m.group(0).lower()}"
    if name.lower() in FRAMEWORK_NAMES or PY_PLUGIN_NAME.match(name):
        return "framework / framework plugin name"
    return None


def contributors(full):
    for anon in ("true", "false"):  # anon=true fails on repos with very large histories
        got = http(f"https://api.github.com/repos/{full}/contributors?per_page=1&anon={anon}")
        if got is None:
            continue
        m = re.search(r'[?&]page=(\d+)>; rel="last"', got[1].get("Link", ""))
        return int(m.group(1)) if m else len(json.loads(got[0] or b"[]"))
    return 0


def py_names(text):
    text = text.lower()
    return {n for n in PY_WEB if re.search(rf"(^|[\s\"'\[,(]){re.escape(n)}($|[\s\"'\],;<>=!~\[)])", text, re.M)}


NON_RUNTIME_REQS = re.compile(r"dev|test|doc|lint|ci|example|bench|optional|extra", re.I)


def py_deps(path, text):
    """Web frameworks among the RUNTIME dependencies only (optional / dev / test groups are ignored)."""
    name = PurePosixPath(path).name.lower()
    try:
        if name == "pyproject.toml":
            d = tomllib.loads(text)
            runtime = list(d.get("project", {}).get("dependencies", []))
            runtime += list(d.get("tool", {}).get("poetry", {}).get("dependencies", {}))
            return py_names("\n".join(runtime))
        if name == "pipfile":
            return py_names("\n".join(tomllib.loads(text).get("packages", {})))
    except tomllib.TOMLDecodeError:
        return set()
    if name.startswith("requirements"):
        return set() if NON_RUNTIME_REQS.search(name.removeprefix("requirements")) else py_names(text)
    m = re.search(r"install_requires\s*(=\s*\[([^\]]*)\]|=([^\[]*?)(\n\S|\Z))", text, re.S)  # setup.py / setup.cfg
    return py_names((m.group(2) or m.group(3) or "")) if m else set()


def web_facts(full, sha):
    tree, _ = api(f"/repos/{full}/git/trees/{sha}?recursive=1")
    paths = sorted(e["path"] for e in (tree or {}).get("tree", []) if e["type"] == "blob")
    kept = [p for p in paths if measure.path_reason(p) is None]
    deploy = sorted(p for p in kept if DEPLOY_FILE.search(p))
    web, published = set(), False
    for p in kept:
        name = PurePosixPath(p).name.lower()
        if name != "package.json" and not PY_MANIFEST.search(p):
            continue
        got = http(f"https://raw.githubusercontent.com/{full}/{sha}/{urllib.parse.quote(p)}", api=False)
        text = got[0].decode("utf-8", "replace") if got else ""
        if name == "package.json":
            try:
                pkg = json.loads(text)
            except ValueError:
                continue
            if not isinstance(pkg, dict):
                continue
            deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
            web |= {d for d in deps if d in JS_WEB}
            # published library: the root package, or (monorepo) a package named after the repository
            pkg_name = str(pkg.get("name", "")).split("/")[-1].lower()
            if (p == "package.json" or pkg_name == full.split("/")[1].lower()) and not pkg.get("private") and any(
                    k in pkg for k in ("main", "module", "exports", "types", "typings")):
                published = True
        else:
            web |= py_deps(p, text)
    return {"truncated_tree": bool((tree or {}).get("truncated")), "web_deps": sorted(web),
            "deploy_files": deploy[:5], "published_package": published}


# words that are not also common in other Latin-script languages ("a", "in" are left out: Portuguese, German ...)
ENGLISH_WORDS = set("the and to of is for with you your this that it on are be can as or by from an will not "
                    "use using have has which all more our we if at".split())
MIN_ENGLISH_SHARE = 0.05  # calibrated 2026-11-02 on the 100 repos: non-English READMEs <= 0.0073, English >= 0.0755


def english_share(text):
    """Share of common English function words among the Latin-letter words of a README (code, HTML, URLs removed).
    Works for any script: Chinese/Japanese READMEs have almost no Latin words, Portuguese ones lack these words."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>|\]\([^)]*\)|https?://\S+", " ", text)
    words = re.findall(r"[A-Za-z]+", text)
    return round(sum(w.lower() in ENGLISH_WORDS for w in words) / max(len(words), 1), 4)


def readme_english_share(full, sha):
    data, _ = api(f"/repos/{full}/readme?ref={sha}")
    return english_share(base64.b64decode(data["content"]).decode("utf-8", "replace")) if data else 0.0


def main_language_sloc(key, lang):
    files = measure.OUT / key / "files.csv"
    with files.open(encoding="utf-8", newline="") as f:
        return sum(int(r["sloc"]) for r in csv.DictReader(f) if r["language"] == MEASURE_LANGUAGE[lang])


def evaluate(c, facts, prev, overrides):
    """(reason, facts) -- reason None = accepted. Facts are fetched only when the cheaper checks passed."""
    key, full = c["key"], c["full_name"]
    f = facts.setdefault(key, {})
    if c["id"] in prev:
        return "in agentic sample"
    if c["archived"] == "True" or c["fork"] == "True" or c["is_template"] == "True":
        return "archived / fork / template"
    reason = keyword_reason(c)
    if reason:
        return reason
    if "contributors" not in f:
        f["contributors"] = contributors(full)
    if f["contributors"] < MIN_CONTRIBUTORS:
        return f"contributors {f['contributors']} < {MIN_CONTRIBUTORS}"
    if "sha" not in f:
        f["branch"], f["sha"], f["pin_status"] = pin(c["url"])
    if f["pin_status"] != "ok":
        return f["pin_status"]
    if "commit_date" not in f:
        commit, _ = api(f"/repos/{full}/commits/{f['sha']}")
        f["commit_date"] = commit["commit"]["committer"]["date"] if commit else ""
    if f["commit_date"][:10] < PUSHED_SINCE:
        return f"last commit {f['commit_date'][:10]} on {f['branch']}"
    if "web_deps" not in f:
        f.update(web_facts(full, f["sha"]))
    if not f["web_deps"]:
        return "no web framework dependency"
    if not f["deploy_files"]:
        return "no deployment file"
    if f["published_package"]:
        return "published npm package (library)"
    # language last among the automatic rules: only otherwise-qualifying repos are judged (and can be reviewed)
    if "readme_english" not in f:
        f["readme_english"] = readme_english_share(full, f["sha"])
    if f["readme_english"] < MIN_ENGLISH_SHARE:
        return f"README not in English (share {f['readme_english']} < {MIN_ENGLISH_SHARE})"
    if key in overrides:
        return f"manual: {overrides[key]}"
    if "main_language_sloc" not in f:
        row = {"key": key, "url": c["url"], "branch": f["branch"], "sha": f["sha"]}
        if not (measure.OUT / key / "summary.json").exists():
            measure.measure_repo(row)
        f["main_language_sloc"] = main_language_sloc(key, c["main_language"])
    if f["main_language_sloc"] < MIN_SLOC:
        return f"{c['main_language']} SLOC {f['main_language_sloc']} < {MIN_SLOC}"
    return None


def main():
    global TOKEN
    TOKEN = token()
    OUT.mkdir(parents=True, exist_ok=True)
    facts_path = OUT / "screening_cache.json"
    facts = json.loads(facts_path.read_text(encoding="utf-8")) if facts_path.exists() else {}

    def save():
        facts_path.write_text(json.dumps(facts, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    # measurements of rejected repos live in repo_metrics_rejected/; bring them back so nothing is re-measured
    rejected_dir = OUT / "repo_metrics_rejected"
    measure.OUT.mkdir(parents=True, exist_ok=True)
    for d in sorted(rejected_dir.glob("*")) if rejected_dir.exists() else []:
        d.rename(measure.OUT / d.name)

    candidates = snapshot()
    prev = previous_ids(facts)
    save()
    overrides = {}
    if (OUT / "manual_exclusions.csv").exists():
        with (OUT / "manual_exclusions.csv").open(encoding="utf-8", newline="") as f:
            overrides = {r["key"]: r["reason"] for r in csv.DictReader(f)}

    screening, selected = [], []
    for lang, quota in QUOTA.items():
        pool = sorted((c for c in candidates if c["main_language"] == lang), key=lambda c: int(c["id"]))
        random.Random(f"{SEED}-{lang}").shuffle(pool)
        taken = 0
        for rank, c in enumerate(pool, 1):
            if taken == quota:
                break
            try:
                reason = evaluate(c, facts, prev, overrides)
            except Exception as e:  # network / fetch failure: not cached, so a rerun retries this repo
                save()
                print(f"FAILED {c['key']}: {e!r:.300}", flush=True)
                raise
            save()
            f = facts.get(c["key"], {})
            screening.append({"main_language": lang, "rank": rank, "key": c["key"], "url": c["url"],
                              "stars": c["stars"], "contributors": f.get("contributors", ""),
                              "commit_date": f.get("commit_date", ""), "web_deps": " ".join(f.get("web_deps", [])),
                              "main_language_sloc": f.get("main_language_sloc", ""), "decision": "selected" if reason is None
                              else "rejected", "reason": reason or "", "description": c["description"]})
            if reason is None:
                taken += 1
                selected.append({**c, "branch": f["branch"], "sha": f["sha"], "contributors": f["contributors"],
                                 "commit_date": f["commit_date"], "web_deps": " ".join(f["web_deps"]),
                                 "main_language_sloc": f["main_language_sloc"]})
            print(f"{lang:<10} #{rank:<5} {taken:>2}/{quota} {c['key']:<45} {reason or 'SELECTED'}", flush=True)
        if taken < quota:
            print(f"WARNING: {lang} pool exhausted with {taken}/{quota}")

    write_csv(OUT / "screening_results.csv", list(screening[0]), screening)
    sel_fields = ["key", "full_name", "url", "main_language", "stars", "contributors", "created_at", "commit_date",
                  "license", "web_deps", "main_language_sloc", "branch", "sha", "topics", "description"]
    write_csv(OUT / "selected_repos.csv", sel_fields,
              sorted(({k: r[k] for k in sel_fields} for r in selected), key=lambda r: r["key"].lower()))
    keep = {r["key"] for r in selected}  # repo_metrics/ = exactly the selected repos
    rejected_dir.mkdir(exist_ok=True)
    for d in sorted(measure.OUT.iterdir()):
        if d.name not in keep:
            d.rename(rejected_dir / d.name)
    print(f"selected {len(selected)} -> data/webapp/selected_repos.csv; "
          f"{len(screening)} examined -> screening_results.csv")


if __name__ == "__main__":
    main()
