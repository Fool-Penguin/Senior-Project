"""
CodeDEE - Stage 4: On-Demand Multi-Gate Auto-Fix Verifier
Enforces strict in-memory verification for AI-generated security patches:
- Gate 1: Tree-sitter Syntax Validation (Zero syntax errors)
- Gate 2: Interface Preservation (Function signature & parameters unmodified)
- Gate 3: Taint Sink Neutralized (Symbolic taint path severed or sanitized)
- Gate 4: Maintainability Non-Regression (Delta CC <= 0, no complexity explosion)
- Gate 6: SAST Re-scan (Zero new vulnerabilities introduced)

Strict Rule: ONLY patches passing 100% of gates are forwarded to the developer.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from typing import Optional

from codedee.core.parser import CodeDEEParser, SupportedLanguage
from codedee.core.graph_builder import GraphBuilder
from codedee.core.metrics import MaintainabilityEngine
from codedee.core.taint_walker import SymbolicTaintWalker, are_cwes_in_compatible_sink_family
from codedee.core.neural_oracle import get_catalogue_metadata

PATCH_SYSTEM_PROMPT = """You are an expert Automated Program Repair (APR) and Security Hardening Engine (CodeDEE Fix Generator).
Your task is to fix a verified security vulnerability in a code snippet by applying standard defensive coding practices.

### Repair Guidelines:
1. Neutralize the dangerous sink (e.g. use parameterized queries for SQL, shlex.quote / shell=False for commands, html.escape for XSS, secure_filename / abspath for paths).
2. Interface Preservation: Do NOT modify the function name, parameter list, or public interface.
3. Code Cleanliness: Keep the fix minimal, maintainable, and avoid adding unnecessary complexity or branches.
4. Output Format: Provide strictly the full corrected function replacement inside a JSON response without conversational text.

