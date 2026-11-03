import yaml

with open('data/security_vulnerability_catalogue.yaml', 'r', encoding='utf-8') as f:
    text = f.read()

injection_to_insert = """

  - id: "VULN-INJ-007"
    cwe_id: "CWE-77"
    name: "Improper Neutralization of Special Elements used in a Command ('Command Injection')"
    owasp_web: "A05:2025-Injection"
    mitre_cwe_rank: 23
    severity: "CRITICAL"
    cvss_v31_base: 9.8
    cvss_v31_vector: "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    languages: ["python", "javascript", "typescript"]
    detection_approach: "Inter-procedural Taint Graph + Command Argument Vector Verification"
    attribution:
      cwe_definition: "https://cwe.mitre.org/data/definitions/77.html"
      owasp_category: "https://owasp.org/Top10/A05_2025-Injection/"
      sanitizer_cheat_sheet: "https://cheatsheetseries.owasp.org/cheatsheets/OS_Command_Injection_Defense_Cheat_Sheet.html"
      node_printer_cve: "CVE-2014-3741 (tojocky/node-printer)"
    source_patterns:
      python: ["request.args.get('cmd')", "request.form.get('printer')", "request.json.get('args')", "os.environ.get('CLI_PARAM')"]
      javascript: ["req.query.printer", "req.body.temp_file_name", "req.params.command", "process.env.TARGET"]
    sink_patterns:
      python: ["os.system(cmd_string)", "os.popen(cmd_string)", "subprocess.Popen(cmd_string, shell=True)"]
      javascript: ["child_process.exec(cmdString)", "child_process.execSync(cmdString)", "child_process.spawn(cmdString, { shell: true })"]
    sanitizer_patterns:
      python:
        - "subprocess.run([binary_path, arg1, arg2], shell=False)"
        - "shlex.quote(user_param)"
        - "shlex.split(safe_command)"
        - 'Input validation against strict alphanumeric whitelist regex: re.match(r"^[a-zA-Z0-9_.-]+$", param)'
      javascript:
        - "child_process.execFile(executable, [arg1, arg2])"
        - "child_process.spawn(executable, [arg1, arg2], { shell: false })"
        - "Argument array tokenization preventing shell metacharacter expansion (;|&$`<>)"
        - 'Sanitization using strict regex allowlist /^[a-zA-Z0-9_.-]+$/ before command execution'
    dataset_sample:
      sample_id: "CVEFIXES_CVE_2014_3741_03086"
      source_dataset: "hitoshura25_cvefixes_all.parquet (Bhandari et al., MSR 2021)"
      source_type: "real_repo"
      vulnerable_code: "child_process.exec('lpr -P'+printer+' -oraw -r'+' '+temp_file_name, function(err, stdout, stderr){"
      fixed_code: "child_process.execFile('lpr', ['-P' + printer, '-oraw', '-r', temp_file_name], function(err, stdout, stderr){"

  - id: "VULN-INJ-008"
    cwe_id: "CWE-95"
    name: "Improper Neutralization of Directives in Dynamically Evaluated Code ('Eval Injection')"
    owasp_web: "A05:2025-Injection"
    mitre_cwe_rank: null
    severity: "CRITICAL"
    cvss_v31_base: 9.8
    cvss_v31_vector: "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    languages: ["python", "javascript", "typescript"]
    detection_approach: "AST Dynamic Code Execution Detector + Taint Flow Analyzer"
    attribution:
      cwe_definition: "https://cwe.mitre.org/data/definitions/95.html"
      owasp_category: "https://owasp.org/Top10/A05_2025-Injection/"
      mdn_eval_docs: "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/eval"
      cyberseceval_ref: "Meta Purple Llama CyberSecEval 2 Benchmark (Bhatt et al., 2024)"
    source_patterns:
      python: ["request.args.get('userMathFormula')", "request.json.get('calc')", "request.form.get('expr')"]
      javascript: ["req.query.userMathFormula", "req.body.formula", "req.params.calculation"]
    sink_patterns:
      python: ["eval('(' + user_math_formula + ')')", "eval(user_expression)", "exec(user_code)"]
      javascript: ["eval('(' + userMathFormula + ')')", "eval(userExpression)", "new Function(userFormula)()"]
    sanitizer_patterns:
      python:
        - "ast.literal_eval(user_data) (safely parses literal expressions without executing code)"
        - "mathjs or sympy parse_expr with safe AST visitor banning builtins and call nodes"
        - "Operator lookup dispatch dictionary (e.g. {'+': operator.add, '-': operator.sub})"
        - 'Input validation against strict arithmetic regex: re.match(r"^[0-9+\\-*/().\\s]+$", expr)'
      javascript:
        - "vm.runInNewContext(userMathFormula, Object.create(null), { timeout: 200 }) (isolated VM sandbox)"
        - "Dedicated safe math expression parser library (e.g. expr-eval, mathjs.evaluate with scope lockdown)"
        - "JSON.parse(user_data) for structured serialized payloads"
        - 'Strict tokenization whitelist regex allowing only digits and basic arithmetic operators: /^[0-9+\\-*/().\\s]+$/'
    dataset_sample:
      sample_id: "CYBERSECEVAL_JS_CWE95_EVAL_01"
      source_dataset: "meta_cyberseceval_autocomplete.json (Bhatt et al., 2024)"
      source_type: "synthetic_manual"
      vulnerable_code: "function processDynamicCalculation(userMathFormula) { return eval('(' + userMathFormula + ')'); }"
      fixed_code: "const vm = require('vm'); function processDynamicCalculation(userMathFormula) { const sandbox = Object.create(null); return vm.runInNewContext(userMathFormula, sandbox, { timeout: 200 }); }"
"""

marker = "# CATEGORY: CLIENT-SIDE & CROSS-SITE SCRIPTING (OWASP A05:2025)"
if marker not in text:
    raise ValueError(f"Marker not found: {marker}")

parts = text.split(marker)
new_text = parts[0].rstrip() + injection_to_insert + "\n\n  " + marker + parts[1]

# Validate with pyyaml
data = yaml.safe_load(new_text)
inclusions = data.get('inclusions', [])
cwe_ids = [x.get('cwe_id') for x in inclusions]
assert "CWE-77" in cwe_ids, "CWE-77 missing"
assert "CWE-95" in cwe_ids, "CWE-95 missing"

with open('data/security_vulnerability_catalogue.yaml', 'w', encoding='utf-8') as f:
    f.write(new_text)

print(f"Successfully added CWE-77 and CWE-95! Total inclusions now: {len(inclusions)}")
