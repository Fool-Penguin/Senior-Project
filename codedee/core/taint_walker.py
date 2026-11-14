"""
CodeDEE - Stage 3B: Symbolic Taint Walker Engine
Traverses the Data-Flow Graph (DFG) to trace tainted paths from untrusted sources to sensitive sinks
and maps potential vulnerabilities to the official 28 Taxonomy entries and their Sink Families.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional
import networkx as nx

from codedee.core.graph_builder import CodeGraphs
from codedee.core.parser import SupportedLanguage


# Canonical Sink Families grouping related CWEs that share overlapping syntactic AST sinks.
# During Neuro-Symbolic Reconciliation, the Neural Oracle is permitted to refine a Symbolic
# candidate_cwe ONLY within the same compatible Sink Family (e.g., CWE-89 -> CWE-943 for NoSQLi,
# or CWE-94 -> CWE-1336 for Template Injection). Out-of-family predictions are flagged as NEEDS_REVIEW.
SINK_FAMILIES: dict[str, set[str]] = {
    "DB_QUERY": {"CWE-89", "CWE-943", "CWE-1426"},
    "CMD_EXEC": {"CWE-78", "CWE-77", "CWE-1426"},
    "CODE_EVAL": {"CWE-94", "CWE-95", "CWE-1336", "CWE-502", "CWE-1426"},
    "WEB_TEMPLATE": {"CWE-79", "CWE-1336", "CWE-601"},
    "FILE_PATH": {"CWE-22", "CWE-200"},
    "NET_REDIRECT": {"CWE-918", "CWE-601"},
    "OBJ_ATTR": {"CWE-1321", "CWE-915"},
    "DESERIALIZE_XML": {"CWE-502", "CWE-611", "CWE-94"},
    "CRYPTO_SECRET": {"CWE-798", "CWE-327", "CWE-328", "CWE-338", "CWE-347"},
    "ACCESS_AUTH": {"CWE-862", "CWE-352", "CWE-347", "CWE-200"},
    "REGEX_DOS": {"CWE-1333"},
    "INFO_LEAK": {"CWE-200", "CWE-209", "CWE-798"},
    "LLM_AI": {"CWE-1427", "CWE-1426", "CWE-200"},
}


def get_sink_family(cwe_id: str) -> str:
    """Return the primary Sink Family for a given CWE ID."""
    cwe = (cwe_id or "").upper().strip()
    primary_map = {
        "CWE-89": "DB_QUERY",
        "CWE-943": "DB_QUERY",
        "CWE-78": "CMD_EXEC",
        "CWE-77": "CMD_EXEC",
        "CWE-94": "CODE_EVAL",
        "CWE-95": "CODE_EVAL",
        "CWE-1336": "WEB_TEMPLATE",
        "CWE-79": "WEB_TEMPLATE",
        "CWE-22": "FILE_PATH",
        "CWE-918": "NET_REDIRECT",
        "CWE-601": "NET_REDIRECT",
        "CWE-1321": "OBJ_ATTR",
        "CWE-915": "OBJ_ATTR",
        "CWE-502": "DESERIALIZE_XML",
        "CWE-611": "DESERIALIZE_XML",
        "CWE-798": "CRYPTO_SECRET",
        "CWE-327": "CRYPTO_SECRET",
        "CWE-328": "CRYPTO_SECRET",
        "CWE-338": "CRYPTO_SECRET",
        "CWE-347": "ACCESS_AUTH",
        "CWE-862": "ACCESS_AUTH",
        "CWE-352": "ACCESS_AUTH",
        "CWE-1333": "REGEX_DOS",
        "CWE-200": "INFO_LEAK",
        "CWE-209": "INFO_LEAK",
        "CWE-1427": "LLM_AI",
        "CWE-1426": "LLM_AI",
    }
    return primary_map.get(cwe, "OTHER")


def are_cwes_in_compatible_sink_family(symbolic_cwe: str, neural_cwe: str) -> bool:
    """
    Check whether neural_cwe belongs to the compatible Sink Family of symbolic_cwe.
    Returns True if exact match or if both share a compatible Sink Family.
    """
    s_cwe = (symbolic_cwe or "").upper().strip()
    n_cwe = (neural_cwe or "").upper().strip()
    if not s_cwe or not n_cwe:
        return False
    if s_cwe == n_cwe:
        return True
    for family_members in SINK_FAMILIES.values():
        if s_cwe in family_members and n_cwe in family_members:
            return True
    return False


@dataclass
class TaintFinding:
    """Represents a suspicious tainted flow candidate discovered by symbolic traversal."""
    function_name: str
    source_param: str
    sink_callee: str
    sink_line: int
    candidate_cwe: str
    owasp_category: str
    taint_path: list[str]
    has_sanitizer: bool
    sanitizer_detected: str = ""
    code_slice: str = ""
    sink_family: str = ""

    def __post_init__(self):
        if not self.sink_family:
            self.sink_family = get_sink_family(self.candidate_cwe)


# Rules mapping sensitive sink callees to CWE candidates across Python, JS, and TS
SINK_RULES: list[dict] = [
    # CWE-89 / CWE-943: SQL & NoSQL Query Injection (DB_QUERY Family)
    {
        "pattern": r"(execute|executescript|cursor\.execute|session\.execute|query|raw_query|db\.query|sequelize\.query)",
        "cwe_id": "CWE-89",
        "sink_family": "DB_QUERY",
        "owasp": "A05:2025-Injection",
        "sanitizers": [r"int\(", r"float\(", r"\bparam\b", r"\?", r"%\w", r",\s*\("]
    },
    {
        "pattern": r"(\.find\b|\.findOne\b|\.aggregate\b|\$where)",
        "cwe_id": "CWE-943",
        "sink_family": "DB_QUERY",
        "owasp": "A05:2025-Injection",
        "sanitizers": [r"mongo_sanitize", r"String\(", r"str\("]
    },
    # CWE-78 / CWE-77: OS & Command Injection (CMD_EXEC Family)
    {
        "pattern": r"(subprocess\.(run|Popen|call|check_output)|os\.system|os\.popen|child_process\.(exec|execSync|spawn))",
        "cwe_id": "CWE-78",
        "sink_family": "CMD_EXEC",
        "owasp": "A05:2025-Injection",
        "sanitizers": [r"shlex\.quote", r"shell=False", r"execFile"]
    },
    # CWE-1336: Server-Side Template Injection (WEB_TEMPLATE Family)
    {
        "pattern": r"(jinja2\.Template|render_template_string|mako\.template\.Template|ejs\.render|nunjucks\.renderString|handlebars\.compile)",
        "cwe_id": "CWE-1336",
        "sink_family": "WEB_TEMPLATE",
        "owasp": "A05:2025-Injection",
        "sanitizers": [r"SandboxedEnvironment", r"render_template\("]
    },
    # CWE-79: Cross-Site Scripting (XSS) (WEB_TEMPLATE Family)
    {
        "pattern": r"(res\.send|response\.write|innerHTML|outerHTML|document\.write|Markup|mark_safe)",
        "cwe_id": "CWE-79",
        "sink_family": "WEB_TEMPLATE",
        "owasp": "A05:2025-Injection",
        "sanitizers": [r"escape\(", r"html\.escape", r"DOMPurify\.sanitize", r"encodeURIComponent"]
    },
    # CWE-22: Path Traversal (FILE_PATH Family)
    {
        "pattern": r"(open|send_file|send_from_directory|fs\.readFile|fs\.readFileSync|fs\.createReadStream|path\.join|shutil\.copy)",
        "cwe_id": "CWE-22",
        "sink_family": "FILE_PATH",
        "owasp": "A01:2025-Broken Access Control",
        "sanitizers": [r"os\.path\.abspath", r"os\.path\.commonpath", r"secure_filename", r"path\.normalize", r"path\.resolve"]
    },
    # CWE-94 / CWE-95: Code / Eval Injection (CODE_EVAL Family)
    {
        "pattern": r"(eval|exec|Function|vm\.runInContext|vm\.runInNewContext|compile)",
        "cwe_id": "CWE-94",
        "sink_family": "CODE_EVAL",
        "owasp": "A05:2025-Injection",
        "sanitizers": [r"ast\.literal_eval", r"JSON\.parse"]
    },
    # CWE-502 / CWE-611: Deserialization & XXE (DESERIALIZE_XML Family)
    {
        "pattern": r"(pickle\.loads|_pickle\.loads|yaml\.load|yaml\.unsafe_load|unserialize|marshal\.loads)",
        "cwe_id": "CWE-502",
        "sink_family": "DESERIALIZE_XML",
        "owasp": "A08:2025-Software or Data Integrity Failures",
        "sanitizers": [r"yaml\.safe_load", r"json\.loads"]
    },
    {
        "pattern": r"(ElementTree\.fromstring|lxml\.etree\.fromstring|minidom\.parseString|parseXml|parseFromString)",
        "cwe_id": "CWE-611",
        "sink_family": "DESERIALIZE_XML",
        "owasp": "A02:2025-Security Misconfiguration",
        "sanitizers": [r"defusedxml", r"resolve_entities\s*=\s*False", r"noent\s*:\s*false"]
    },
    # CWE-918 / CWE-601: SSRF & Open Redirect (NET_REDIRECT Family)
    {
        "pattern": r"(requests\.(get|post|request)|urllib\.request\.urlopen|httpx\.(get|post)|fetch|axios\.(get|post)|http\.get)",
        "cwe_id": "CWE-918",
        "sink_family": "NET_REDIRECT",
        "owasp": "A01:2025-Broken Access Control",
        "sanitizers": [r"urlparse", r"whitelist_domains", r"is_private"]
    },
    {
        "pattern": r"(redirect|res\.redirect|HttpResponseRedirect|window\.location)",
        "cwe_id": "CWE-601",
        "sink_family": "NET_REDIRECT",
        "owasp": "A01:2025-Broken Access Control",
        "sanitizers": [r"urlparse", r"ALLOWED_DOMAINS"]
    },
    # CWE-1321 / CWE-915: Prototype Pollution & Mass Assignment (OBJ_ATTR Family)
    {
        "pattern": r"(setattr|Object\.assign|lodash\.merge|defaultsDeep|extend)",
        "cwe_id": "CWE-1321",
        "sink_family": "OBJ_ATTR",
        "owasp": "A08:2025-Software or Data Integrity Failures",
        "sanitizers": [r"__proto__", r"__class__", r"hasOwn", r"extra\s*=\s*['\"]forbid['\"]"]
    },
    # CWE-1333: ReDoS (REGEX_DOS Family)
    {
        "pattern": r"(re\.compile|re\.match|re\.search|RegExp)",
        "cwe_id": "CWE-1333",
        "sink_family": "REGEX_DOS",
        "owasp": "A02:2025-Security Misconfiguration",
        "sanitizers": [r"re2", r"escape"]
    },
    # CWE-1427 / CWE-1426: LLM Prompt Injection & Output Handling (LLM_AI Family)
    {
        "pattern": r"(chat\.completions\.create|llm\.invoke|generateText)",
        "cwe_id": "CWE-1427",
        "sink_family": "LLM_AI",
        "owasp": "LLM01:2025-Prompt Injection",
        "sanitizers": [r"response_format", r"Pydantic", r"Zod"]
    },
]


class SymbolicTaintWalker:
    """Stage 3B In-Memory DFG Taint Path Walker."""

    @classmethod
    def find_vulnerability_candidates(
        cls,
        graphs: CodeGraphs,
        full_code: str,
    ) -> list[TaintFinding]:
        """
        Traverse the DFG from param_source nodes to call_sink nodes.
        Returns candidate vulnerability findings mapped to CWE taxonomy.
        """
        findings: list[TaintFinding] = []
        dfg = graphs.dfg

        # Find all sources and sinks
        source_nodes = [n for n, d in dfg.nodes(data=True) if d.get("kind") == "param_source"]
        sink_nodes = [n for n, d in dfg.nodes(data=True) if d.get("kind") == "call_sink"]

        for src in source_nodes:
            src_data = dfg.nodes[src]
            fn_name = src_data.get("function", "")
            param_name = src_data.get("var", "")

            # Target matching function entity for slicing
            fn_entity = next((f for f in graphs.functions if f.name == fn_name), None)
            code_slice = fn_entity.code if fn_entity else full_code

            for sink in sink_nodes:
                sink_data = dfg.nodes[sink]
                if sink_data.get("function", fn_name) != fn_name:
                    continue  # Intra-procedural scope

                # Check if a directed data flow path exists from Source to Sink
                if nx.has_path(dfg, src, sink):
                    paths = list(nx.all_simple_paths(dfg, src, sink))
                    if not paths:
                        continue
                    
                    shortest_path = paths[0]
                    callee = sink_data.get("callee", "")
                    sink_line = sink_data.get("line", 1)

                    # Match with SINK_RULES
                    for rule in SINK_RULES:
                        if re.search(rule["pattern"], callee, re.IGNORECASE):
                            # Check for sanitizers along the path or code slice
                            has_sanitizer = False
                            detected_san = ""
                            for s_regex in rule.get("sanitizers", []):
                                if re.search(s_regex, code_slice):
                                    has_sanitizer = True
                                    detected_san = s_regex
                                    break

                            finding = TaintFinding(
                                function_name=fn_name,
                                source_param=param_name,
                                sink_callee=callee,
                                sink_line=sink_line,
                                candidate_cwe=rule["cwe_id"],
                                owasp_category=rule["owasp"],
                                taint_path=shortest_path,
                                has_sanitizer=has_sanitizer,
                                sanitizer_detected=detected_san,
                                code_slice=code_slice,
                                sink_family=rule.get("sink_family", get_sink_family(rule["cwe_id"])),
                            )
                            findings.append(finding)
                            break  # Avoid double-counting same sink

        return findings