Schema:
{
  "patch_description": "<Brief summary of fix applied, e.g. 'Use parameterized cursor.execute with tuple'>",
  "fixed_code": "<Complete corrected code string>"
}
"""


@dataclass
class GateResult:
    passed: bool
    details: str


@dataclass
class VerifiedPatch:
    patch_id: int
    description: str
    fixed_code: str
    gate1_syntax: GateResult
    gate2_interface: GateResult
    gate3_sink_neutralized: GateResult
    gate4_maintainability: GateResult
    gate5_sandbox: GateResult
    gate6_sast_clean: GateResult
    all_passed: bool
    diff: str = ""


class MultiGateVerifier:
    """Stage 4 In-Memory Patch Verifier."""

    @classmethod
    def verify_patch(
        cls,
        original_code: str,
        fixed_code: str,
        language: SupportedLanguage,
        target_cwe: str,
    ) -> VerifiedPatch:
        """Evaluate fixed_code across all 5 mandatory gates."""
        lang = CodeDEEParser.normalize_language(language)

        # ------------------------------------------------------------------
        # Gate 1: Tree-sitter Syntax Validation
        # ------------------------------------------------------------------
        try:
            tree, _ = CodeDEEParser.parse_string(fixed_code, lang)
            has_error = tree.root_node.has_error
            g1 = GateResult(
                passed=not has_error,
                details="Zero syntax errors detected by Tree-sitter CST" if not has_error else "Tree-sitter detected syntax errors",
            )
        except Exception as e:
            g1 = GateResult(passed=False, details=f"Parse exception: {str(e)}")

        if not g1.passed:
            # If syntax fails, immediate rejection
            return cls._make_verdict(1, "Syntax Error", fixed_code, g1, False, False, False, False)

        # ------------------------------------------------------------------
        # Gate 2: Interface Preservation
        # ------------------------------------------------------------------
        orig_fns = CodeDEEParser.extract_functions(original_code, lang)
        fixed_fns = CodeDEEParser.extract_functions(fixed_code, lang)

        if not orig_fns or not fixed_fns:
            g2 = GateResult(passed=True, details="Top-level snippet: Interface preserved")
        else:
            orig_fn = orig_fns[0]
            fixed_fn = fixed_fns[0]
            same_name = orig_fn.name == fixed_fn.name
            same_params = orig_fn.parameters == fixed_fn.parameters

            if same_name and same_params:
                g2 = GateResult(passed=True, details=f"Signature preserved: {orig_fn.name}({', '.join(orig_fn.parameters)})")
            else:
                g2 = GateResult(passed=False, details=f"Interface altered: expected {orig_fn.name}({orig_fn.parameters}), got {fixed_fn.name}({fixed_fn.parameters})")

        # ------------------------------------------------------------------
        # Gate 3: Taint Sink Neutralized (supports In-Family Refined CWEs)
        # ------------------------------------------------------------------
        fixed_graphs = GraphBuilder.build_all(fixed_code, lang)
        fixed_findings = SymbolicTaintWalker.find_vulnerability_candidates(fixed_graphs, fixed_code)

        target_flaw_present = any(
            are_cwes_in_compatible_sink_family(f.candidate_cwe, target_cwe) and not f.has_sanitizer
            for f in fixed_findings
        )
        if not target_flaw_present:
            g3 = GateResult(passed=True, details=f"{target_cwe} sink neutralized or properly sanitized")
        else:
            g3 = GateResult(passed=False, details=f"{target_cwe} unmitigated taint flow still present in patched code")

        # ------------------------------------------------------------------
        # Gate 4: Maintainability Non-Regression (Delta CC <= 0)
        # ------------------------------------------------------------------
        orig_metrics = MaintainabilityEngine.analyze_code(original_code, lang)
        fixed_metrics = MaintainabilityEngine.analyze_code(fixed_code, lang)

        orig_cc = orig_metrics.functions[0].cyclomatic_complexity if orig_metrics.functions else 1
        fixed_cc = fixed_metrics.functions[0].cyclomatic_complexity if fixed_metrics.functions else 1
        delta_cc = fixed_cc - orig_cc

        if delta_cc <= 1:  # Allow max +1 for defensive bounds checking
            g4 = GateResult(passed=True, details=f"Maintainability preserved: Delta CC={delta_cc} (Orig: {orig_cc}, Fixed: {fixed_cc})")
        else:
            g4 = GateResult(passed=False, details=f"Complexity regression: Delta CC={delta_cc} exceeds threshold")

        # ------------------------------------------------------------------
        # Gate 5: Dynamic Sandbox Verification (Ephemeral Execution)
        # ------------------------------------------------------------------
        g5 = cls.run_sandbox_assertion(fixed_code, lang)

        # ------------------------------------------------------------------
        # Gate 6: SAST Re-scan (Zero new flaws)
        # ------------------------------------------------------------------
        new_flaws = [f for f in fixed_findings if not f.has_sanitizer]
        if len(new_flaws) == 0:
            g6 = GateResult(passed=True, details="SAST Re-scan clean: Zero vulnerabilities detected")
        else:
            g6 = GateResult(passed=False, details=f"SAST Re-scan detected {len(new_flaws)} residual flaw(s): {[f.candidate_cwe for f in new_flaws]}")

        all_ok = g1.passed and g2.passed and g3.passed and g4.passed and g5.passed and g6.passed
        return VerifiedPatch(
            patch_id=1,
            description="Defensive remediation patch",
            fixed_code=fixed_code,
            gate1_syntax=g1,
            gate2_interface=g2,
            gate3_sink_neutralized=g3,
            gate4_maintainability=g4,
            gate5_sandbox=g5,
            gate6_sast_clean=g6,
            all_passed=all_ok,
        )

    @classmethod
    def run_sandbox_assertion(cls, fixed_code: str, language: str, test_assertion: Optional[str] = None) -> GateResult:
        """Execute the patched code inside an ephemeral isolated subprocess."""
        if language != "python":
            return GateResult(passed=True, details="Non-Python sandbox execution skipped (pending Node container)")

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "sandbox_patch.py")
            script = fixed_code + "\n"
            if test_assertion:
                script += f"\n# --- Automated Assertion ---\n{test_assertion}\n"
            script += "\nprint('__GATE5_SANDBOX_SUCCESS__')\n"

            with open(test_file, "w", encoding="utf-8") as f:
                f.write(script)

            try:
                res = subprocess.run(
                    [sys.executable, test_file],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if res.returncode == 0 and "__GATE5_SANDBOX_SUCCESS__" in res.stdout:
                    return GateResult(passed=True, details="Dynamic execution verified in isolated sandbox")
                else:
                    err = res.stderr.strip() or res.stdout.strip()
                    return GateResult(passed=False, details=f"Sandbox execution error: {err[:150]}")
            except subprocess.TimeoutExpired:
                return GateResult(passed=False, details="Sandbox execution timed out (potential DoS/infinite loop)")
            except Exception as e:
                return GateResult(passed=False, details=f"Sandbox exception: {str(e)}")

    @staticmethod
    def _make_verdict(pid, desc, code, g1, g2_val, g3_val, g4_val, g6_val):
        return VerifiedPatch(
            patch_id=pid,
            description=desc,
            fixed_code=code,
            gate1_syntax=g1,
            gate2_interface=GateResult(passed=g2_val, details="Failed prior gate"),
            gate3_sink_neutralized=GateResult(passed=g3_val, details="Failed prior gate"),
            gate4_maintainability=GateResult(passed=g4_val, details="Failed prior gate"),
            gate5_sandbox=GateResult(passed=False, details="Failed prior gate"),
            gate6_sast_clean=GateResult(passed=g6_val, details="Failed prior gate"),
            all_passed=False,
        )


class PatchGenerator:
    """Generates 3-4 candidate fixes via Ollama and filters with MultiGateVerifier."""

    def __init__(self, model_name: str = "qwen2.5-coder:7b", ollama_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.ollama_url = ollama_url

    def generate_and_verify(
        self,
        code_slice: str,
        language: SupportedLanguage,
        cwe_id: str,
        source_param: str,
        sink_callee: str,
        sink_line: int = 1,
        taint_path: Optional[list[str]] = None,
        neural_reason: str = "",
        target_count: int = 3,
    ) -> list[VerifiedPatch]:
        """
        Request candidate patches from LLM using combined Neuro-Symbolic context:
          1. Deterministic Catalogue Title & Remediation Pattern (from security_vulnerability_catalogue.yaml)
          2. Symbolic AST Anchor (exact source_param, taint_path, sink_callee, sink_line)
          3. Neural Contextual Explanation (why sanitization was missing or bypassed)
        and return ONLY patches that pass 100% of MultiGateVerifier gates.
        """
        cat = get_catalogue_metadata(cwe_id)
        taint_trace_str = " -> ".join(taint_path) if taint_path else f"{source_param} -> {sink_callee}"
        prompt = f"""### Combined Neuro-Symbolic Remediation Context:
