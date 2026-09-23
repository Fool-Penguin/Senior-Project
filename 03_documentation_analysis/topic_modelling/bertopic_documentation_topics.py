#!/usr/bin/env python3
"""Discover documentation topics with BERTopic, using reusable embeddings.

Topics are fitted on a sample capped per repository and folder, then every
text is assigned to one; optionally, similar topics are merged into themes.

Examples (from the repository root; outputs default to the topic_modelling folder):
    # Validate the pipeline and tune parameters on a 5,000-record sample.
    python topic_modelling/bertopic_documentation_topics.py --test

    # Run the complete corpus, reusing embeddings from a previous run when possible.
    python topic_modelling/bertopic_documentation_topics.py --min-topic-size 100

    # Reproduce the published documentation_topics.csv (40 reviewed topics).
    # The topic ids and names file belong to this exact fit (seed 42, size 100).
    python topic_modelling/bertopic_documentation_topics.py --merge-topics 26,41 --drop-topics 35,36,41 \
        --topic-names topic_modelling/documentation_topic_names.json

The embedding cache is keyed by the input file, embedding model, text-preparation
settings, and selected document limit.  UMAP/HDBSCAN settings deliberately are
not part of that key, so they can be tuned without encoding the corpus again.
"""

from __future__ import annotations

import argparse
import collections
import csv
import functools
import hashlib
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


HERE = Path(__file__).resolve().parent  # outputs live here; the input stays at the repository root
CACHE_FORMAT_VERSION = 2
PREPROCESS_VERSION = 5
TOP_N_KEYWORDS = 10
OUTPUT_COLUMNS = (
    "Repository URL",
    "Repository name",
    "Doc file path",
    "Doc file name",
    "Doc type",
    "Topic id",
    "Topic name",
    "Topic description",
    "Keywords",
)
# Topic name and description written for each reason a row has no topic (id -1).
NO_CLEAR_TOPIC = "No clear topic"
UNASSIGNED = {
    "Not modeled: empty file": "The file has no content.",
    "Not modeled: excluded path or file type": (
        "Not documentation: vendored code, test fixtures, agent run logs, non-English translation folders, "
        "or a .txt file other than readme.txt / llms.txt."
    ),
    "Not modeled: non-English or no prose": (
        "The text is not English, or nothing readable remains after removing code, markup and links."
    ),
    NO_CLEAR_TOPIC: "English documentation that is not similar enough to any topic (cosine similarity below the threshold).",
}
SUBTOPIC_COLUMNS = ("Subtopic id", "Subtopic keywords")  # only with --nr-themes


@dataclass
class Document:
    """A valid JSON object from the input and its bounded modeling text."""

    record: dict[str, Any]
    text: str | None
    topic_id: int = -1
    subtopic_id: int = -1
    unassigned_reason: str = NO_CLEAR_TOPIC  # a key of UNASSIGNED


