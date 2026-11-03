/**
 * Native JavaScript AST Parser Engine
 * Evaluates industry-standard JS AST parsers:
 *  1. Babel Parser (@babel/parser) - De facto compiler AST
 *  2. Acorn (ESTree standard) - Engine for ESLint, Webpack, Rollup
 */

const fs = require('fs');
const path = require('path');
const babelParser = require('../../node_modules/@babel/parser');
const acorn = require('../../node_modules/acorn');

function benchmarkFile(filePath, iterations = 100) {
  const code = fs.readFileSync(filePath, 'utf-8');

  // 1. Babel Parser Cold Parse
  const babelTimes = [];
  let babelTree = null;
  for (let i = 0; i < iterations; i++) {
    const t0 = process.hrtime.bigint();
    babelTree = babelParser.parse(code, {
      sourceType: 'unambiguous',
      plugins: ['jsx', 'typescript']
    });
    const t1 = process.hrtime.bigint();
    babelTimes.push(Number(t1 - t0) / 1e6); // ms
  }
  const avgBabelMs = babelTimes.reduce((a, b) => a + b, 0) / iterations;

  // 2. Acorn ESTree Parser Cold Parse
  const acornTimes = [];
  let acornTree = null;
  for (let i = 0; i < iterations; i++) {
    const t0 = process.hrtime.bigint();
    acornTree = acorn.parse(code, {
      ecmaVersion: 'latest',
      sourceType: 'module'
    });
    const t1 = process.hrtime.bigint();
    acornTimes.push(Number(t1 - t0) / 1e6); // ms
  }
  const avgAcornMs = acornTimes.reduce((a, b) => a + b, 0) / iterations;

  // 3. Comments in AST vs raw code
  const rawCommentCount = (code.match(/\/\/|\/\*/g) || []).length;

  return {
    file: path.basename(filePath),
    loc: code.split('\n').length,
    bytes: Buffer.byteLength(code, 'utf-8'),
    babel_avg_ms: parseFloat(avgBabelMs.toFixed(4)),
    acorn_avg_ms: parseFloat(avgAcornMs.toFixed(4)),
    raw_comments: rawCommentCount
  };
}

// Check if running from CLI directly
if (require.main === module) {
  const targetFile = process.argv[2];
  const iters = parseInt(process.argv[3] || '100', 10);
  if (!targetFile) {
    console.error('Usage: node js_ast_parser.js <filePath> [iterations]');
    process.exit(1);
  }
  const res = benchmarkFile(targetFile, iters);
  console.log(JSON.stringify(res, null, 2));
}

module.exports = { benchmarkFile };
