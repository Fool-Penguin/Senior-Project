#!/usr/bin/env python3
"""Build a manual-review CSV for classifying repos as "agentic AI" or not.

For every repo in repo_metadata.csv, this pulls (and caches) GitHub topics
and a short README snippet, then writes a CSV with one row per repo:

    Repo_Name, Repo_URL, Stars, Description, Topics, Suggested,
    Is_Agentic, Category, Notes, README_Snippet,
    Has_SECURITY, Has_CONTRIBUTING, Has_SKILL, Has_AGENTS

`Suggested` is a heuristic guess (Y / Maybe / N) so you only need to
double-check the "Maybe" rows carefully and spot-check the rest, instead of
manually judging all ~274 repos from scratch. `Is_Agentic`, `Category`, and
`Notes` are left blank for you to fill in while reviewing.

Usage:
    python generate_manual_review.py
    python generate_manual_review.py --output manual_review.csv
    python generate_manual_review.py --refresh   # ignore cache, re-fetch
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

API_ROOT = "https://api.github.com"

METADATA_COLUMNS = [
    "Has_SECURITY",
    "Has_CONTRIBUTING",
    "Has_SKILL",
    "Has_AGENTS",
]

OUTPUT_COLUMNS = [
    "Repo_Name",
    "Repo_URL",
    "Stars",
    "Description",
    "Topics",
    "Suggested",
    "Is_Agentic",
    "Category",
    "Notes",
    "README_Snippet",
] + METADATA_COLUMNS

# --- Heuristic classifier -------------------------------------------------

AGENT_CORE = re.compile(r"\bagent(ic)?s?\b", re.I)
LOOSE_TERMS = re.compile(
    r"\b(assistant|autonomous|automation|copilot|chatbot|orchestrat)\b", re.I
)
EXCLUDE_TERMS = re.compile(
    r"\b(awesome|guide|checklist|tutorial|course|from scratch|curated list|"
    r"lessons|notebooks|collection|cheatsheet|roadmap|interview|book)\b",
    re.I,
)
STRONG_AGENT_TOPICS = {
    "ai-agent", "ai-agents", "agent", "agents", "llm-agent", "llm-agents",
    "agentic-ai", "agentic", "autonomous-agents", "autonomous-agent",
    "multi-agent", "multi-agent-systems", "agent-framework",
}

# Weaker, topic-only signals that on their own are not decisive but combine
# with README/description evidence of autonomy or tool-use to confirm agentic
# behavior for "assistant"/"automation"-flavored repos (e.g. openclaw, n8n).
ADJACENT_AGENT_TOPICS = {
    "assistant", "ai-assistant", "personal-assistant", "chatbot",
    "workflow-automation", "automation", "llm", "llm-apps", "mcp",
    "mcp-server", "mcp-client", "tool-calling", "function-calling",
}

# Evidence of autonomous/tool-using behavior found in the README body, used
# to upgrade "Maybe" -> "Y" for assistant/automation-labeled repos that are
# actually agentic in practice (run tools, plan, act on your behalf, etc.).
BEHAVIOR_EVIDENCE = re.compile(
    r"\b(runs? (tools?|tasks?)|executes? (tasks?|commands?|code)|"
    r"plans? and (executes?|acts?)|acts? on your behalf|autonomous(ly)?|"
    r"multi-?step|tool[- ]use|tool calling|function calling|self-correct|"
    r"self-improv|takes? actions?|connects? models,? tools|"
    r"build (and )?(deploy )?ai agents?|ai agents and workflows)\b",
    re.I,
)


def suggest_classification(
    name: str, description: str, topics: list[str], readme_snippet: str = ""
) -> str:
    text = f"{name} {description}"
    full_text = f"{text} {readme_snippet}"
    topic_set = {t.lower() for t in topics}

    has_strong_topic = bool(topic_set & STRONG_AGENT_TOPICS)
    has_adjacent_topic = bool(topic_set & ADJACENT_AGENT_TOPICS)
    name_has_agent = bool(AGENT_CORE.search(name))
    excluded = bool(EXCLUDE_TERMS.search(text))
    has_behavior_evidence = bool(BEHAVIOR_EVIDENCE.search(full_text))

    if excluded and not name_has_agent and not has_strong_topic:
        return "N"
    if AGENT_CORE.search(full_text) or has_strong_topic:
        return "Y"
    if (LOOSE_TERMS.search(full_text) or has_adjacent_topic) and has_behavior_evidence:
        # "Assistant"/"automation"-labeled repo with concrete evidence of
        # autonomous/tool-using behavior in the README -> confidently agentic.
        return "Y"
    if LOOSE_TERMS.search(full_text) or has_adjacent_topic:
        return "Maybe"
    return "N"


# --- GitHub API helpers ----------------------------------------------------


class GitHubApiError(RuntimeError):
    def __init__(self, status: int, details: str) -> None:
        super().__init__(f"GitHub API HTTP {status}: {details}")
        self.status = status


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def github_json(url: str, token: str | None, accept: str | None = None) -> Any:
    headers = {
        "Accept": accept or "application/vnd.github+json",
        "User-Agent": "manual-review-generator",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise GitHubApiError(exc.code, details) from exc
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise RuntimeError(f"GitHub network error: {exc}") from exc


def fetch_topics(full_name: str, token: str | None) -> list[str]:
    url = f"{API_ROOT}/repos/{urllib.parse.quote(full_name, safe='/')}"
    data = github_json(url, token)
    return data.get("topics", []) or []


def clean_readme_text(raw_markdown: str, max_chars: int = 400) -> str:
    text = raw_markdown
    # Strip HTML tags, images, badges, and markdown link syntax.
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[#*`_>-]{1,}", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def fetch_readme_snippet(full_name: str, token: str | None) -> str:
    url = f"{API_ROOT}/repos/{urllib.parse.quote(full_name, safe='/')}/readme"
    try:
        data = github_json(url, token)
    except GitHubApiError as exc:
        if exc.status == 404:
            return ""
        raise
    content_b64 = data.get("content", "")
    try:
        raw = base64.b64decode(content_b64).decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        return ""
    return clean_readme_text(raw)


# --- Cache -------------------------------------------------------------


def load_cache(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(path: Path, cache: dict[str, dict[str, Any]]) -> None:
    path.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# --- Main ----------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata-csv", default="repo_metadata.csv")
    parser.add_argument("--search-json", default="repo_search_results.json")
    parser.add_argument("--output", default="manual_review.csv")
    parser.add_argument("--cache", default="manual_review_cache.json")
    parser.add_argument("--delay", type=float, default=0.15)
    parser.add_argument(
        "--refresh", action="store_true", help="Ignore cache and re-fetch everything."
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(Path(".env"))
    token = os.getenv("GITHUB_TOKEN")

    metadata_path = Path(args.metadata_csv)
    search_path = Path(args.search_json)
    output_path = Path(args.output)
    cache_path = Path(args.cache)

    with metadata_path.open(encoding="utf-8-sig") as f:
        metadata_rows = list(csv.DictReader(f))

    search_payload = json.loads(search_path.read_text(encoding="utf-8"))
    search_by_name: dict[str, dict[str, Any]] = {}
    for repo in search_payload.get("repositories", []):
        search_by_name.setdefault(repo.get("name", ""), repo)

    cache = {} if args.refresh else load_cache(cache_path)

    rows: list[dict[str, Any]] = []
    failures = 0
    total = len(metadata_rows)

    for index, meta_row in enumerate(metadata_rows, start=1):
        name = meta_row.get("Repo_Name", "")
        search_meta = search_by_name.get(name, {})
        full_name = search_meta.get("full_name") or name
        description = search_meta.get("description") or ""

        cached = cache.get(full_name)
        if cached is not None:
            topics = cached.get("topics", [])
            readme_snippet = cached.get("readme_snippet", "")
            print(f"[{index}/{total}] Cached: {full_name}")
        else:
            print(f"[{index}/{total}] Fetching: {full_name}")
            topics = []
            readme_snippet = ""
            fetched_ok = False

            for attempt in range(2):  # try once, retry once on failure
                try:
                    topics = fetch_topics(full_name, token)
                    time.sleep(args.delay)
                    readme_snippet = fetch_readme_snippet(full_name, token)
                    time.sleep(args.delay)
                    fetched_ok = True
                    break
                except GitHubApiError as exc:
                    if exc.status == 401 and token:
                        print(
                            "Warning: GITHUB_TOKEN invalid; retrying without token.",
                            file=sys.stderr,
                        )
                        token = None
                        continue
                    failures += 1
                    print(f"Warning: failed for {full_name}: {exc}", file=sys.stderr)
                    break
                except RuntimeError as exc:
                    print(
                        f"Warning: attempt {attempt + 1} failed for {full_name}: {exc}",
                        file=sys.stderr,
                    )
                    if attempt == 0:
                        time.sleep(1.0)
                        continue
                    failures += 1

            if fetched_ok or topics or readme_snippet:
                cache[full_name] = {"topics": topics, "readme_snippet": readme_snippet}
                save_cache(cache_path, cache)

        suggested = suggest_classification(name, description, topics, readme_snippet)

        row = {
            "Repo_Name": name,
            "Repo_URL": meta_row.get("Repo_URL", ""),
            "Stars": meta_row.get("Stars", ""),
            "Description": description,
            "Topics": ", ".join(topics),
            "Suggested": suggested,
            "Is_Agentic": "",
            "Category": "",
            "Notes": "",
            "README_Snippet": readme_snippet,
        }
        for col in METADATA_COLUMNS:
            row[col] = meta_row.get(col, "")
        rows.append(row)

    # Sort so the ambiguous "Maybe" rows are easiest to find and tackle first,
    # then confirmed "Y" (spot-check), then "N" (skim for mistakes), each by
    # stars descending within its group.
    order = {"Maybe": 0, "Y": 1, "N": 2}

    def sort_key(row: dict[str, Any]) -> tuple[int, int]:
        try:
            stars = -int(row["Stars"])
        except (ValueError, TypeError):
            stars = 0
        return (order.get(row["Suggested"], 3), stars)

    rows.sort(key=sort_key)

    with output_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    counts = {"Y": 0, "Maybe": 0, "N": 0}
    for row in rows:
        counts[row["Suggested"]] = counts.get(row["Suggested"], 0) + 1

    print(f"\nWrote {len(rows)} repositories to {output_path}")
    print(f"Suggested breakdown: Y={counts['Y']}  Maybe={counts['Maybe']}  N={counts['N']}")
    if failures:
        print(f"Could not fetch data for {failures} repositories.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