class Progress:
    """Small dependency-free progress reporter suitable for long batch jobs."""

    def __init__(self, label: str, total: int | None, interval: int = 1) -> None:
        self.label = label
        self.total = total
        self.interval = max(1, interval)
        self.start = time.perf_counter()

    def update(self, current: int, *, force: bool = False) -> None:
        if not force and current % self.interval:
            return
        elapsed = time.perf_counter() - self.start
        rate = current / elapsed if elapsed else 0.0
        total = f"/{self.total:,}" if self.total is not None else ""
        print(f"{self.label}: {current:,}{total} ({rate:.1f}/s, {elapsed:.1f}s)", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=HERE.parent / "documentation_files.jsonl")
    parser.add_argument("--output", type=Path, default=HERE / "documentation_topics.csv")
    parser.add_argument("--model-output", type=Path, default=HERE / "bertopic_documentation_model")
    parser.add_argument(
        "--embedding-cache",
        type=Path,
        default=None,
        help="NumPy .npy cache path (default: <input>.embeddings.npy).",
    )
    parser.add_argument(
        "--embedding-model",
        default="all-MiniLM-L6-v2",
        help="SentenceTransformers model name or local model path.",
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="Load the embedding model only from the local Hugging Face cache; do not make network requests.",
    )
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--max-document-chars", type=int, default=4_000)
    parser.add_argument(
        "--keep-code-blocks",
        action="store_true",
        help="Keep fenced code examples in the modeling text (they are removed by default).",
    )
    parser.add_argument(
        "--no-deduplicate",
        action="store_true",
        help="Model repeated normalized document text separately instead of mapping it to one topic.",
    )
    parser.add_argument(
        "--max-documents",
        type=int,
        default=None,
        help="Process at most this many valid JSON objects from the start of the JSONL file.",
    )
    parser.add_argument("--test", action="store_true", help="Process a small subset instead of the full input.")
    parser.add_argument("--test-size", type=int, default=5_000)
    parser.add_argument("--rebuild-embeddings", action="store_true")
    parser.add_argument("--min-topic-size", type=int, default=100)
    # Off by default: on the full corpus, merging 43 topics into 30 joined
    # unrelated ones (cybersecurity + tracing, web search + vector stores).
    parser.add_argument(
        "--nr-themes",
        type=int,
        default=None,
        help="Merge topics into about this many themes; the unmerged topic is kept in Subtopic columns.",
    )
    parser.add_argument(
        "--merge-topics",
        action="append",
        default=[],
        type=lambda text: [int(topic) for topic in text.split(",")],
        metavar="ID,ID[,...]",
        help="Merge these topic ids of the fitted model into one (repeatable); ids are renumbered afterwards.",
    )
    parser.add_argument(
        "--topic-names",
        type=Path,
        default=None,
        help='JSON of final topic id to reviewed name and description, e.g. {"0": {"name": "...", "description": "..."}}.',
    )
    parser.add_argument(
        "--drop-topics",
        type=lambda text: [int(topic) for topic in text.split(",")],
        default=[],
        metavar="ID,ID[,...]",
        help="Final topic ids that duplicate a Doc type; their texts move to the nearest other topic (same threshold).",
    )
    # Fitting on a capped sample stops large repositories and templated folders
    # from becoming "topics"; every text is then assigned with transform().
    parser.add_argument("--max-docs-per-repo", type=int, default=300, help="Texts per repository in the fit sample.")
    parser.add_argument(
        "--max-docs-per-folder",
        type=int,
        default=50,
        help="Texts per folder, and per file name across sibling folders (e.g. skills/*/SKILL.md), in the fit sample.",
    )

    parser.add_argument("--umap-n-neighbors", type=int, default=30)
    parser.add_argument("--umap-n-components", type=int, default=5)
    parser.add_argument("--umap-min-dist", type=float, default=0.05)
    parser.add_argument("--umap-metric", default="cosine")
    parser.add_argument("--random-state", type=int, default=42)

    parser.add_argument(
        "--hdbscan-min-cluster-size",
        type=int,
        default=None,
        help="Defaults to --min-topic-size when omitted.",
    )
    parser.add_argument("--hdbscan-min-samples", type=int, default=5)
    parser.add_argument("--hdbscan-metric", default="euclidean")
    # English-only docs form one dense region; "eom" then selects one cluster
    # holding ~95% of documents, while "leaf" keeps the fine-grained topics.
    parser.add_argument(
        "--hdbscan-cluster-selection-method", choices=("eom", "leaf"), default="leaf"
    )
    parser.add_argument("--vectorizer-min-df", type=int, default=3)
    parser.add_argument("--vectorizer-max-df", type=float, default=0.9)
    parser.add_argument(
        "--outlier-threshold",
        type=float,
        default=0.5,
        help="Assign HDBSCAN outliers to the nearest topic when cosine similarity is at least this (above 1 disables).",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    positive = (
        "batch_size", "max_document_chars", "test_size", "min_topic_size", "max_docs_per_repo",
        "max_docs_per_folder", "umap_n_neighbors", "umap_n_components", "vectorizer_min_df",
    )
    for name in positive:
        if getattr(args, name) <= 0:
            raise ValueError(f"--{name.replace('_', '-')} must be positive")
    if args.nr_themes is not None and args.nr_themes <= 0:
        raise ValueError("--nr-themes must be positive")
    if args.max_documents is not None and args.max_documents <= 0:
        raise ValueError("--max-documents must be positive")
    if args.hdbscan_min_cluster_size is not None and args.hdbscan_min_cluster_size <= 0:
        raise ValueError("--hdbscan-min-cluster-size must be positive")
    if args.hdbscan_min_samples is not None and args.hdbscan_min_samples <= 0:
        raise ValueError("--hdbscan-min-samples must be positive")
    if not 0 < args.vectorizer_max_df <= 1:
        raise ValueError("--vectorizer-max-df must be greater than 0 and at most 1")


def document_limit(args: argparse.Namespace) -> int | None:
    """Choose the record limit without silently overriding an explicit limit."""
    return args.max_documents if args.max_documents is not None else (args.test_size if args.test else None)


FENCED_CODE_BLOCK = re.compile(r"(?ms)^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$")
FRONT_MATTER = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.S)
FRONT_MATTER_TEXT = re.compile(r"(?mi)^(?:title|name|description|summary):[ \t]*[\"']?(.*?)[\"']?[ \t]*$")
# Markup that otherwise dominates keywords ("card title", "strong", "img div")
# and embeddings of MDX/HTML-heavy pages without saying what a page is about.
MARKUP_RULES = (
    # Apache-style license headers open 1,378 texts (mostly Airflow .rst) and
    # made the embedding of those pages describe the license, not the page.
    (re.compile(r"(?is)(?:\.\.\s*)?Licensed\s+(?:to|under)\s.{0,1500}?limitations\s+under\s+the\s+License\.?"), " "),
    (re.compile(r"(?m)^[ \t]*(?:import\s.+\sfrom\s.+|export\s+(?:const|default|function)\b.*)$"), " "),
    (re.compile(r"<!--.*?-->", re.S), " "),
    (re.compile(r"</?[A-Za-z][^<>]*>"), " "),
    (re.compile(r"!?\[([^\]]*)\]\([^)]*\)"), r"\1"),
    (re.compile(r"https?://\S+"), " "),
    (re.compile(r"(?m)^[ \t|:+-]+$"), ""),
    (re.compile(r"[ \t]{2,}"), " "),
)


def clean_markup(text: str) -> str:
    """Keep front-matter titles/descriptions and prose; drop layout markup."""
    match = FRONT_MATTER.match(text)
    if match:
        text = "\n".join(FRONT_MATTER_TEXT.findall(match.group(1))) + "\n" + text[match.end():]
    for pattern, replacement in MARKUP_RULES:
        text = pattern.sub(replacement, text)
    return text


