# Agent Onboarding Guide

This document is designed for AI agents (and humans) to quickly understand,
navigate, and extend the **Research Toolkit** codebase.

---

## 1. What This Toolkit Does

The Research Toolkit is a **CLI application** (`tool`) with two capabilities:

1. **Research Pipeline** — search the web, store resources locally, summarize
   them with an LLM, and answer questions via RAG with citations.
2. **Artifact Review** — send any file (image, PDF, markdown, etc.) to a
   multimodal LLM (Gemini) for structured, rubric-based feedback.

Entry point: `tool` (installed via `pip install -e .`).

---

## 2. Architecture Overview

The codebase follows **Clean Architecture** (Uncle Bob). Dependencies point
inward — outer layers know about inner layers, never the reverse.

```
src/research_toolkit/
├── domain/              # Pure entities & value objects (no IO, no imports from other layers)
│   ├── entities.py          # Resource, Session, Summary, Citation
│   ├── value_objects.py     # ResourceId, SearchQuery, Snippet, etc.
│   └── review_entities.py   # Severity, ReviewIssue, ArtifactRef, ReviewReport
│
├── application/         # Use cases & abstract ports
│   ├── ports.py             # ABC interfaces: Store, LLMProvider, SearchProvider,
│   │                        #   MultimodalLLMProvider, Indexer, etc.
│   └── use_cases/
│       ├── search_web.py
│       ├── ingest_resource.py
│       ├── summarize_resource.py
│       ├── query_library.py
│       ├── review_artifact.py   # Multimodal review use case
│       └── doctor_checks.py
│
├── adapters/            # CLI parsing, presentation, command specs
│   ├── cli.py               # argparse-based CLI dispatcher (~630 lines)
│   ├── presenters.py        # Rich/JSON/MD output formatters
│   └── command_spec.py      # Machine-readable JSON spec for all commands
│
└── infrastructure/      # Concrete implementations of ports
    ├── filesystem_store.py      # File-based resource + review storage
    ├── ollama_provider.py       # Local LLM via Ollama REST API
    ├── gemini_provider.py       # Gemini text-only LLM (for summarize/query)
    ├── gemini_multimodal_provider.py  # Gemini multimodal (for review)
    ├── openai_provider.py       # OpenAI LLM fallback
    ├── brave_search.py          # Brave web search
    ├── tfidf_indexer.py         # TF-IDF search index
    ├── clock.py                 # Wall clock
    └── logger.py                # Console logger
```

### Key Principle

- **Domain** has zero external dependencies — only stdlib.
- **Application** depends only on domain + stdlib. Ports are abstract (ABC).
- **Adapters** depend on application (use cases, DTOs).
- **Infrastructure** implements ports; depends on external libraries (httpx, openai, etc.).

---

## 3. Adding a New Feature

### New Use Case (e.g., "export")

1. If new domain concepts are needed, add entities to `domain/`.
2. If a new external capability is needed, add an abstract port to `application/ports.py`.
3. Create the use case in `application/use_cases/your_use_case.py` — inject ports via constructor.
4. Implement any new ports in `infrastructure/`.
5. Add presenter function in `adapters/presenters.py`.
6. Wire up the CLI subcommand in `adapters/cli.py`:
   - Add to `HELP_TEXT`, `COMMAND_HELP`, create `cmd_yourcommand()`, add subparser.
7. Add to `adapters/command_spec.py` for machine-readable discovery.
8. Add tests in `tests/`.

### New Rubric (for review)

Create a JSON file in `rubrics/` following this schema:

```json
{
  "name": "Rubric Name",
  "version": "1.0",
  "description": "What this rubric evaluates",
  "criteria": [
    { "name": "Criterion", "weight": 25, "description": "What to look for" }
  ],
  "pass_threshold": 60
}
```

Use it: `tool review artifact.png --rubric rubrics/your_rubric.json`

---

## 4. LLM Provider Chain

The toolkit supports three LLM backends with automatic fallback:

| Priority | Provider | Used For | Config |
|----------|----------|----------|--------|
| 1 | Ollama (local) | summarize, query | `OLLAMA_HOST`, `OLLAMA_MODEL` |
| 2 | Gemini (text) | summarize, query (fallback) | `GEMINI_API_KEY` |
| 3 | OpenAI | summarize, query (fallback) | `OPENAI_API_KEY` |
| — | Gemini (multimodal) | review only | `GEMINI_API_KEY` |

Set `LLM_PROVIDER=auto` (default) for the fallback chain, or force one with `ollama`, `gemini`, `openai`.

---

## 5. Storage Layout

All persistent data lives under `research/`:

```
research/
├── resources/           # Ingested web pages & search results
│   └── <resource_id>/
│       ├── meta.json
│       ├── raw/content.html
│       ├── content.md
│       └── summary.json
├── sessions/            # Search session logs
│   └── <session_id>.json
├── reviews/             # Artifact review outputs
│   └── <timestamp>__<slug>/
│       ├── input/<filename>
│       ├── rubric.json
│       ├── report.json
│       ├── report.md
│       └── traces/{prompt.txt, model_meta.json}
└── index/               # TF-IDF search index
```

---

## 6. Running Tests

```bash
pip install pytest   # if not installed
python -m pytest tests/ -v
```

All tests use mocked providers (no API calls). Test fixtures live in `tests/fixtures/`.

---

## 7. Quick Command Reference

```bash
tool help                  # full help
tool doctor                # environment check
tool spec                  # JSON command spec (pipe to jq for reading)
tool search "query"        # search & store
tool ingest file.md        # ingest local file
tool list                  # list resources
tool summarize <id>        # summarize with citations
tool query "question"      # RAG query
tool review file.png       # multimodal review
```

---

## 8. Machine-Readable Spec

For programmatic discovery, `tool spec` returns JSON describing every command, its arguments, flags, and defaults. This is the recommended way for agents to discover capabilities at runtime.