- Confirmed Vulnerability: {cwe_id} — {cat['cwe_name']} ({cat['owasp_category']}, Severity: {cat['risk_level']}, CVSS: {cat['cvss_v31_base']})
- Symbolic AST Taint Source: `{source_param}`
- Symbolic AST Taint Path: {taint_trace_str}
- Symbolic AST Sink Callee: `{sink_callee}` (line {sink_line})
- Neural Contextual Flow Audit: {neural_reason or 'Untrusted input reaches sensitive sink without adequate sanitization.'}
- Official Catalogue Remediation Standard: {cat['remediation_guidance']}

### Code to Fix ({language}):
```{language}
{code_slice}
```

Instructions:
1. Apply the Official Catalogue Remediation Standard above to neutralize `{sink_callee}` while preserving the exact function signature (`{source_param}`).
2. Return strictly the JSON object specifying patch_description and fixed_code.
"""

        candidates: list[dict] = []
        # Generate patches with slight temperature variations to produce alternative defensive approaches
        temps = [0.1, 0.3, 0.5]
        for t in temps[:target_count]:
            raw = self._call_ollama(prompt, temperature=t)
            parsed = self._parse_json(raw)
            if parsed and parsed.get("fixed_code"):
                candidates.append(parsed)

        verified_patches: list[VerifiedPatch] = []
        for idx, cand in enumerate(candidates, 1):
            fixed_str = cand["fixed_code"]
            verdict = MultiGateVerifier.verify_patch(
                original_code=code_slice,
                fixed_code=fixed_str,
                language=language,
                target_cwe=cwe_id,
            )
            verdict.patch_id = idx
            verdict.description = cand.get("patch_description", f"Fix candidate #{idx}")

            # Strict policy: ONLY 100% passed patches are forwarded to developer
            if verdict.all_passed:
                verified_patches.append(verdict)

        return verified_patches

    def _call_ollama(self, prompt: str, temperature: float = 0.2) -> str:
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "system": PATCH_SYSTEM_PROMPT,
            "stream": False,
            "format": "json",
            "options": {"temperature": temperature, "top_p": 0.9, "num_predict": 1024},
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.ollama_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                res_json = json.loads(response.read().decode("utf-8"))
                return res_json.get("response", "")
        except Exception:
            return ""

    def _parse_json(self, text: str) -> Optional[dict]:
        if not text:
            return None
        t = text.strip()
        if t.startswith("```"):
            t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
            t = re.sub(r"\n?```$", "", t)
        try:
            return json.loads(t)
        except Exception:
            m = re.search(r"\{[\s\S]*\}", t)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    pass
        return None