WORD = re.compile(r"[^\W\d_]+")
ENGLISH_FUNCTION_WORDS = frozenset(
    "the and of to is are in for with this that you your it be on can will from by or as an not use".split()
)


def is_english(text: str) -> bool:
    """Stdlib language gate: the embedding model and vectorizer are English-only.

    Measured on the corpus: English docs have >=14% function words (terse API
    references ~3-6%); pt-BR/ar/ko/zh translations have ~0-1%, and CJK/Arabic
    text fails the ASCII-letter share.
    ponytail: heuristic, swap for a language-ID model if mixed-language docs matter.
    """
    words = WORD.findall(text.lower())
    letters = sum(map(len, words))
    if not letters:
        return False
    ascii_share = sum(len(word) for word in words if word.isascii()) / letters
    function_share = sum(word in ENGLISH_FUNCTION_WORDS for word in words) / len(words)
    return ascii_share >= 0.95 and function_share >= 0.02


HEADING = re.compile(r"(?m)^[ \t]{0,3}#{1,6}[ \t]+(?P<md>.+?)[ \t#]*$|^(?P<rst>\S.*)\n([=~^\"'`#*+-])\3{2,}[ \t]*$")
MAX_OUTLINE_CHARS = 500


def modeling_text(content: Any, maximum: int, *, keep_code_blocks: bool) -> str | None:
    """Return the heading outline plus bounded prose for clustering, or ``None``.

    The embedding model reads only ~1,000 characters, so the outline of all
    headings comes first: it summarizes pages whose introduction is generic.
    """
    if not isinstance(content, str):
        return None
    prose = FENCED_CODE_BLOCK.sub("\n", content.strip())
    headings = (match.group("md") or match.group("rst") for match in HEADING.finditer(FRONT_MATTER.sub("", prose)))
    outline = clean_markup("; ".join(dict.fromkeys(heading.strip() for heading in headings)))[:MAX_OUTLINE_CHARS]
    body = clean_markup(content.strip() if keep_code_blocks else prose)
    text = re.sub(r"\n{3,}", "\n\n", f"{outline.strip()}\n\n{body}").strip()
    # A bounded prefix prevents a handful of generated logs from consuming
    # disproportionate memory while retaining document titles and introductions.
    return text[:maximum] or None


# Not documentation: vendored code, test fixtures, agent run logs, and
# non-English translation trees (Pidgin and Dutch pages pass is_english).
EXCLUDED_PATH = re.compile(
    r"(?i)(?:^|/)(?:third[_-]party|vendor|node_modules|\.omo/evidence|__fixtures__|fixtures|test-fixtures|__snapshots__|snapshots|testdata)/"
    r"|(?:^|/)(?:translations|i18n|locales?|l10n)/(?!en(?:[-_][a-z]+)?/)[^/]+/"
)
# .txt matches are mostly requirements.txt, CMakeLists.txt, animation frames,
# logs and fixtures; these names are the documentation among them.
TXT_DOCUMENT_NAMES = frozenset({"readme.txt", "llms.txt", "llms-full.txt"})


def is_excluded_path(path: str) -> bool:
    name = path.rsplit("/", 1)[-1].lower()
    return bool(EXCLUDED_PATH.search(path)) or (name.endswith(".txt") and name not in TXT_DOCUMENT_NAMES)


