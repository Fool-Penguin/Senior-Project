"""
CodeBLEU Evaluator for CodeDEE Benchmark Pipeline
Reference: Ren et al., 2020: "CodeBLEU: a Method for Automatic Evaluation of Code Synthesis"
Calculates:
  1. BLEU-4 score (n-gram precision with brevity penalty)
  2. Weighted BLEU (syntax-weighted n-grams)
  3. AST Match score (tree-sitter syntactic node similarity)
  4. Data-flow Match score (variable def-use sequence match)
Final CodeBLEU = 0.25 * BLEU + 0.25 * Weighted_BLEU + 0.25 * AST_Match + 0.25 * Dataflow_Match
"""

import ast
import math
import re
from collections import Counter
from typing import List, Dict, Set, Tuple


PYTHON_KEYWORDS = {
    "def", "return", "import", "from", "as", "if", "elif", "else",
    "for", "while", "try", "except", "finally", "with", "class",
    "lambda", "yield", "raise", "assert", "break", "continue",
    "pass", "True", "False", "None", "and", "or", "not", "is", "in"
}


def tokenize_code(code: str) -> List[str]:
    """Tokenizes code into programming language tokens."""
    # Split by operators, punctuation, whitespace while preserving identifiers
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|==|!=|<=|>=|\+=|-=|\*=|/=|->|[^\s\w]", code)
    return [t for t in tokens if t.strip()]


def compute_ngram_counts(tokens: List[str], n: int) -> Counter:
    """Returns counts of n-grams."""
    return Counter(tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1))


def compute_bleu(ref_tokens: List[str], hyp_tokens: List[str], max_n: int = 4) -> float:
    """Standard BLEU score calculation with brevity penalty."""
    if not hyp_tokens:
        return 0.0

    precisions = []
    for n in range(1, max_n + 1):
        hyp_ngrams = compute_ngram_counts(hyp_tokens, n)
        ref_ngrams = compute_ngram_counts(ref_tokens, n)

        if not hyp_ngrams:
            precisions.append(0.0)
            continue

        clipped_overlap = sum(min(count, ref_ngrams[ngram]) for ngram, count in hyp_ngrams.items())
        total_hyp = sum(hyp_ngrams.values())
        precisions.append(clipped_overlap / total_hyp if total_hyp > 0 else 0.0)

    # Brevity penalty
    c = len(hyp_tokens)
    r = len(ref_tokens)
    if c == 0:
        return 0.0
    bp = 1.0 if c > r else math.exp(1 - r / c)

    # Geometric mean of precisions
    log_sum = 0.0
    valid_n = 0
    for p in precisions:
        if p > 0:
            log_sum += math.log(p)
            valid_n += 1
        else:
            log_sum += math.log(1e-5)
            valid_n += 1

    geo_mean = math.exp(log_sum / valid_n)
    return bp * geo_mean


def compute_weighted_bleu(ref_tokens: List[str], hyp_tokens: List[str], max_n: int = 4) -> float:
    """Syntax-weighted BLEU score where keywords have 2x weight."""
    if not hyp_tokens:
        return 0.0

    def token_weight(tok: str) -> float:
        return 2.0 if tok in PYTHON_KEYWORDS else 1.0

    precisions = []
    for n in range(1, max_n + 1):
        hyp_ngrams = compute_ngram_counts(hyp_tokens, n)
        ref_ngrams = compute_ngram_counts(ref_tokens, n)

        if not hyp_ngrams:
            precisions.append(0.0)
            continue

        weighted_overlap = 0.0
        weighted_total = 0.0
        for ngram, count in hyp_ngrams.items():
            overlap = min(count, ref_ngrams[ngram])
            w = sum(token_weight(t) for t in ngram) / len(ngram)
            weighted_overlap += overlap * w
            weighted_total += count * w

        precisions.append(weighted_overlap / weighted_total if weighted_total > 0 else 0.0)

    c = len(hyp_tokens)
    r = len(ref_tokens)
    bp = 1.0 if c > r else math.exp(1 - r / c)

    log_sum = 0.0
    for p in precisions:
        log_sum += math.log(p if p > 0 else 1e-5)
    return bp * math.exp(log_sum / max_n)


def get_ast_node_types(code: str) -> List[str]:
    """Extracts hierarchical AST node types from Python code."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    return [type(node).__name__ for node in ast.walk(tree)]


def compute_ast_match(ref_code: str, hyp_code: str) -> float:
    """Computes syntactic AST node structure similarity."""
    ref_nodes = get_ast_node_types(ref_code)
    hyp_nodes = get_ast_node_types(hyp_code)

    if not ref_nodes or not hyp_nodes:
        return 0.0

    ref_counts = Counter(ref_nodes)
    hyp_counts = Counter(hyp_nodes)

    overlap = sum(min(count, ref_counts[ntype]) for ntype, count in hyp_counts.items())
    total = sum(hyp_counts.values())
    return overlap / total if total > 0 else 0.0


def get_dataflow_vars(code: str) -> Set[Tuple[str, str]]:
    """Extracts variable def-use and access patterns."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()

    pairs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            ctx_name = type(node.ctx).__name__
            pairs.add((node.id, ctx_name))
        elif isinstance(node, ast.Attribute):
            pairs.add((node.attr, "Attribute"))
    return pairs


def compute_dataflow_match(ref_code: str, hyp_code: str) -> float:
    """Computes variable and dataflow similarity."""
    ref_df = get_dataflow_vars(ref_code)
    hyp_df = get_dataflow_vars(hyp_code)

    if not ref_df or not hyp_df:
        return 0.5  # Neutral fallback if simple function has minimal variables

    intersection = ref_df.intersection(hyp_df)
    union = ref_df.union(hyp_df)
    return len(intersection) / len(union) if union else 0.0


def calculate_codebleu(reference_code: str, candidate_code: str) -> Dict[str, float]:
    """
    Computes overall CodeBLEU score and individual components:
      - ngram_bleu
      - weighted_bleu
      - ast_match
      - dataflow_match
      - codebleu (final composite 0.0 to 100.0)
    """
    ref_tokens = tokenize_code(reference_code)
    hyp_tokens = tokenize_code(candidate_code)

    bleu = compute_bleu(ref_tokens, hyp_tokens)
    w_bleu = compute_weighted_bleu(ref_tokens, hyp_tokens)
    ast_match = compute_ast_match(reference_code, candidate_code)
    df_match = compute_dataflow_match(reference_code, candidate_code)

    composite = (0.25 * bleu + 0.25 * w_bleu + 0.25 * ast_match + 0.25 * df_match) * 100.0

    return {
        "ngram_bleu": round(bleu * 100.0, 2),
        "weighted_bleu": round(w_bleu * 100.0, 2),
        "ast_match": round(ast_match * 100.0, 2),
        "dataflow_match": round(df_match * 100.0, 2),
        "codebleu": round(composite, 2)
    }
