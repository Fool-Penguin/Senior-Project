// Resolve JS/TS import specifiers inside one repository snapshot, without a checkout.
// stdin JSON: { paths: [all repo file paths], configs: {path: text} (tsconfig/jsconfig/package.json and
//               vite/webpack/vue/next/nuxt/babel configs), queries: [[fromFile, specifier], ...] }
// stdout JSON: { resolved: [resolvedRepoPath | null, ...] (same order as queries),
//                alias_unresolved: number of unresolved specifiers that look like project aliases }
// Uses the TypeScript module resolver (tsconfig paths/baseUrl, extensions, index files, .js -> .ts).
// Workspace packages (package.json "name" inside the repo) resolve to their folder, because the repo
// is never `npm install`ed: node_modules/<name>/... is mapped onto the package folder.
import path from 'node:path';
import ts from 'typescript';

const ROOT = '/repo/';
const input = JSON.parse(await new Promise((ok) => {
  let s = ''; process.stdin.on('data', (d) => { s += d; }).on('end', () => ok(s));
}));
const files = new Set(input.paths.map((p) => ROOT + p));
const dirs = new Set(['/repo']);
const entries = new Map(); // dir -> {files, directories} (base names), for tsconfig include/files matching
const entry = (d) => { if (!entries.has(d)) entries.set(d, { files: new Set(), directories: new Set() }); return entries.get(d); };
for (const p of files) {
  entry(p.slice(0, p.lastIndexOf('/'))).files.add(p.slice(p.lastIndexOf('/') + 1));
  for (let d = p.slice(0, p.lastIndexOf('/')); d.length > 5; d = d.slice(0, d.lastIndexOf('/'))) {
    dirs.add(d);
    entry(d.slice(0, d.lastIndexOf('/'))).directories.add(d.slice(d.lastIndexOf('/') + 1));
  }
}
const configs = Object.fromEntries(Object.entries(input.configs).map(([k, v]) => [ROOT + k, v]));
const byPath = ([a], [b]) => (a < b ? -1 : a > b ? 1 : 0);
const byDepth = (x, y) => (x[0].split('/').length - y[0].split('/').length) || byPath(x, y);

const workspace = {}; // package name -> folder; duplicates: the shallowest package.json wins
for (const [p, text] of Object.entries(configs).sort(byDepth)) {
  if (!p.endsWith('/package.json') || p.includes('/node_modules/')) continue;
  try { const name = JSON.parse(text).name; if (typeof name === 'string' && !(name in workspace)) workspace[name] = p.slice(0, -13); } catch { /* invalid json */ }
}
const hasWorkspace = Object.keys(workspace).length > 0;
const NM = /\/node_modules\/((?:@[^/]+\/)?[^/]+)(\/.*)?$/;
const real = (p) => { const m = NM.exec(p); return m && workspace[m[1]] ? workspace[m[1]] + (m[2] || '') : p; };
const fsEntries = (d) => {
  const e = entries.get(d.replace(/\/$/, ''));
  return e ? { files: [...e.files].sort(), directories: [...e.directories].sort() } : { files: [], directories: [] };
};
const host = {
  fileExists: (p) => files.has(real(p)),
  readFile: (p) => configs[real(p)],
  // any node_modules dir "exists" when the repo has workspace packages, so TypeScript looks inside it and real()
  // can map node_modules/<name> onto the package folder (main/types/exports are then read)
  directoryExists: (p) => { const d = real(p).replace(/\/$/, ''); return dirs.has(d) || (hasWorkspace && d.endsWith('/node_modules')); },
  getCurrentDirectory: () => '/repo',
  getDirectories: () => [],
  realpath: real,
  useCaseSensitiveFileNames: true,
  // ts.matchFiles is internal API; typescript is pinned in package-lock.json
  readDirectory: (root, exts, excl, incl, depth) => ts.matchFiles(root, exts, excl, incl, true, '/repo', depth, fsEntries, real),
};

