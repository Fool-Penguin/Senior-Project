# Documentation Collection Summary

## Dataset at a glance

This summary describes `documentation_files.jsonl`, inspected on 12 September 2026. The collection uses one depth-1 Git clone at a time, scans the checked-out default branch recursively (excluding `.git`), and retains files matching `.adoc`, `.asciidoc`, `.markdown`, `.md`, `.mdx`, `.rst`, and `.txt`.

| Measure | Result |
|---|---:|
| Repositories in the input sample | 175 |
| Repositories represented by one or more records | 163 (93.1%) |
| Documentation-file records | 96,231 |
| JSONL file size | 1,021,305,352 bytes (about 974 MiB) |
| Extracted text | 873,735,740 characters across 19,522,120 lines |
| Invalid JSONL records | 0 |
| Duplicate repository/branch/path/SHA records | 0 |
| Empty-content records | 151 |

The JSONL contains the repository, source URL, checked-out branch, repository-relative path, commit SHA, and UTF-8-decoded content for every matched file. Each represented repository is recorded at one checked-out commit, so the data is a point-in-time snapshot rather than a history.

## File types and locations

Markdown is the dominant format, followed closely by MDX. No `.adoc` or `.asciidoc` files were recorded, despite both extensions being included in the collector configuration.

| Extension | Files | Share |
|---|---:|---:|
| `.md` | 50,150 | 52.11% |
| `.mdx` | 39,084 | 40.61% |
| `.txt` | 5,009 | 5.21% |
| `.rst` | 1,969 | 2.05% |
| `.markdown` | 19 | 0.02% |

The recursive scan found 95,117 files in nested directories (98.84%) and 1,114 at repository root (1.16%). The top-level `docs` directory alone contains 44,037 records. Path-based indicators show 51,258 files under a `docs`, `doc`, or `documentation` directory; 9,384 README files; 2,392 changelog or release files; 483 contributing files; and 403 license/notice files. These categories can overlap.

## Default branches captured

Most records came from `main` (83,732 files; 87.0%). Other observed branches were `master` (5,962), `dev` (3,840), `develop` (1,242), `canary` (833), `dev-v2` (335), `3.6.x` (138), `feat/server_team` (70), `development` (51), `v2` (14), and `5.x` (14). This confirms the collector used the repositories' configured checked-out default branches rather than assuming `main` or `master`.

## Distribution across repositories

The corpus is concentrated in a small number of large repositories: the ten repositories with the most matched files account for 50,693 records (52.68% of the dataset), while the ten largest by extracted text account for 469,431,576 characters (53.73%).

| Repository | Matched files | Extracted text |
|---|---:|---:|
| `crewAIInc/crewAI` | 27,983 | 211.35M characters |
| `microsoft/ai-agents-for-beginners` | 3,514 | 39.48M characters |
| `xbtlin/ai-berkshire` | 2,676 | 26.85M characters |
| `mukul975/Anthropic-Cybersecurity-Skills` | 2,587 | 13.65M characters |
| `affaan-m/ECC` | 2,557 | 13.66M characters |
| `code-yeongyu/oh-my-openagent` | 2,417 | 29.23M characters |
| `CopilotKit/CopilotKit` | 2,325 | 13.31M characters |
| `nexu-io/open-design` | 2,250 | 19.37M characters |
| `apache/airflow` | 2,246 | 10.03M characters |
| `openclaw/openclaw` | 2,138 | 27.27M characters |

## Repositories without output records

The following 12 input repositories have no records in `documentation_files.jsonl`:

- `CoplayDev/unity-mcp`
- `Significant-Gravitas/AutoGPT`
- `ToolJet/ToolJet`
- `alibaba/nacos`
- `alibaba/spring-ai-alibaba`
- `ansible/ansible`
- `bojieli/ai-agent-book`
- `google-gemini/gemini-cli`
- `jeecgboot/JeecgBoot`
- `langchain4j/langchain4j`
- `medusajs/medusa`
- `n8n-io/n8n`

No JSONL record can mean either that the repository had no files matching the selected extensions or that collection did not complete for that repository. The collector's terminal output is needed to distinguish those cases.

## Interpretation and data-quality notes

The corpus is a broad documentation-oriented collection, not a semantic documentation-only corpus. The `.txt` rule also captures technical artifacts such as `CMakeLists.txt`, test fixtures, generated chunks, evaluation logs, and phonemizer examples. Several individual files are very large, including a 10.10M-character evaluation result in `Skyvern-AI/skyvern`, an 8.84M-character phonemizer example in `leon-ai/leon`, and a 6.04M-character evaluation log in `assafelovic/gpt-researcher`.

Consequently, downstream analysis should either:

1. retain all records when broad repository text coverage is desired; or
2. exclude `.txt` files and optionally apply path/content rules to remove fixtures, logs, generated files, and release archives when building a documentation-focused corpus.

The recursive workflow successfully preserves nested documentation, skills, examples, package documentation, and localized content; filtering should therefore happen after collection rather than by limiting the clone scan to a small set of directories.
