"""
CodeDEE - Core End-to-End Pipeline
Coordinates Stage 1 (Parser), Stage 2 (Graphs), Stage 3A (Metrics), and Stage 3B (Taint Walker + Oracle)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from codedee.core.parser import CodeDEEParser, SupportedLanguage
from codedee.core.graph_builder import GraphBuilder, CodeGraphs
from codedee.core.metrics import MaintainabilityEngine, FileMetrics
from codedee.core.taint_walker import SymbolicTaintWalker, TaintFinding
from codedee.core.neural_oracle import NeuralOracle, VerifiedVulnerability, get_catalogue_metadata
from codedee.core.symbol_resolver import ProjectSymbolResolver
from codedee.core.interprocedural_cg import InterproceduralCallGraph, InterproceduralTaintContext


@dataclass
class SecurityAuditReport:
    """Consolidated audit report for a source file ready for VS Code Extension UI."""
    language: SupportedLanguage
    maintainability: FileMetrics
    vulnerabilities: list[VerifiedVulnerability]
    total_findings: int
    confirmed_count: int
    review_count: int


class CodeDEEPipeline:
    """Master Pipeline orchestrator for CodeDEE Analysis."""

    def __init__(
        self,
        oracle_model: str = "qwen2.5-coder:7b",
        enable_neural_oracle: bool = True,
        project_root: Optional[Path | str] = None,
    ):
        self.enable_neural_oracle = enable_neural_oracle
        self.oracle = NeuralOracle(model_name=oracle_model) if enable_neural_oracle else None
        self.project_root = Path(project_root).resolve() if project_root else None
        
        # Inter-procedural Call Graph & Symbol Resolver (Semester 2 Engine)
        self.resolver: Optional[ProjectSymbolResolver] = None
        self.call_graph: Optional[InterproceduralCallGraph] = None
        if self.project_root and self.project_root.exists():
            self.resolver = ProjectSymbolResolver(self.project_root)
            self.resolver.index_project()
            self.call_graph = InterproceduralCallGraph(self.resolver)
            self.call_graph.build_project_graph()

    def analyze(self, code: str, language: str, file_rel_path: Optional[str] = None) -> SecurityAuditReport:
        """Run full 4-stage pipeline analysis on given code."""
        lang = CodeDEEParser.normalize_language(language)

        # Stage 1 & 2: Parser + Intermediate Graphs
        graphs = GraphBuilder.build_all(code, lang)

        # Stage 3A: Maintainability Metrics (8 Metrics under ISO 25010)
        metrics = MaintainabilityEngine.analyze_code(code, lang)

        # Stage 3B: Symbolic Taint Walker
        symbolic_findings = SymbolicTaintWalker.find_vulnerability_candidates(graphs, code)

        # Stage 3B: Neural Oracle Verification (if enabled)
        verified_vulns: list[VerifiedVulnerability] = []
        if self.enable_neural_oracle and self.oracle:
            for sf in symbolic_findings:
                verified = self.oracle.verify_finding(sf, lang)
                verified_vulns.append(verified)
        else:
            # Fallback to symbolic-only verification (with deterministic Catalogue metadata)
            for sf in symbolic_findings:
                status = "CONFIRMED" if not sf.has_sanitizer else "REJECTED"
                final_cwe = sf.candidate_cwe if status == "CONFIRMED" else "CWE-NONE"
                cat = get_catalogue_metadata(final_cwe)
                verified_vulns.append(
                    VerifiedVulnerability(
                        status=status,
                        cwe_id=final_cwe,
                        cwe_name=cat["cwe_name"],
                        risk_level=cat["risk_level"],
                        cvss_v31_base=cat["cvss_v31_base"],
                        owasp_category=cat["owasp_category"],
                        remediation_guidance=cat["remediation_guidance"],
                        function_name=sf.function_name,
                        source_param=sf.source_param,
                        sink_callee=sf.sink_callee,
                        sink_line=sf.sink_line,
                        reason=f"Tainted parameter '{sf.source_param}' reaches '{sf.sink_callee}'.",
                        code_slice=sf.code_slice,
                        taint_path=sf.taint_path,
                        symbolic_cwe=sf.candidate_cwe,
                        neural_cwe="SYMBOLIC_ONLY",
                        sink_family=sf.sink_family,
                        reconciliation_note="Evaluated in Symbolic-Only mode.",
                    )
                )

        confirmed = sum(1 for v in verified_vulns if v.status == "CONFIRMED")
        review = sum(1 for v in verified_vulns if v.status == "NEEDS_REVIEW")

        return SecurityAuditReport(
            language=lang,
            maintainability=metrics,
            vulnerabilities=verified_vulns,
            total_findings=len(verified_vulns),
            confirmed_count=confirmed,
            review_count=review,
        )