const BUNDLER = { module: ts.ModuleKind.ESNext, moduleResolution: ts.ModuleResolutionKind.Bundler };
const BASE = { allowJs: true, resolveJsonModule: true, ...BUNDLER };
const MODERN = [ts.ModuleResolutionKind.Node16, ts.ModuleResolutionKind.NodeNext, ts.ModuleResolutionKind.Bundler];
const parsedCache = new Map(); // config path -> {options, fileNames, refs, hasPaths}
function parseConfig(cfg) {
  if (!parsedCache.has(cfg)) {
    let info = { options: BASE, fileNames: new Set(), refs: [], hasPaths: false };
    try {
      const parsed = ts.parseConfigFileTextToJson(cfg, configs[cfg]);
      // allowJs so .js files can be covered by include (the config's own allowJs still wins)
      const res = ts.parseJsonConfigFileContent(parsed.config ?? {}, host, cfg.slice(0, cfg.lastIndexOf('/')), { allowJs: true }, cfg);
      let options = { ...BASE, ...res.options };
      // module systems that cannot resolve modern packages fall back to Bundler
      if (!MODERN.includes(options.moduleResolution)) options = { ...options, ...BUNDLER };
      info = { options, fileNames: new Set(res.fileNames), hasPaths: !!res.options.paths,
        refs: (res.projectReferences ?? []).map((r) => ts.resolveProjectReferencePath(r)).filter((p) => p in configs) };
    } catch { /* broken config: keep BASE */ }
    parsedCache.set(cfg, info);
  }
  return parsedCache.get(cfg);
}

// Nearest tsconfig.json/jsconfig.json. A solution config (Vite: `files: []` + `references`) covers no file
// itself: follow the references and use the config whose include/files covers the file, else the first
// config with `paths`, else the nearest config.
function optionsFor(file) {
  for (let d = file.slice(0, file.lastIndexOf('/')); d.length >= 5; d = d.slice(0, d.lastIndexOf('/'))) {
    for (const name of ['tsconfig.json', 'jsconfig.json']) {
      const cfg = `${d}/${name}`;
      if (!(cfg in configs)) continue;
      const order = [];
      const visit = (c) => { if (!order.includes(c)) { order.push(c); parseConfig(c).refs.forEach(visit); } };
      visit(cfg);
      return parseConfig(order.find((c) => parseConfig(c).fileNames.has(file))
        ?? order.find((c) => parseConfig(c).hasPaths) ?? cfg).options;
    }
  }
  return BASE;
}

// Node16/NodeNext without a resolution mode resolves like CommonJS, so a package whose `exports` only has an
// "import" condition fails: retry once with Bundler.
function resolve(spec, from) {
  const options = optionsFor(from);
  const tries = options.moduleResolution === ts.ModuleResolutionKind.Bundler ? [options] : [options, { ...options, ...BUNDLER }];
  for (const o of tries) {
    try {
      const hit = ts.resolveModuleName(spec, from, o, host).resolvedModule;
      if (hit) return real(hit.resolvedFileName);
    } catch { /* resolver error: try the next mode */ }
  }
  return null;
}

// .d.ts files are not measured: an import that lands on one goes to the sibling source with the same stem.
const DTS = /\.d\.([cm]?)ts$/;
function measurable(target) {
  const m = target && DTS.exec(target);
  if (!m) return target;
  const stem = target.slice(0, m.index);
  return (m[1] ? [`.${m[1]}ts`, `.${m[1]}js`] : ['.ts', '.tsx', '.js', '.jsx']).map((e) => stem + e).find((p) => files.has(p)) ?? null;
}

