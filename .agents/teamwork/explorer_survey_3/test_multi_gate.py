import ast
import re
import tree_sitter
import tree_sitter_python
import tree_sitter_javascript
from typing import Dict, Any, Tuple, List

PY_LANG = tree_sitter.Language(tree_sitter_python.language())
JS_LANG = tree_sitter.Language(tree_sitter_javascript.language())

class InMemoryMultiGateVerifier:
    def __init__(self):
        self.py_parser = tree_sitter.Parser(PY_LANG)
        self.js_parser = tree_sitter.Parser(JS_LANG)

    def _get_parser(self, lang: str):
        return self.py_parser if lang == "python" else self.js_parser

    def clean_code(self, raw_code: str, lang: str) -> str:
        # Extract markdown code blocks
        pattern = rf"```(?:{lang}|python|javascript|js)?\s*\n(.*?)\n```"
        match = re.search(pattern, raw_code, flags=re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        cleaned = re.sub(r"^```(?:[a-zA-Z]+)?\s*\n?", "", raw_code.strip())
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
        return cleaned.strip()

    def gate1_cst_syntax(self, code: str, lang: str) -> Tuple[bool, str]:
        parser = self._get_parser(lang)
        tree = parser.parse(code.encode("utf-8"))
        if tree.root_node.has_error:
            # Locate first error
            def find_err(node):
                if node.is_error or node.is_missing:
                    return f"Syntax error ({node.type}) at row {node.start_point.row+1}, col {node.start_point.column}"
                for c in node.children:
                    res = find_err(c)
                    if res:
                        return res
                return "Syntax defect"
            return False, find_err(tree.root_node)
        if lang == "python":
            try:
                ast.parse(code)
            except SyntaxError as e:
                return False, f"Python AST syntax error at line {e.lineno}: {e.msg}"
        return True, "Gate 1 Passed: 100% syntactically valid CST"

    def gate2_interface_preservation(
        self, orig_code: str, patch_code: str, lang: str, expected_func_name: str
    ) -> Tuple[bool, str]:
        parser = self._get_parser(lang)
        t_orig = parser.parse(orig_code.encode("utf-8"))
        t_patch = parser.parse(patch_code.encode("utf-8"))

        def extract_sig(root):
            fn_types = {"function_definition", "async_function_definition", "function_declaration", "method_definition"}
            stack = [root]
            while stack:
                n = stack.pop()
                if n.type in fn_types:
                    name = None
                    params = []
                    for c in n.children:
                        if c.type in {"identifier", "property_identifier"} and not name:
                            name = c.text.decode("utf-8")
                        elif c.type in {"parameters", "formal_parameters"}:
                            for p in c.children:
                                if p.type in {"identifier", "typed_parameter", "formal_parameter"}:
                                    params.append(p.text.decode("utf-8").split(":")[0].strip())
                    if name == expected_func_name:
                        return name, params
                stack.extend(reversed(n.children))
            return None, None

        orig_name, orig_params = extract_sig(t_orig.root_node)
        patch_name, patch_params = extract_sig(t_patch.root_node)

        if not patch_name:
            return False, f"Gate 2 Failed: Expected function '{expected_func_name}' not found in patch"
        if orig_params != patch_params:
            return False, f"Gate 2 Failed: Parameter signature mismatch. Original {orig_params} vs Patch {patch_params}"

        return True, f"Gate 2 Passed: Signature '{expected_func_name}({', '.join(orig_params)})' preserved"

    def gate3_taint_neutralization(self, patch_code: str, lang: str, cwe_id: str = "CWE-89") -> Tuple[bool, str]:
        parser = self._get_parser(lang)
        tree = parser.parse(patch_code.encode("utf-8"))
        code_bytes = patch_code.encode("utf-8")

        # Find call expressions with execute/query
        vulnerable = False
        neutralized = False
        reasons = []

        stack = [tree.root_node]
        while stack:
            n = stack.pop()
            if n.type in {"call", "call_expression"}:
                call_text = n.text.decode("utf-8")
                if "execute" in call_text or "query" in call_text:
                    # Check arguments
                    args_node = None
                    for c in n.children:
                        if c.type in {"argument_list", "arguments"}:
                            args_node = c
                            break
                    if args_node:
                        # Extract arguments
                        args = [child for child in args_node.children if child.type not in {"(", ")", ","}]
                        if args:
                            first_arg = args[0]
                            # Check if first arg has string concat / formatting
                            if lang == "python":
                                if first_arg.type in {"binary_operator", "formatted_string"}:
                                    vulnerable = True
                                    reasons.append("First argument contains dynamic formatting or binary operator")
                                elif len(args) >= 2:
                                    neutralized = True
                            elif lang in {"javascript", "typescript"}:
                                if first_arg.type in {"binary_expression"}:
                                    vulnerable = True
                                    reasons.append("First argument contains string concatenation (+)")
                                elif first_arg.type == "template_string" and any(c.type == "template_substitution" for c in first_arg.children):
                                    vulnerable = True
                                    reasons.append("First argument contains unescaped template substitution")
                                elif len(args) >= 2:
                                    neutralized = True
            stack.extend(reversed(n.children))

        # Check for lingering regex patterns in code
        if lang == "python":
            if re.search(r"execute\s*\(\s*f[\"']", patch_code):
                return False, "Gate 3 Failed: SQL query still constructed with dynamic f-string"
            if re.search(r"execute\s*\(\s*.*%\s*\(", patch_code):
                return False, "Gate 3 Failed: SQL query still constructed with raw % formatting"
            if "execute(" in patch_code and (", (" in patch_code or ", [" in patch_code or "?" in patch_code or "%s" in patch_code):
                neutralized = True

        if lang in {"javascript", "typescript"}:
            if re.search(r"query\s*\(\s*`[^`]*\${", patch_code):
                return False, "Gate 3 Failed: SQL query still constructed with template literal interpolation"
            if "query(" in patch_code and (", [" in patch_code or "$1" in patch_code or "?" in patch_code):
                neutralized = True

        if vulnerable:
            return False, f"Gate 3 Failed: {'; '.join(reasons)}"
        if neutralized:
            return True, "Gate 3 Passed: SQL sink successfully neutralized via parameterized query"
        return True, "Gate 3 Passed: Dynamic sink eliminated"

    def gate4_maintainability(self, orig_code: str, patch_code: str, lang: str) -> Tuple[bool, Dict[str, Any]]:
        parser = self._get_parser(lang)
        def compute_cc(code: str) -> int:
            tree = parser.parse(code.encode("utf-8"))
            cc = 1
            decision_types = {
                "python": {"if_statement", "elif_clause", "for_statement", "while_statement", "except_clause", "boolean_operator"},
                "javascript": {"if_statement", "for_statement", "while_statement", "for_in_statement", "catch_clause", "ternary_expression", "switch_case"}
            }.get(lang, {"if_statement"})

            stack = [tree.root_node]
            while stack:
                curr = stack.pop()
                if curr.type in decision_types:
                    cc += 1
                stack.extend(reversed(curr.children))
            return cc

        cc_orig = compute_cc(orig_code)
        cc_patch = compute_cc(patch_code)
        delta_cc = cc_patch - cc_orig

        # Non-regression: delta CC <= 0
        passed = delta_cc <= 0
        metrics = {
            "cc_orig": cc_orig,
            "cc_patch": cc_patch,
            "delta_cc": delta_cc,
            "passed": passed
        }
        return passed, metrics

    def gate6_sast_rescan(self, patch_code: str, lang: str) -> Tuple[bool, List[str]]:
        new_flaws = []
        if lang == "python":
            if "eval(" in patch_code:
                new_flaws.append("CWE-94: Introduced eval()")
            if "exec(" in patch_code:
                new_flaws.append("CWE-94: Introduced exec()")
            if "shell=True" in patch_code:
                new_flaws.append("CWE-78: Introduced shell=True")
            if "pickle.loads(" in patch_code:
                new_flaws.append("CWE-502: Introduced pickle.loads()")
        elif lang in {"javascript", "typescript"}:
            if "eval(" in patch_code:
                new_flaws.append("CWE-94: Introduced eval()")
            if "child_process" in patch_code and "exec(" in patch_code:
                new_flaws.append("CWE-78: Introduced command execution")

        return len(new_flaws) == 0, new_flaws

    def verify_patch(
        self, orig_code: str, raw_patch: str, lang: str, expected_func_name: str, cwe_id: str = "CWE-89"
    ) -> Dict[str, Any]:
        clean = self.clean_code(raw_patch, lang)
        g1_ok, g1_msg = self.gate1_cst_syntax(clean, lang)
        if not g1_ok:
            return {"all_passed": False, "failed_gate": "Gate 1", "diagnostics": {"gate1": g1_msg}, "code": clean}

        g2_ok, g2_msg = self.gate2_interface_preservation(orig_code, clean, lang, expected_func_name)
        if not g2_ok:
            return {"all_passed": False, "failed_gate": "Gate 2", "diagnostics": {"gate2": g2_msg}, "code": clean}

        g3_ok, g3_msg = self.gate3_taint_neutralization(clean, lang, cwe_id)
        if not g3_ok:
            return {"all_passed": False, "failed_gate": "Gate 3", "diagnostics": {"gate3": g3_msg}, "code": clean}

        g4_ok, g4_metrics = self.gate4_maintainability(orig_code, clean, lang)
        if not g4_ok:
            return {"all_passed": False, "failed_gate": "Gate 4", "diagnostics": {"gate4": f"Delta CC {g4_metrics['delta_cc']} > 0"}, "code": clean}

        g6_ok, g6_flaws = self.gate6_sast_rescan(clean, lang)
        if not g6_ok:
            return {"all_passed": False, "failed_gate": "Gate 6", "diagnostics": {"gate6": g6_flaws}, "code": clean}

        return {
            "all_passed": True,
            "failed_gate": None,
            "diagnostics": {
                "gate1": g1_msg,
                "gate2": g2_msg,
                "gate3": g3_msg,
                "gate4": f"Delta CC: {g4_metrics['delta_cc']} (orig={g4_metrics['cc_orig']}, patch={g4_metrics['cc_patch']})",
                "gate6": "Zero new security flaws detected"
            },
            "code": clean
        }

verifier = InMemoryMultiGateVerifier()

# Test Python patch verification
py_orig = """def find_user_by_id(user_id: int):
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    cursor.execute(query)
    return cursor.fetchone()
"""

py_patch = """```python
def find_user_by_id(user_id: int):
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE id = ?"
    cursor.execute(query, (user_id,))
    return cursor.fetchone()
```"""

print("=== Verifying Python Patch ===")
res_py = verifier.verify_patch(py_orig, py_patch, "python", "find_user_by_id")
print("Python Verified:", res_py["all_passed"])
for k, v in res_py["diagnostics"].items():
    print(f"  {k}: {v}")

# Test JS patch verification
js_orig = """async function getUserProfile(req, res) {
    const userId = req.query.id;
    const client = new Client();
    await client.connect();
    const query = "SELECT * FROM profiles WHERE user_id = '" + userId + "'";
    const result = await client.query(query);
    res.json(result.rows);
}"""

js_patch = """```javascript
async function getUserProfile(req, res) {
    const userId = req.query.id;
    const client = new Client();
    await client.connect();
    const query = "SELECT * FROM profiles WHERE user_id = $1";
    const result = await client.query(query, [userId]);
    res.json(result.rows);
}
```"""

print("\n=== Verifying JS Patch ===")
res_js = verifier.verify_patch(js_orig, js_patch, "javascript", "getUserProfile")
print("JS Verified:", res_js["all_passed"])
for k, v in res_js["diagnostics"].items():
    print(f"  {k}: {v}")