# Document type from the path, first match wins. Topics describe what a file is
# about; this says what kind of file it is (a changelog about build fixes is
# still a changelog). File-name conventions come first, so a README is a README
# wherever it sits; folder rules only type files with no conventional name.
_S = r"(^|/)"  # start of a path segment
_NAME_RULES = (  # patterns end in $ and contain no "/", so they match the file name
    ("Changelog / release notes", _S + r"((change-?log|release[-_ ]?notes)([-_.][^/]*)?|(changes|history|news)(\.[a-z]+)?)$"),
    ("Contributing guide", _S + r"contribut(ing|e|ions?)([-_.][^/]*)?$"),
    ("Issue / PR template", _S + r"(pull_request_template|bug_report|feature_request)[^/]*$"),
    ("Code of conduct", _S + r"code[-_]of[-_]conduct[^/]*$"),
    ("Security policy", r"^(\.github/)?security\.mdx?$"),  # repository root only: docs/security.mdx is a page
    ("License / notice", _S + r"(licen[cs]e|notice|copying)([-_.][^/]*)?$"),
    ("Build / dependency file", _S + r"(requirements[^/]*\.txt|cmakelists\.txt)$"),
    ("Agent skill", _S + r"skill\.md$"),
    # Upper case only: docs/gemini.md is a provider page, GEMINI.md is agent instructions.
    ("Agent instructions", _S + r"((?-i:AGENTS|CLAUDE|GEMINI)\.md|copilot-instructions\.md)$"),
    ("README", _S + r"readme[^/]*$"),
    ("Agent run log / test output", _S + r"test[-_]?(logs?|reports?|results?)([-_.][^/]*)?$"),
    ("Plan / spec / design record", _S + r"(plan|spec|prd|roadmap)\.mdx?$"),
    # Not index.md: sites store each page as <page>/index.mdx, so the folder says more.
    ("Overview / introduction page", _S + r"(overview|introduction|intro|home|welcome)\.mdx?$"),
    ("Getting started / installation",
     _S + r"((getting[-_]started|get[-_]started|quick[-_]?start|installation|install|setup|onboarding)[-_.]|first[-_])[^/]*$"),
    ("Deployment / self-hosting", _S + r"(deploy(ment|ing)?s?|self[-_]?host(ing|ed)?|hosting)[-_.][^/]*$"),
    ("Migration / upgrade guide", _S + r"[^/]*(migrat|upgrad)[^/]*$"),
    ("FAQ / troubleshooting", _S + r"[^/]*(faq|troubleshoot)[^/]*$"),
    ("Reference (API, CLI, configuration)",
     _S + r"([^/]*api[-_]?reference[^/]*|([\w-]*reference|api|sdk|cli|commands|configuration|config|glossary)\.mdx?)$"),
    ("Snippet / partial", _S + r"(_[^/]+\.mdx?|snippet-[^/]*)$"),
    ("Design system / style guide", _S + r"(design\.md|style[-_]?guide[^/]*)$"),
)
_FOLDER_RULES = (  # patterns end in "/", so they match a directory in the path
    ("Changelog / release notes", _S + r"(change-?logs?|releases|release-notes|\.changeset|newsfragments)/"),
    ("Issue / PR template", _S + r"(issue_template|pull_request_template)/"),
    ("Vendored third-party file", _S + r"(third[_-]party|vendor|node_modules)/"),
    ("Agent run log / test output", _S + r"(\.omo/evidence|evidence|runs)/"),
    ("Test file / fixture", _S + r"(__fixtures__|fixtures|test-fixtures|testdata|test-data|__snapshots__|snapshots|tests?)/"),
    ("Translated page", _S + r"(translations|i18n|locales?|l10n)/(?!en([-_][a-z]+)?/)[^/]+/"),
    ("Agent skill", _S + r"skills/"),
    ("Agent definition / command", _S + r"\.[\w-]+/(agents|commands?|prompts)/"),
    ("Prompt / rule file", _S + r"(prompts?|rules)/"),
    ("Example / tutorial", _S + r"(examples?|cookbooks?|samples?|tutorials?|demos?)/"),
    ("Plan / spec / design record", _S + r"\.?(adrs?|rfcs?|plans?|specs?|proposals|design-docs)/"),
    ("Report / analysis", _S + r"(reports?|analysis|research|benchmarks?|experiments?|evals?)/"),
    ("Blog post / announcement", _S + r"(blog|posts|announcements?)/"),
    ("Snippet / partial", _S + r"(snippets?|partials?|_partials?|includes?)/"),
    ("Migration / upgrade guide", _S + r"[^/]*(migrat|upgrad)[^/]*/"),
    ("FAQ / troubleshooting", _S + r"(faq|troubleshooting)/"),
    ("Getting started / installation",
     _S + r"(getting[-_]started|get[-_]started|quick[-_]?start|installation|install|setup|onboarding)/"),
    ("Deployment / self-hosting", _S + r"(deploy(ment|ing)?s?|self[-_]?host(ing|ed)?|hosting)/"),
    ("Tool / integration page",
     _S + r"(tools?|integrations?|providers?|plugins?|connectors?|toolkits?|extensions?|channels?|pieces|bundles|models)/"),
    ("Concept / explanation", _S + r"(concepts?|core[-_]concepts|architecture|explanations?|fundamentals)/"),
    ("Guide / how-to", _S + r"(guides?|how[-_]?to|learn|recipes|advanced|use[-_]cases|user[-_]guide|features?)/"),
    ("Reference (API, CLI, configuration)",
     _S + r"([\w-]*reference|api|api[-_]docs|sdk|cli|commands|configuration|config|glossary)/"),
    ("Design system / style guide", _S + r"design[-_]systems?/"),
)
DOC_TYPE_RULES = tuple((label, re.compile(pattern, re.I)) for label, pattern in _NAME_RULES + _FOLDER_RULES)
DOCS_SITE_FOLDER = re.compile(
    _S + r"(docs?|documentation|docs-site|website|site|content|pages|mintlify|gitbooks?|versioned_docs|wiki|book)/", re.I
)


def doc_type(path: str) -> str:
    label = next((label for label, pattern in DOC_TYPE_RULES if pattern.search(path)), None)
    return label or ("Docs site page (general)" if DOCS_SITE_FOLDER.search(path) else "Other (unclassified)")


# Repository parts that are ordinary words; stripping them would remove content.
GENERIC_REPOSITORY_WORDS = frozenset({"agents", "ai", "cli", "micro", "pi", "sim", "rig", "everywhere"})


@functools.lru_cache(maxsize=None)
def repository_name_pattern(repository: str) -> re.Pattern[str] | None:
    names = [part for part in repository.lower().split("/") if len(part) > 2 and part not in GENERIC_REPOSITORY_WORDS]
    return re.compile(r"(?i)\b(?:" + "|".join(map(re.escape, sorted(names, key=len, reverse=True))) + r")\b") if names else None


def strip_repository_name(text: str, repository: str) -> str:
    """Remove a repository's own owner/name ("crewAI", "CopilotKit") from its docs.

    Otherwise the product name dominates keywords and pulls a repository's docs
    together regardless of subject. Mentions in other repositories are kept.
    """
    pattern = repository_name_pattern(repository)
    return pattern.sub(" ", text) if pattern else text