// Bundler aliases (vite/webpack/vue/next/nuxt/babel config): simple string forms only, read with regexes.
//   '@': path.resolve(__dirname, 'src')   '@': fileURLToPath(new URL('./src', import.meta.url))   '@': '/src'
//   { find: '@', replacement: ... }   config.resolve.alias['@'] = ...
// A config dir with none of these gets `@/` and `~/` -> <config dir>/src/ (Nuxt: also app/ and the dir itself).
// Aliases apply to files under the config's dir and are used only when TypeScript resolution fails.
const BUNDLER_CONFIG = /\/((vite|vitest|webpack|vue|next|nuxt|babel)\.config[^/]*\.[cm]?[jt]s|\.babelrc(\.json)?)$/;
const STR = String.raw`['"\x60]([^'"\x60]+)['"\x60]`;
const join = (dir, ...segs) => { const p = path.posix.join(dir, ...segs); return p === '/repo' || p.startsWith(ROOT) ? p : null; };
function aliasTarget(value, dir) {
  let m = new RegExp(String.raw`^(?:path\.)?(?:resolve|join)\(\s*(?:(?:__dirname|import\.meta\.dirname|process\.cwd\(\))\s*,\s*)?((?:${STR}\s*,?\s*)+)\)`).exec(value);
  if (m) return join(dir, ...[...m[1].matchAll(new RegExp(STR, 'g'))].map((x) => x[1]));
  m = new RegExp(String.raw`^(?:fileURLToPath\(\s*)?new URL\(\s*${STR}\s*,\s*import\.meta\.url\s*\)`).exec(value);
  if (m) return join(dir, m[1]);
  m = new RegExp(String.raw`^['"\x60]([./][^'"\x60]*)['"\x60]`).exec(value);
  return m ? join(dir, m[1].replace(/^\//, './')) : null; // Vite '/src' = project root
}
function extractAliases(text, dir) {
  const found = [];
  const add = (key, value) => { const t = aliasTarget(value, dir); if (t) found.push([key.replace(/\$$/, ''), [t]]); };
  for (const m of text.matchAll(/\balias\s*:\s*\{/g)) { // object form: balanced braces
    const start = m.index + m[0].length;
    let depth = 1, end = start;
    while (end < text.length && depth) { depth += text[end] === '{' ? 1 : text[end] === '}' ? -1 : 0; end++; }
    const block = text.slice(start, end - 1);
    for (const k of block.matchAll(/(?:^|[,\s])(['"]?)([@~$\w./-]+)\1\s*:\s*/g)) add(k[2], block.slice(k.index + k[0].length));
  }
  for (const k of text.matchAll(new RegExp(String.raw`find\s*:\s*${STR}\s*,\s*replacement\s*:\s*`, 'g'))) add(k[1], text.slice(k.index + k[0].length));
  for (const k of text.matchAll(new RegExp(String.raw`alias\[\s*${STR}\s*\]\s*=\s*`, 'g'))) add(k[1], text.slice(k.index + k[0].length));
  return found;
}
const aliasesByDir = new Map(); // config dir -> [[key, [target dirs]]], longest key first
const nuxtDirs = new Set();
for (const [p, text] of Object.entries(configs).sort(byPath)) {
  if (!BUNDLER_CONFIG.test(p)) continue;
  const dir = p.slice(0, p.lastIndexOf('/'));
  aliasesByDir.set(dir, [...(aliasesByDir.get(dir) ?? []), ...extractAliases(text, dir)]);
  if (/\/nuxt\.config/.test(p)) nuxtDirs.add(dir);
}
for (const [dir, list] of aliasesByDir) {
  if (!list.length) {
    const targets = [`${dir}/src`, ...(nuxtDirs.has(dir) ? [`${dir}/app`, dir] : [])];
    list.push(['@', targets], ['~', targets]);
  }
  list.sort((a, b) => b[0].length - a[0].length || (a[0] < b[0] ? -1 : 1));
}
function aliasesFor(file) {
  for (let d = file.slice(0, file.lastIndexOf('/')); d.length >= 5; d = d.slice(0, d.lastIndexOf('/'))) {
    if (aliasesByDir.has(d)) return aliasesByDir.get(d);
  }
  return [];
}
const matches = (spec, key) => spec === key || spec.startsWith(key + '/');

let aliasUnresolved = 0;
const resolved = input.queries.map(([fromRel, spec]) => {
  const from = ROOT + fromRel;
  const first = resolve(spec, from);
  let target = measurable(first);
  if (!target) { // workspace package whose entry points at build output (dist/) not in the repo
    const name = Object.keys(workspace).filter((n) => matches(spec, n)).sort((a, b) => b.length - a.length)[0];
    if (name) {
      const sub = spec.slice(name.length + 1);
      const fake = `${workspace[name]}/__resolve__.ts`;
      for (const cand of sub ? [`./src/${sub}`, `./${sub}`] : ['./src', './src/index', '.', './index']) {
        target = measurable(resolve(cand, fake));
        if (target) break;
      }
    }
  }
  const aliases = aliasesFor(from);
  if (!target && !first) { // bundler alias
    const hit = aliases.find(([key]) => matches(spec, key));
    for (const dir of hit ? hit[1] : []) {
      target = measurable(resolve(dir + spec.slice(hit[0].length), from));
      if (target) break;
    }
  }
  target = target ?? first; // a .d.ts with no source sibling: resolved, but not a measured file
  const ok = target && files.has(target);
  if (!ok) {
    const prefixes = Object.keys(optionsFor(from).paths ?? {}).map((k) => k.split('*')[0]).filter(Boolean);
    if (['@/', '~/', 'src/', ...prefixes].some((p) => spec.startsWith(p))
      || Object.keys(workspace).some((n) => matches(spec, n)) || aliases.some(([key]) => matches(spec, key))) aliasUnresolved++;
  }
  return ok ? target.slice(ROOT.length) : null;
});
process.stdout.write(JSON.stringify({ resolved, alias_unresolved: aliasUnresolved }));
