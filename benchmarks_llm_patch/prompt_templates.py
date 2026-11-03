"""
Prompt Generation Engine for Component C7 (Patch Synthesizer)
Integrates Program Slicing (C6) and Multi-Style Patch Generation:
  1. Minimal Fix: Surgical patch changing only the vulnerable line/sink.
  2. Refactor Fix: Enhanced defense-in-depth with input validation and guard clauses.
  3. Idiomatic Fix: Framework-recommended safe paradigm.
"""

from typing import Dict, Any

SYSTEM_PROMPT = (
    "You are CodeDEE's Automated Security Program Repair (APR) engine.\n"
    "Your task is to fix a security vulnerability in the provided source code.\n\n"
    "STRICT RULES:\n"
    "1. Preserve the exact function signature (name, parameter names, and return type).\n"
    "2. Neutralize the taint path completely (break the vulnerable sink).\n"
    "3. Do NOT break existing functional behavior.\n"
    "4. Keep the code clean and maintainable. Avoid unnecessary nesting.\n"
    "5. Return ONLY the remediated function code inside a single ```python ... ``` markdown block.\n"
    "6. Do NOT include introductory or concluding conversational prose.\n"
)

def build_patch_prompt(test_case: Dict[str, Any], fix_style: str = "minimal") -> str:
    """Builds a structured C7 repair prompt enforcing specific repair styles."""
    style_guidelines = {
        "minimal": "Apply a surgical, minimal patch directly neutralizing the vulnerable sink with as few line changes as possible.",
        "refactor": "Apply defense-in-depth: validate input first using guard clauses, then execute safely, keeping cognitive complexity low.",
        "idiomatic": "Use standard python modern library idioms (e.g., parameterized queries, shlex/list execution, safe serialization)."
    }
    guideline = style_guidelines.get(fix_style, style_guidelines["minimal"])

    user_prompt = (
        f"Target Vulnerability: {test_case['cwe_id']} - {test_case['cwe_name']}\n"
        f"OWASP Category: {test_case['owasp']}\n"
        f"Vulnerable Sink: {test_case['taint_sink']}\n"
        f"Taint Source: {test_case['taint_source']}\n"
        f"Repair Style Required: {fix_style.upper()} ({guideline})\n\n"
        f"Vulnerable Function Code:\n"
        f"```{test_case.get('language', 'python')}\n"
        f"{test_case['code']}\n"
        f"```\n\n"
        f"Provide the fixed, safe Python function:"
    )
    return user_prompt