def load_documents(
    input_path: Path,
    max_chars: int,
    limit: int | None,
    *,
    sample: bool,
    sample_seed: int,
    keep_code_blocks: bool,
) -> tuple[list[Document], int]:
    """Read JSONL and optionally keep a deterministic reservoir sample."""
    documents: list[Document] = []
    malformed = 0
    valid_records = 0
    randomizer = random.Random(sample_seed)
    progress = Progress("Sampling JSONL" if sample else "Reading JSONL", None if sample else limit, interval=5_000)

    with input_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                malformed += 1
                print(f"Warning: skipping malformed JSON on line {line_number:,}: {exc.msg}", file=sys.stderr)
                continue
            if not isinstance(record, dict):
                malformed += 1
                print(f"Warning: skipping non-object JSON on line {line_number:,}", file=sys.stderr)
                continue
            valid_records += 1
            # ``content`` is source data rather than output metadata. Do not
            # retain the original (potentially multi-megabyte) string after
            # making the bounded modeling copy; keeping it would defeat the
            # memory bound for the full 96k-document corpus.
            metadata = {key: value for key, value in record.items() if key != "content"}
            content = record.get("content")
            text, reason = None, NO_CLEAR_TOPIC
            if not isinstance(content, str) or not content.strip():
                reason = "Not modeled: empty file"
            elif is_excluded_path(value(metadata, "path")):
                reason = "Not modeled: excluded path or file type"
            else:
                text = modeling_text(content, max_chars, keep_code_blocks=keep_code_blocks)
                if text and is_english(text):
                    text = strip_repository_name(text, value(metadata, "repository")).strip() or None
                else:
                    text = None
                if text is None:
                    reason = "Not modeled: non-English or no prose"
            document = Document(record=metadata, text=text, unassigned_reason=reason)
            if limit is None or len(documents) < limit:
                documents.append(document)
            elif sample:
                replacement = randomizer.randrange(valid_records)
                if replacement < limit:
                    documents[replacement] = document
            else:
                break
            progress.update(valid_records)
            if limit is not None and not sample and len(documents) >= limit:
                break
    progress.update(valid_records, force=True)
    return documents, malformed


def input_signature(input_path: Path, args: argparse.Namespace, limit: int | None) -> dict[str, Any]:
    """Describe only inputs that affect the order and values of cached embeddings."""
    stat = input_path.stat()
    return {
        "format_version": CACHE_FORMAT_VERSION,
        "input_path": str(input_path.resolve()),
        "input_size": stat.st_size,
        "input_mtime_ns": stat.st_mtime_ns,
        "document_limit": limit,
        "embedding_model": args.embedding_model,
        "max_document_chars": args.max_document_chars,
        "keep_code_blocks": args.keep_code_blocks,
        "deduplicate": not args.no_deduplicate,
        "preprocess_version": PREPROCESS_VERSION,
        "selection": "reservoir" if args.test else "head_or_full",
        "sample_seed": args.random_state if args.test else None,
        "normalized_embeddings": True,
    }


def cache_paths(cache_path: Path) -> tuple[Path, Path]:
    return cache_path, cache_path.with_suffix(cache_path.suffix + ".json")


def cache_is_valid(
    cache_path: Path, manifest_path: Path, signature: dict[str, Any], expected_rows: int
) -> bool:
    if not cache_path.is_file() or not manifest_path.is_file():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("signature") != signature or manifest.get("rows") != expected_rows:
            return False
        embeddings = np.load(cache_path, mmap_mode="r")
        return embeddings.ndim == 2 and embeddings.shape[0] == expected_rows
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def encode_batch(model: Any, texts: list[str], batch_size: int) -> np.ndarray:
    """Support current SentenceTransformers and fail clearly on invalid embeddings."""
    try:
        encoded = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
    except TypeError:  # Compatibility with older SentenceTransformers releases.
        encoded = model.encode(texts, batch_size=batch_size, show_progress_bar=False, convert_to_numpy=True)
        norms = np.linalg.norm(encoded, axis=1, keepdims=True)
        encoded = encoded / np.maximum(norms, np.finfo(np.float32).eps)
    result = np.asarray(encoded, dtype=np.float32)
    if result.ndim != 2 or result.shape[0] != len(texts):
        raise RuntimeError(f"embedding model returned unexpected shape {result.shape} for {len(texts)} texts")
    return result


@functools.lru_cache(maxsize=1)
def load_embedding_model(name: str, local_files_only: bool) -> Any:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("Missing dependency: install sentence-transformers") from exc
    print(f"Loading embedding model: {name}", flush=True)
    try:
        return SentenceTransformer(name, local_files_only=local_files_only)
    except Exception as exc:
        offline_hint = "" if local_files_only else " Try --local-files-only if the model is already cached."
        raise RuntimeError(f"could not load embedding model {name!r}.{offline_hint}") from exc


