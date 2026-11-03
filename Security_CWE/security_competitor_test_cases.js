/**
 * Security & CWE Competitor Benchmark Test Cases (JavaScript / TypeScript)
 * =========================================================================
 * Project: Dual-Lens Function-Level Code Quality & Security Assistant (CodeLens AI / AgentShield)
 * Advisor: Prof. Kookaip | Target: Senior Project 2026
 *
 * Competitor Evaluation Matrix:
 *   1. ESLint Security (eslint-plugin-security): `npx eslint security_competitor_test_cases.js`
 *   2. Semgrep OSS: `semgrep scan --config auto security_competitor_test_cases.js`
 *   3. Snyk Code
 */

const { exec, spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const http = require('http');

// ==============================================================================
// 1. CWE-78: OS Command Injection | OWASP A03:2021
// ==============================================================================
function vulnerable_cwe_078_compress_file(userFileName) {
  // Attacker Input: "document.pdf; rm -rf /" or "doc.pdf && cat /etc/passwd"
  // Competitor:
  //   - ESLint Security: Flags [security/detect-child-process]
  //   - Semgrep: Flags child_process execution rule
  //   - CodeLens AI: Explains CWE-78, CVSS 9.8, generates safe `spawn` with array arguments.
  exec(`tar -czf backup.tar.gz ${userFileName}`, (err, stdout, stderr) => {
    if (err) console.error(err);
    console.log(stdout);
  });
}

function remediated_cwe_078_compress_file(userFileName) {
  // Guardrail: Safe parameterized execution without shell parsing
  const sanitizedName = path.basename(userFileName);
  const child = spawn('tar', ['-czf', 'backup.tar.gz', sanitizedName]);
  child.stdout.on('data', (data) => console.log(data.toString()));
}

// ==============================================================================
// 2. CWE-1321: Prototype Pollution | OWASP A08:2021
// ==============================================================================
function vulnerable_cwe_1321_merge_config(targetConfig, userSuppliedJson) {
  // Attacker Input: JSON containing {"__proto__": {"isAdmin": true}}
  // Competitor:
  //   - ESLint Security: Flags [security/detect-object-injection]
  //   - Limitation: Produces huge numbers of false positives on standard object bracket access.
  //   - CodeLens AI: Specifically flags prototype pollution vulnerability and generates Object.create(null) or Map guardrail.
  const parsed = JSON.parse(userSuppliedJson);
  for (let key in parsed) {
    targetConfig[key] = parsed[key]; // Dangerous recursive or flat merge allowing __proto__ pollution
  }
  return targetConfig;
}

// ==============================================================================
// 3. CWE-022: Path Traversal (Arbitrary File Read)
// ==============================================================================
function vulnerable_cwe_022_serve_static(baseDir, requestedUrlPath) {
  // Attacker Input: "../../etc/shadow"
  // Competitor:
  //   - ESLint Security: Flags [security/detect-non-literal-fs-filename]
  //   - CodeLens AI: Generates safe path containment check using path.relative()
  const filePath = path.join(baseDir, requestedUrlPath);
  return fs.readFileSync(filePath, 'utf-8');
}

// ==============================================================================
// 4. OWASP LLM05:2025 & CWE-94: Agent Dynamic Tool Execution via eval()
// ==============================================================================
function vulnerable_owasp_llm05_agent_eval_action(llmActionJson) {
  // Modern Agent Scenario: AI Agent tool outputs dynamic code to execute
  // Competitor:
  //   - ESLint: Flags `no-eval`
  //   - Blindspot: Misses agent reasoning loop context and indirect prompt injection threat model
  //   - CodeLens AI: Maps to OWASP LLM05:2025 and injects isolated VM or sandbox parser
  const action = JSON.parse(llmActionJson);
  const result = eval(action.generatedScript);
  return result;
}

module.exports = {
  vulnerable_cwe_078_compress_file,
  remediated_cwe_078_compress_file,
  vulnerable_cwe_1321_merge_config,
  vulnerable_cwe_022_serve_static,
  vulnerable_owasp_llm05_agent_eval_action,
};
