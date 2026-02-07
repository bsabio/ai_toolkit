# CLI Commands Reference

Complete reference for every `tool` subcommand.

---

## General Commands

### `tool help`

Show help text for all commands, or details for a specific command.

```bash
tool help            # full usage overview
tool help search     # search-specific help
tool help review     # review-specific help
```

### `tool spec`

Emit the machine-readable JSON command spec (useful for agent onboarding).

```bash
tool spec | python -m json.tool
```

### `tool doctor`

Run environment diagnostics — checks API keys, Ollama connectivity, Gemini key, search provider, index health, and storage.

```bash
tool doctor
```

---

## Research Pipeline Commands

### `tool search "<query>"`

Search the web and store results in the local library.

| Flag | Default | Description |
|------|---------|-------------|
| `--max N` | 5 | Maximum results to fetch |

```bash
tool search "transformer architecture explained" --max 10
```

### `tool ingest <path_or_url>`

Ingest a local file (`.md`, `.txt`, `.html`) or URL into the library.

```bash
tool ingest notes.md
tool ingest https://example.com/article
```

### `tool summarize <resource_id>`

Summarize a stored resource, producing a markdown summary with citations.

| Flag | Default | Description |
|------|---------|-------------|
| `--json` | false | Output raw JSON instead of rich table |

```bash
tool summarize abc123
tool summarize abc123 --json
```

### `tool query "<question>"`

Answer a question from the local library (RAG-style), with citations.

| Flag | Default | Description |
|------|---------|-------------|
| `--live` | false | Fall back to live web search if library has no answer |
| `--json` | false | Output raw JSON |

```bash
tool query "What are the main Ollama CLI flags?"
tool query "latest news" --live
```

### `tool list`

List all stored resources.

```bash
tool list
tool list --json
```

### `tool show <resource_id>`

Show details for a specific stored resource.

```bash
tool show abc123
```

### `tool models`

List available Ollama models.

```bash
tool models
```

### `tool reindex`

Rebuild the search index from stored resources.

```bash
tool reindex
```

---

## Artifact Review Commands

### `tool review <path>`

Send an artifact (image, PDF, markdown, text) to Gemini for structured multimodal feedback.

| Flag | Default | Description |
|------|---------|-------------|
| `--rubric <path>` | built-in general rubric | Path to a JSON rubric file |
| `--format json\|md` | rich table | Output format |
| `--json` | false | Shortcut for `--format json` |
| `--model <name>` | `gemini-2.0-flash` | Gemini model to use |
| `--thinking high\|low` | none | Enable Gemini thinking budget |

**Supported file types:** `.png`, `.jpg/.jpeg`, `.gif`, `.webp`, `.pdf`, `.md`, `.txt`, `.json`, `.csv`, `.html`

```bash
# Review a UI screenshot with the UI rubric
tool review mockup.png --rubric rubrics/ui.json

# Review a markdown doc, get JSON output
tool review report.md --rubric rubrics/docs.json --json

# Review a PDF with high thinking budget
tool review slides.pdf --thinking high

# Review with default rubric, markdown output
tool review chart.png --format md
```

**Output schema (JSON mode):**

```json
{
  "overall_score": 72,
  "pass": true,
  "summary": "...",
  "issues": [
    {
      "severity": "critical|major|minor|suggestion",
      "title": "...",
      "location": "...",
      "evidence": "...",
      "fix": "..."
    }
  ],
  "next_steps": ["..."],
  "artifact": { "path": "...", "filename": "...", "mime_type": "...", "size_bytes": 0 },
  "model": "gemini-2.0-flash",
  "reviewed_at": "2026-02-07T01:09:18Z"
}
```

**Storage:** Each review is persisted under `research/reviews/<timestamp>__<slug>/`:

```
research/reviews/2026-02-07T01-09-18__sample-ui.png/
├── input/sample-ui.png     # copy of the reviewed artifact
├── rubric.json             # rubric used
├── report.json             # structured review output
├── report.md               # markdown-rendered report
└── traces/
    ├── prompt.txt           # exact prompt sent to Gemini
    └── model_meta.json      # model name & timing
```

---

## Bundled Rubrics

| File | Purpose | Criteria | Pass Threshold |
|------|---------|----------|---------------|
| `rubrics/ui.json` | UI/UX review | Visual Hierarchy, Consistency, Readability, Layout, Accessibility, Responsiveness | 65 |
| `rubrics/docs.json` | Documentation review | Clarity, Completeness, Structure, Correctness, Formatting | 60 |

Custom rubrics follow the same JSON schema — see the bundled files for examples.

---

## Environment Variables

| Variable | Required For | Description |
|----------|-------------|-------------|
| `GEMINI_API_KEY` | `review` | Google AI Studio API key |
| `OPENAI_API_KEY` | `query`, `summarize` (fallback) | OpenAI API key |
| `OLLAMA_HOST` | `query`, `summarize` (default) | Ollama server URL (default: `http://localhost:11434`) |
| `OLLAMA_MODEL` | `query`, `summarize` | Ollama model name (default: `qwen2.5:3b`) |
| `LLM_PROVIDER` | all LLM commands | `auto`, `ollama`, `gemini`, or `openai` |
| `BRAVE_API_KEY` | `search` | Brave Search API key |
| `GOOGLE_API_KEY` | `search` | Google Custom Search API key |
| `SERPAPI_KEY` | `search` | SerpAPI key |