def create_embedding_cache(
    cache_path: Path,
    manifest_path: Path,
    texts: list[str],
    signature: dict[str, Any],
    args: argparse.Namespace,
) -> np.ndarray:
    """Embed in batches into a memory-mapped .npy file, then atomically publish it."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    partial_path = cache_path.with_suffix(cache_path.suffix + ".partial.npy")
    partial_manifest = manifest_path.with_suffix(manifest_path.suffix + ".partial")
    for stale_path in (partial_path, partial_manifest):
        if stale_path.exists():
            stale_path.unlink()

    model = load_embedding_model(args.embedding_model, args.local_files_only)
    # Batches of similar length need less padding; rows are written back in input order.
    order = sorted(range(len(texts)), key=lambda index: len(texts[index]))
    progress = Progress("Generating embeddings", len(texts), interval=max(args.batch_size, 1))
    first_end = min(args.batch_size, len(texts))
    first_batch = encode_batch(model, [texts[i] for i in order[:first_end]], args.batch_size)
    output = np.lib.format.open_memmap(
        partial_path, mode="w+", dtype=np.float32, shape=(len(texts), first_batch.shape[1])
    )
    output[order[:first_end]] = first_batch
    progress.update(first_end, force=True)
    for start in range(first_end, len(texts), args.batch_size):
        batch = order[start:start + args.batch_size]
        output[batch] = encode_batch(model, [texts[i] for i in batch], args.batch_size)
        end = start + len(batch)
        progress.update(end, force=end == len(texts))
    output.flush()
    del output

    manifest = {"signature": signature, "rows": len(texts), "dimensions": int(first_batch.shape[1])}
    partial_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(partial_path, cache_path)
    os.replace(partial_manifest, manifest_path)
    return np.load(cache_path, mmap_mode="r")


VERSION_SEGMENT = re.compile(r"/v?\d+(?:\.\d+)+(?=/)")


def version_key(document: Document) -> str:
    """Map version snapshots of one page (docs/v1.15.2/x.mdx, docs/x.mdx) to one key.

    crewAI alone ships ~40 docs version snapshots; fitting every copy made
    those near-duplicates the largest "topics".
    """
    return value(document.record, "repository") + ":" + VERSION_SEGMENT.sub("", "/" + value(document.record, "path"))


def model_corpus(documents: list[Document], *, deduplicate: bool) -> tuple[list[str], list[list[int]]]:
    """Return modeling texts and the source rows each text represents.

    Version snapshots and exact normalized duplicates are fitted once.  Fitting
    on one copy prevents a few repositories from turning duplicate artifacts
    into the largest apparent "topics", while every source row still receives
    the learned topic when results are written.
    """
    groups: dict[str, list[int]] = {}
    for source_index, document in enumerate(documents):
        if document.text is not None:
            groups.setdefault(version_key(document) if deduplicate else str(source_index), []).append(source_index)

    texts: list[str] = []
    source_indices: list[list[int]] = []
    text_positions: dict[bytes, int] = {}
    for members in groups.values():
        # Model the unversioned (current) copy when there is one.
        members.sort(key=lambda i: len(value(documents[i].record, "path")))
        text = documents[members[0]].text
        assert text is not None
        normalized = " ".join(text.casefold().split())
        digest = hashlib.blake2b(normalized.encode("utf-8", errors="replace"), digest_size=16).digest()
        position = text_positions.get(digest) if deduplicate else None
        if position is None:
            text_positions[digest] = len(texts)
            texts.append(text)
            source_indices.append(members)
        else:
            source_indices[position].extend(members)
    return texts, source_indices


def balanced_sample(paths: list[tuple[str, str]], *, per_repo: int, per_folder: int, seed: int) -> list[int]:
    """Pick random text indices, capped per repository, per folder, and per sibling-folder file name.

    ``paths`` holds (repository, path) for each text. The file-name cap catches
    templated trees such as ``pieces/community/*/README.md`` that a plain
    folder cap misses.
    """
    order = list(range(len(paths)))
    random.Random(seed).shuffle(order)
    counts: collections.Counter[tuple[str, ...]] = collections.Counter()
    chosen = []
    for index in order:
        repository, path = paths[index]
        parts = path.split("/")
        keys = ((repository,), (repository, "/".join(parts[:-1])), (repository, "/".join(parts[:-2]), parts[-1]))
        if counts[keys[0]] < per_repo and counts[keys[1]] < per_folder and counts[keys[2]] < per_folder:
            counts.update(keys)
            chosen.append(index)
    return sorted(chosen)


def assign_to_nearest_topic(
    topics: np.ndarray, embeddings: np.ndarray, topic_embeddings: np.ndarray, threshold: float, excluded: set[int]
) -> np.ndarray:
    """Give each -1 text its most similar allowed topic when cosine similarity >= threshold.

    Matches BERTopic's reduce_outliers(strategy="embeddings"), but can skip topics
    (ids index ``topic_embeddings``; text embeddings are already normalized).
    """
    topics = topics.copy()
    outliers = np.flatnonzero(topics == -1)
    if not outliers.size:
        return topics
    centers = topic_embeddings / np.linalg.norm(topic_embeddings, axis=1, keepdims=True)
    similarity = np.asarray(embeddings[outliers]) @ centers.T
    similarity[:, sorted(excluded)] = -np.inf
    best = similarity.argmax(axis=1)
    close = similarity[np.arange(outliers.size), best] >= threshold
    topics[outliers[close]] = best[close]
    return topics


def load_or_create_embeddings(
    texts: list[str], cache_path: Path, signature: dict[str, Any], args: argparse.Namespace
) -> np.ndarray:
    """Load a compatible cache or generate one batch by batch."""
    _, manifest_path = cache_paths(cache_path)
    if not args.rebuild_embeddings and cache_is_valid(cache_path, manifest_path, signature, len(texts)):
        print(f"Reusing cached embeddings: {cache_path} ({len(texts):,} documents)", flush=True)
        return np.load(cache_path, mmap_mode="r")
    print(f"Creating embedding cache: {cache_path} ({len(texts):,} documents)", flush=True)
    return create_embedding_cache(cache_path, manifest_path, texts, signature, args)


def build_topic_model(args: argparse.Namespace) -> Any:
    try:
        from bertopic import BERTopic
        from bertopic.representation import KeyBERTInspired, MaximalMarginalRelevance
        from bertopic.vectorizers import ClassTfidfTransformer
        from hdbscan import HDBSCAN
        from sklearn.feature_extraction.text import CountVectorizer
        from umap import UMAP
    except ImportError as exc:
        raise RuntimeError("Missing dependency: install bertopic, umap-learn, hdbscan, and scikit-learn") from exc

    umap_model = UMAP(
        n_neighbors=args.umap_n_neighbors,
        n_components=args.umap_n_components,
        min_dist=args.umap_min_dist,
        metric=args.umap_metric,
        random_state=args.random_state,
    )
    hdbscan_model = HDBSCAN(
        min_cluster_size=args.hdbscan_min_cluster_size or args.min_topic_size,
        min_samples=args.hdbscan_min_samples,
        metric=args.hdbscan_metric,
        cluster_selection_method=args.hdbscan_cluster_selection_method,
        prediction_data=True,
    )
    vectorizer_model = CountVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        min_df=args.vectorizer_min_df,
        max_df=args.vectorizer_max_df,
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9_-]{2,}\b",
    )
    return BERTopic(
        # Needed by KeyBERTInspired/MMR to embed candidate keywords.
        embedding_model=load_embedding_model(args.embedding_model, args.local_files_only),
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer_model,
        ctfidf_model=ClassTfidfTransformer(reduce_frequent_words=True),
        # Keywords closest in meaning to the topic's documents, then de-duplicated
        # ("agent, agents, agent tools" becomes distinct words).
        representation_model=[
            KeyBERTInspired(top_n_words=30, random_state=args.random_state),
            MaximalMarginalRelevance(diversity=0.3, top_n_words=TOP_N_KEYWORDS),
        ],
        top_n_words=TOP_N_KEYWORDS,
        min_topic_size=args.min_topic_size,
        calculate_probabilities=False,
        verbose=True,
    )


def topic_labels(topic_model: Any, names: dict[int, str] | None = None) -> dict[int, tuple[str, str]]:
    names = names or {}
    """Create stable, readable labels and exactly up-to-ten keyword strings."""
    labels: dict[int, tuple[str, str]] = {-1: ("Unassigned", "")}
    for topic_id in topic_model.get_topics():
        if topic_id == -1:
            continue
        words = topic_model.get_topic(topic_id) or []
        keywords = [str(word) for word, _score in words[:TOP_N_KEYWORDS] if word]
        keyword_text = ", ".join(keywords)
        name = names.get(topic_id) or " | ".join(word.replace("_", " ").title() for word in keywords[:3]) or f"Topic {topic_id}"
        labels[int(topic_id)] = (name, keyword_text)
    return labels


def value(record: dict[str, Any], key: str) -> str:
    raw = record.get(key, "")
    return raw if isinstance(raw, str) else str(raw)


def write_csv(
    documents: list[Document],
    labels: dict[int, tuple[str, str]],
    descriptions: dict[int, str],
    subtopic_labels: dict[int, tuple[str, str]] | None,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    columns = OUTPUT_COLUMNS + (SUBTOPIC_COLUMNS if subtopic_labels is not None else ())
    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for document in documents:
            record = document.record
            path = value(record, "path")
            if document.topic_id == -1:
                topic_name, keywords = document.unassigned_reason, ""
                description = UNASSIGNED[document.unassigned_reason]
            else:
                topic_name, keywords = labels.get(document.topic_id, (f"Topic {document.topic_id}", ""))
                description = descriptions.get(document.topic_id, "")
            writer.writerow(
                {
                    "Repository URL": value(record, "repository_url"),
                    "Repository name": value(record, "repository"),
                    "Doc file path": path,
                    "Doc file name": Path(path).name,
                    "Doc type": doc_type(path),
                    "Topic id": document.topic_id,
                    "Topic name": topic_name,
                    "Topic description": description,
                    "Keywords": keywords,
                    "Subtopic id": document.subtopic_id,
                    "Subtopic keywords": (subtopic_labels or {}).get(document.subtopic_id, ("", ""))[1],
                }
            )


def save_model(topic_model: Any, output_path: Path, embedding_model: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Retaining the model identifier allows BERTopic.load() to embed new documents.
    topic_model.save(str(output_path), serialization="safetensors", save_ctfidf=True, save_embedding_model=embedding_model)


def main() -> int:
    args = parse_args()
    try:
        validate_args(args)
        if not args.input.is_file():
            for c in [
                HERE.parent / "data" / args.input.name,
                HERE.parent / args.input.name,
                Path("03_documentation_analysis/data") / args.input.name,
            ]:
                if c.is_file():
                    args.input = c
                    break
        if not args.input.is_file():
            raise FileNotFoundError(f"input JSONL file does not exist: {args.input}")
        limit = document_limit(args)
        cache_path = args.embedding_cache or args.input.with_suffix(".embeddings.npy")
        started = time.perf_counter()
        documents, malformed = load_documents(
            args.input,
            args.max_document_chars,
            limit,
            sample=args.test,
            sample_seed=args.random_state,
            keep_code_blocks=args.keep_code_blocks,
        )
        model_count = sum(document.text is not None for document in documents)
        print(
            f"Loaded {len(documents):,} valid record(s); {model_count:,} will be modeled; "
            f"{len(documents) - model_count:,} empty/invalid-content record(s) will be unassigned.",
            flush=True,
        )
        if malformed:
            print(f"Skipped {malformed:,} malformed JSONL record(s) with no usable metadata.", file=sys.stderr)
        if model_count < 2:
            raise ValueError("at least two non-empty string documents are required for topic modeling")

        signature = input_signature(args.input, args, limit)
        texts, source_indices = model_corpus(documents, deduplicate=not args.no_deduplicate)
        duplicate_count = model_count - len(texts)
        print(
            f"Modeling {len(texts):,} unique text(s)"
            f"; {duplicate_count:,} duplicate source record(s) will inherit their canonical topic.",
            flush=True,
        )
        embeddings = load_or_create_embeddings(texts, cache_path, signature, args)
        topic_model = build_topic_model(args)

        text_paths = [(value(documents[m[0]].record, "repository"), value(documents[m[0]].record, "path")) for m in source_indices]
        fit_indices = balanced_sample(
            text_paths, per_repo=args.max_docs_per_repo, per_folder=args.max_docs_per_folder, seed=args.random_state
        )
        fit_texts = [texts[i] for i in fit_indices]
        print(f"Fitting BERTopic (UMAP + HDBSCAN) on a balanced sample of {len(fit_texts):,} text(s)...", flush=True)
        fit_started = time.perf_counter()
        topic_model.fit(fit_texts, embeddings=np.asarray(embeddings[fit_indices]))
        print(f"BERTopic fit completed in {time.perf_counter() - fit_started:.1f}s", flush=True)

        subtopics = np.full(len(texts), -1)
        fit_topics = np.asarray(topic_model.topics_)
        subtopics[fit_indices] = fit_topics
        rest = np.setdiff1d(np.arange(len(texts)), fit_indices)
        if rest.size:
            print(f"Assigning the remaining {rest.size:,} text(s)...", flush=True)
            subtopics[rest], _ = topic_model.transform([texts[i] for i in rest], embeddings=np.asarray(embeddings[rest]))
        outliers = int((subtopics == -1).sum())
        if outliers and args.outlier_threshold <= 1:
            # Keywords stay those of HDBSCAN's core members; only assignments change.
            subtopics = np.asarray(topic_model.reduce_outliers(
                texts, subtopics.tolist(), strategy="embeddings", embeddings=embeddings, threshold=args.outlier_threshold
            ))
            print(f"Reassigned {outliers - int((subtopics == -1).sum()):,} of {outliers:,} outlier text(s)")

        subtopic_labels = topic_labels(topic_model)
        if args.merge_topics:
            print(f"Merging topic groups {args.merge_topics}...", flush=True)
            topic_model.merge_topics(fit_texts, args.merge_topics)
        if args.nr_themes is not None:
            print(f"Merging {len(topic_model.get_topics()) - 1:,} topics into about {args.nr_themes} themes...", flush=True)
            topic_model.reduce_topics(fit_texts, nr_topics=args.nr_themes + 1)  # +1: the outlier topic counts
        # Every fitted topic has members in the fit sample, so this maps all of them.
        topic_of = dict(zip(fit_topics.tolist(), topic_model.topics_)) | {-1: -1}
        topics = np.array([topic_of[subtopic] for subtopic in subtopics.tolist()])
        if args.drop_topics:
            # These topics duplicate a Doc type; their texts move to the nearest remaining topic.
            dropped = np.isin(topics, args.drop_topics)
            print(f"Reassigning {int(dropped.sum()):,} text(s) of dropped topics {args.drop_topics}...", flush=True)
            topics[dropped] = -1
            offset = 1 if -1 in topic_model.get_topics() else 0
            # -2 hides the other texts so only the dropped topics' texts are reassigned.
            reassigned = assign_to_nearest_topic(
                np.where(dropped, -1, -2), embeddings, np.asarray(topic_model.topic_embeddings_)[offset:],
                args.outlier_threshold, set(args.drop_topics),
            )
            topics[dropped] = reassigned[dropped]
        reviewed = {}
        if args.topic_names:
            reviewed = {int(topic): info for topic, info in json.loads(args.topic_names.read_text(encoding="utf-8")).items()}
            topic_model.set_topic_labels({topic: info["name"] for topic, info in reviewed.items()})  # saved in the model too
        names = {topic: info["name"] for topic, info in reviewed.items()}
        descriptions = {topic: info.get("description", "") for topic, info in reviewed.items()}
        for indices, subtopic, topic in zip(source_indices, subtopics.tolist(), topics.tolist(), strict=True):
            for index in indices:
                documents[index].subtopic_id = subtopic
                documents[index].topic_id = topic

        write_csv(
            documents, topic_labels(topic_model, names), descriptions,
            subtopic_labels if args.nr_themes else None, args.output,
        )
        save_model(topic_model, args.model_output, args.embedding_model)
        print(f"Wrote {len(documents):,} rows to {args.output}")
        print(f"Saved BERTopic model to {args.model_output}")
        print(f"Total elapsed time: {time.perf_counter() - started:.1f}s")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
