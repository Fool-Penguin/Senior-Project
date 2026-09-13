"""Run: python topic_modelling/test_bertopic_documentation_topics.py (or pytest)."""

import numpy as np

from bertopic_documentation_topics import (
    Document,
    assign_to_nearest_topic,
    balanced_sample,
    clean_markup,
    doc_type,
    is_english,
    is_excluded_path,
    model_corpus,
    modeling_text,
    strip_repository_name,
    topic_labels,
)


def test_preprocessing() -> None:
    assert is_english("This guide shows you how to install the CLI and use it with your project.")
    assert not is_english("Este guia mostra como instalar a CLI e usá-la no seu projeto com agentes.")
    assert not is_english("本指南介绍如何安装命令行工具并在项目中使用。")

    cleaned = clean_markup('---\ntitle: "Agents"\nicon: robot\n---\n<Card title="x">See [docs](https://a.b/c)</Card>\n|---|---|\n')
    assert "Agents" in cleaned and "icon" not in cleaned and "<Card" not in cleaned
    assert "docs" in cleaned and "https" not in cleaned and "|---|" not in cleaned

    licensed = clean_markup(" .. Licensed to the Apache Software Foundation (ASF) under one\n    or more ... "
                            "permissions and limitations\n    under the License.\n\nOperators run tasks.")
    assert "Licensed" not in licensed and "Operators run tasks." in licensed

    text = modeling_text("---\ntitle: Memory\n---\nIntro.\n\n## Store\n```bash\n# not a heading\n```\nSetup\n-----\n",
                         4_000, keep_code_blocks=False)
    assert text is not None and text.startswith("Store; Setup\n") and "not a heading" not in text

    for path in ("third_party/json/README.md", ".omo/evidence/run.md", "src/__fixtures__/a.md",
                 "translations/pcm/README.md", "i18n/zh-CN/docs/a.md", "CMakeLists.txt"):
        assert is_excluded_path(path), path
    for path in ("translations/en/README.md", "locales/en-US/a.md", "docs/llms.txt", "docs/i18n.md"):
        assert not is_excluded_path(path), path

    assert strip_repository_name("Use CrewAI crews", "crewAIInc/crewAI") == "Use   crews"
    assert strip_repository_name("Build agents", "livekit/agents") == "Build agents"

    def doc(path: str, text: str) -> Document:
        return Document(record={"repository": "r", "path": path}, text=text)

    texts, sources = model_corpus(
        [doc("docs/v1.2.0/en/a.mdx", "old"), doc("docs/en/a.mdx", "current"), doc("docs/en/b.mdx", "other")],
        deduplicate=True,
    )
    assert texts == ["current", "other"] and sources == [[1, 0], [2]]


def test_topic_labels() -> None:
    class FakeModel:
        def get_topics(self):
            return {-1: [], 0: [], 1: []}

        def get_topic(self, topic):
            return [("mcp server", 0.9), ("mcp client", 0.8), ("", 0.1)] if topic == 0 else [("agent memory", 0.9)]

    labels = topic_labels(FakeModel(), {0: "Model Context Protocol (MCP)"})
    assert labels[-1] == ("Unassigned", "")
    assert labels[0] == ("Model Context Protocol (MCP)", "mcp server, mcp client")
    assert labels[1] == ("Agent Memory", "agent memory")


def test_doc_type() -> None:
    expected = {
        "CHANGELOG/2026.1.13.md": "Changelog / release notes",
        "packages/core/CHANGELOG.md": "Changelog / release notes",
        ".changeset/quiet-dogs.md": "Changelog / release notes",
        "docs/CONTRIBUTING.md": "Contributing guide",
        ".github/ISSUE_TEMPLATE/bug_report.md": "Issue / PR template",
        "CHANGELOG-next.md": "Changelog / release notes",
        "SECURITY.md": "Security policy",
        "docs/security.mdx": "Docs site page (general)",
        # File name first: a README is a README wherever it sits.
        ".agents/skills/gsap/README.md": "README",
        "integrations/slack/README.md": "README",
        "translations/nl/08-multi-agent/README.md": "README",
        "docs/tools/overview.mdx": "Overview / introduction page",
        "documentation/blog/2025-06-17-goose-app/index.mdx": "Blog post / announcement",
        ".agents/skills/gsap/references/timeline.md": "Agent skill",
        "plugins/x/AGENTS.md": "Agent instructions",
        "backend/docs/gemini.md": "Docs site page (general)",
        ".claude/commands/review.md": "Agent definition / command",
        "cookbook/tools/README.md": "README",
        "cookbook/tools/weather_agent.md": "Example / tutorial",
        "docs/adr/ADR-011-cloud-run.md": "Plan / spec / design record",
        "README.md": "README",
        "packages/core/README.md": "README",
        "docs/concepts/memory.mdx": "Concept / explanation",
        "docs/v1.15.0/en/tools/web-scraping/firecrawl.mdx": "Tool / integration page",
        "docs/en/learn/custom-manager-agent.mdx": "Guide / how-to",
        "docs/quickstart.mdx": "Getting started / installation",
        "docs/sdk-reference/prompt.mdx": "Reference (API, CLI, configuration)",
        "docs/overview.mdx": "Overview / introduction page",
        "translations/nl/08-multi-agent/lesson.md": "Translated page",
        "translations/en/08-multi-agent/lesson.md": "Other (unclassified)",
        ".omo/evidence/run-1/verification.txt": "Agent run log / test output",
        "src/__fixtures__/sample.md": "Test file / fixture",
        "requirements.txt": "Build / dependency file",
        "rules/python/patterns.md": "Prompt / rule file",
        "engineering/engineering-sre.md": "Other (unclassified)",
    }
    for path, label in expected.items():
        assert doc_type(path) == label, (path, doc_type(path))


def test_assign_to_nearest_topic() -> None:
    topic_embeddings = np.array([[1.0, 0.0], [0.0, 1.0], [0.7, 0.7]])
    texts = np.array([[1.0, 0.0], [0.6, 0.8], [0.0, -1.0]])
    topics = assign_to_nearest_topic(np.array([-1, -1, -1]), texts, topic_embeddings, 0.5, excluded={2})
    assert topics.tolist() == [0, 1, -1]  # topic 2 would win for the second text but is excluded
    assert assign_to_nearest_topic(np.array([5, -2, -1]), texts, topic_embeddings, 0.5, set()).tolist() == [5, -2, -1]


def test_balanced_sample() -> None:
    paths = [("big", f"docs/{i}.md") for i in range(10)]  # one folder
    paths += [("big", f"pieces/p{i}/README.md") for i in range(10)]  # templated sibling folders
    paths += [("small", f"d{i}/x{i}.md") for i in range(3)]
    chosen = balanced_sample(paths, per_repo=5, per_folder=2, seed=0)
    repos = [paths[i][0] for i in chosen]
    assert repos.count("big") == 4 and repos.count("small") == 3


if __name__ == "__main__":
    test_preprocessing()
    test_topic_labels()
    test_doc_type()
    test_assign_to_nearest_topic()
    test_balanced_sample()
    print("ok")
