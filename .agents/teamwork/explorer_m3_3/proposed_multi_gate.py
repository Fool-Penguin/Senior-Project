"""
proposed_multi_gate.py - Reference implementation for MultiGateVerifier.
"""

import difflib
import re
from typing import Any, Dict, List, Optional, Tuple

import tree_sitter

from app.maintainability.engine import MaintainabilityEngine
from app.models.contracts import GateResult, GateVerificationResult, VerifiedPatch
from app.parser.cst_manager import CSTParserManager, LanguageType
from app.taint.walker import SymbolicTaintWalker


class MultiGateVerifier:
    """
    In-memory verifier executing Gates 1, 2, 3, 4, and 6 on candidate patches.
    Enforces 100% pass rate across:
    - Gate 1: Tree-sitter CST Syntax validity
    - Gate 2: Interface preservation (function name and parameter signature)
    - Gate 3: Taint sink neutralization (direct concatenation/interpolation removed)
    - Gate 4: Maintainability non-regression (delta CC <= 0)
    - Gate 6: SAST re-scan check (zero new flaws)
    """

    _instance: Optional["MultiGateVerifier"] = None

    @classmethod
    def get_instance(cls) -> "MultiGateVerifier":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self.cst_manager = CSTParserManager.get_instance()
        self.maintainability_engine = MaintainabilityEngine()
        self.taint_walker = SymbolicTaintWalker()

    def verify_gate_1_syntax(self, candidate_code: str, language: str) -> GateResult:
        """Gate 1: Tree-sitter CST syntax validity check."""
        try:
            tree = self.cst_manager.parse(candidate_code, language)
            if tree.root_node.has_error:
                error_locs: List[str] = []

                def walk(n: tree_sitter.Node):
                    if n.type == "ERROR" or n.is_missing:
                        error_locs.append(f"{n.type} at line {n.start_point.row + 1}")
                    for c in n.children:
                        walk(c)

                walk(tree.root_node)
                msg = ", ".join(error_locs[:3]) if error_locs else "Syntax error in AST"
                return GateResult(passed=False, details=f"Gate 1 failed: {msg}")
            return GateResult(passed=True, details="Gate 1 passed: CST syntax parsed with zero errors")
        except Exception as e:
            return GateResult(passed=False, details=f"Gate 1 failed with exception: {str(e)}")

    def extract_function_signatures(self, code: str, language: str) -> List[Tuple[str, List[str]]]:
        """Extract function names and formal parameter names from code."""
        tree = self.cst_manager.parse(code, language)
        signatures: List[Tuple[str, List[str]]] = []

        def visit(node: tree_sitter.Node):
            if node.type in ("function_definition", "function_declaration", "method_definition"):
                name = ""
                params: List[str] = []
                for child in node.children:
                    if child.type in ("identifier", "property_identifier") and not name:
                        name = code[child.start_byte : child.end_byte]
                    elif child.type in ("parameters", "formal_parameters"):
                        for p in child.children:
                            if p.type in ("identifier", "typed_parameter", "default_parameter", "pattern", "required_parameter", "optional_parameter"):
                                p_str = code[p.start_byte : p.end_byte].split(":")[0].split("=")[0].strip()
                                if p_str and p_str not in ("(", ")", ",", "self", "cls"):
                                    params.append(p_str)
                if name:
                    signatures.append((name, params))
            for c in node.children:
                visit(c)

        visit(tree.root_node)
        return signatures

    def verify_gate_2_interface(
        self, original_code: str, candidate_code: str, language: str
    ) -> GateResult:
        """Gate 2: Interface preservation check (function name and parameter names preserved)."""
        orig_sigs = self.extract_function_signatures(original_code, language)
        cand_sigs = self.extract_function_signatures(candidate_code, language)

        if not orig_sigs:
            return GateResult(passed=True, details="Gate 2 passed: Standalone code snippet with no enclosing signature")

        if not cand_sigs:
            return GateResult(passed=False, details="Gate 2 failed: Candidate code removed enclosing function declaration")

        orig_name, orig_params = orig_sigs[0]
        cand_name, cand_params = cand_sigs[0]

        if orig_name != cand_name:
            return GateResult(
                passed=False,
                details=f"Gate 2 failed: Function name changed from '{orig_name}' to '{cand_name}'",
            )

        if len(orig_params) != len(cand_params):
            return GateResult(
                passed=False,
                details=f"Gate 2 failed: Parameter count changed from {len(orig_params)} to {len(cand_params)}",
            )

        if orig_params != cand_params:
            return GateResult(
                passed=False,
                details=f"Gate 2 failed: Parameter names changed from {orig_params} to {cand_params}",
            )

        return GateResult(
            passed=True,
            details=f"Gate 2 passed: Function interface '{orig_name}({', '.join(orig_params)})' preserved identically",
        )

    def verify_gate_3_taint_neutralized(
        self, original_code: str, candidate_code: str, language: str
    ) -> GateResult:
        """Gate 3: Taint sink neutralization check (interpolation/concatenation removed, parameterization applied)."""
        # 1. Direct concatenation / interpolation check
        has_fstring_sql = bool(re.search(r"execute\(\s*f[\"'].*\{", candidate_code))
        has_template_sql = bool(re.search(r"query\(\s*`.*?\$\{", candidate_code))
        has_percent_sql = bool(re.search(r"execute\(\s*[\"'].*?%s[\"']\s*%", candidate_code))

        # Check for + concatenation within SQL sink invocation
        has_concat_sql = bool(re.search(r"(execute|executemany|query|raw|rawQuery)\([^)]*\+", candidate_code))

        if has_fstring_sql or has_template_sql or has_percent_sql or has_concat_sql:
            reason = "Unsanitized string concatenation (+) in SQL sink" if has_concat_sql else "Unsanitized string interpolation or % format in SQL sink"
            return GateResult(
                passed=False,
                details=f"Gate 3 failed: {reason}",
            )

        # 2. Confirm parameterized query was introduced
        has_parameterization = bool(
            re.search(r"execute\(\s*[\"'].*?(\?|%s).*?[\"'],\s*\(", candidate_code)
            or re.search(r"query\(\s*[\"'].*?(\$1|\?).*?[\"'],\s*\[", candidate_code)
            or ("replacements:" in candidate_code or "parameters:" in candidate_code)
            or re.search(r"execute\([^,]+,\s*(?:\([^\)]+\)|\[[^\]]+\]|[a-zA-Z0-9_]+,\))", candidate_code)
            or re.search(r"query\([^,]+,\s*\[[^\]]+\]", candidate_code)
            or ("$queryRaw`" in candidate_code)
        )

        if not has_parameterization:
            # Stricter fallback: ensure comma exists inside execute(...) or query(...) followed by an argument
            has_param_arg = bool(re.search(r"(?:execute|query)\([^,]+,\s*[^)]+\)", candidate_code))
            if has_param_arg:
                has_parameterization = True

        if not has_parameterization:
            return GateResult(
                passed=False,
                details="Gate 3 failed: Parameterized query placeholder or parameter container not detected",
            )

        return GateResult(
            passed=True,
            details="Gate 3 passed: Direct SQL string concatenation successfully replaced with parameterized binding",
        )

    def verify_gate_4_maintainability(
        self, original_code: str, candidate_code: str, language: str
    ) -> Tuple[GateResult, int]:
        """Gate 4: Maintainability non-regression check (delta CC <= 0)."""
        m_orig = self.maintainability_engine.analyze_code(original_code, language)
        m_cand = self.maintainability_engine.analyze_code(candidate_code, language)

        delta_cc = m_cand.cyclomatic_complexity - m_orig.cyclomatic_complexity

        if delta_cc > 0:
            return (
                GateResult(
                    passed=False,
                    details=f"Gate 4 failed: Cyclomatic Complexity increased by {delta_cc} (regression)",
                ),
                delta_cc,
            )

        return (
            GateResult(
                passed=True,
                details=f"Gate 4 passed: Cyclomatic Complexity non-regression verified (delta CC = {delta_cc})",
            ),
            delta_cc,
        )

    def verify_gate_6_sast_rescan(self, candidate_code: str, language: str) -> GateResult:
        """Gate 6: SAST re-scan check (zero new flaws, taint path eliminated)."""
        findings = self.taint_walker.analyze_code(
            code=candidate_code,
            language=language,
            file_path="candidate_rescan.py",
        )

        active_flaws = [f for f in findings if not f.sanitized]
        if active_flaws:
            return GateResult(
                passed=False,
                details=f"Gate 6 failed: SAST re-scan identified {len(active_flaws)} unsanitized taint path(s)",
            )

        return GateResult(
            passed=True,
            details="Gate 6 passed: SAST re-scan clean (zero new flaws, all taint paths neutralized)",
        )

    def verify_patch(
        self,
        original_code: str,
        patched_code: str,
        language: str = "python",
    ) -> GateVerificationResult:
        """
        Evaluate candidate patch across all gates according to PROJECT.md § 4.
        Returns complete GateVerificationResult with is_100_percent_verified.
        """
        g1 = self.verify_gate_1_syntax(patched_code, language)
        g2 = self.verify_gate_2_interface(original_code, patched_code, language)
        g3 = self.verify_gate_3_taint_neutralized(original_code, patched_code, language)
        g4, delta_cc = self.verify_gate_4_maintainability(original_code, patched_code, language)
        g6 = self.verify_gate_6_sast_rescan(patched_code, language)

        passed_gates: List[str] = []
        if g1.passed:
            passed_gates.append("Gate 1")
        if g2.passed:
            passed_gates.append("Gate 2")
        if g3.passed:
            passed_gates.append("Gate 3")
        if g4.passed:
            passed_gates.append("Gate 4")
        if g6.passed:
            passed_gates.append("Gate 6")

        is_100 = bool(g1.passed and g2.passed and g3.passed and g4.passed and g6.passed)

        details = {
            "gate_1": g1.details,
            "gate_2": g2.details,
            "gate_3": g3.details,
            "gate_4": g4.details,
            "gate_6": g6.details,
        }

        return GateVerificationResult(
            gate_1_syntax=g1.passed,
            gate_2_interface=g2.passed,
            gate_3_neutralization=g3.passed,
            gate_4_maintainability=g4.passed,
            gate_6_sast_rescan=g6.passed,
            is_100_percent_verified=is_100,
            delta_cc=delta_cc,
            passed_gates=passed_gates,
            gate_details=details,
        )

    def verify_candidate(
        self,
        original_code: str,
        candidate_code: str,
        language: str,
        patch_id: str,
        filename: str = "target_file.py",
    ) -> Tuple[bool, Optional[VerifiedPatch]]:
        """
        Execute all gates. Retain only candidates that achieve 100% pass across all gates.
        """
        # Sequential check
        g1 = self.verify_gate_1_syntax(candidate_code, language)
        if not g1.passed:
            return False, None

        g2 = self.verify_gate_2_interface(original_code, candidate_code, language)
        if not g2.passed:
            return False, None

        g3 = self.verify_gate_3_taint_neutralized(original_code, candidate_code, language)
        if not g3.passed:
            return False, None

        g4, delta_cc = self.verify_gate_4_maintainability(original_code, candidate_code, language)
        if not g4.passed:
            return False, None

        g6 = self.verify_gate_6_sast_rescan(candidate_code, language)
        if not g6.passed:
            return False, None

        # Build clean unified diff
        orig_lines = [l + "\n" for l in original_code.splitlines()] if original_code else []
        cand_lines = [l + "\n" for l in candidate_code.splitlines()] if candidate_code else []
        diff_lines = list(
            difflib.unified_diff(
                orig_lines,
                cand_lines,
                fromfile=f"a/{filename}",
                tofile=f"b/{filename}",
            )
        )
        diff_str = "".join(diff_lines)

        verified = VerifiedPatch(
            patch_id=patch_id,
            diff=diff_str,
            remediated_code=candidate_code,
            passed_gates=["Gate 1", "Gate 2", "Gate 3", "Gate 4", "Gate 6"],
            delta_cc=delta_cc,
            explanation=(
                f"100% verified patch ({patch_id}): CST syntax is valid, interface preserved, "
                f"taint sink neutralized via parameterized query, delta CC={delta_cc}, zero SAST flaws."
            ),
            gate1_syntax=g1,
            gate2_interface=g2,
            gate3_taint_neutralized=g3,
            gate4_maintainability=g4,
            gate6_sast_rescan=g6,
        )
        return True, verified
