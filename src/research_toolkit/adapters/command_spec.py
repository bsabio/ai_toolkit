"""Machine-readable command specification for agent onboarding."""

from __future__ import annotations

COMMAND_SPEC: dict = {
    "name": "tool",
    "version": "0.2.0",
    "description": (
        "Research Toolkit CLI – search, store, summarize, and query web information "
        "with citations.  Uses Ollama (local LLM) by default; falls back to Gemini or OpenAI."
    ),
    "llm_providers": {
        "ollama": {
            "description": "Local LLM via Ollama daemon (no API key needed)",
            "default_model": "qwen2.5:3b",
            "auto_detected": True,
        },
        "gemini": {
            "description": "Cloud LLM via Google Gemini API (requires GEMINI_API_KEY)",
            "default_model": "gemini-2.0-flash",
        },
        "openai": {
            "description": "Cloud LLM via OpenAI API (requires OPENAI_API_KEY)",
            "default_model": "gpt-4o-mini",
        },
    },
    "commands": {
        "help": {
            "description": "Show help for all commands or a specific command.",
            "usage": "tool help [<command>]",
            "args": [
                {"name": "command", "type": "string", "required": False, "description": "Command name to get help for"}
            ],
            "flags": [],
        },
        "spec": {
            "description": "Output machine-readable command specification as JSON.",
            "usage": "tool spec",
            "args": [],
            "flags": [],
        },
        "doctor": {
            "description": "Validate environment, storage permissions, provider connectivity, and index health.",
            "usage": "tool doctor [--json] [--provider ollama|gemini|openai|auto]",
            "args": [],
            "flags": [
                {"name": "--json", "description": "Output results as JSON"},
                {"name": "--provider", "type": "string", "default": "auto", "description": "Force LLM provider: ollama, gemini, openai, or auto"},
            ],
        },
        "models": {
            "description": "List all models available on the local Ollama instance.",
            "usage": "tool models [--json]",
            "args": [],
            "flags": [
                {"name": "--json", "description": "Output as JSON"},
            ],
        },
        "search": {
            "description": "Search the web for a query, snapshot and store results locally.",
            "usage": 'tool search "<query>" [--recency 30d] [--max 10] [--json]',
            "args": [
                {"name": "query", "type": "string", "required": True, "description": "Search query string"}
            ],
            "flags": [
                {"name": "--recency", "type": "string", "default": None, "description": "Recency filter, e.g. '7d', '30d'"},
                {"name": "--max", "type": "int", "default": 10, "description": "Maximum number of results"},
                {"name": "--json", "description": "Output as JSON"},
            ],
        },
        "ingest": {
            "description": "Ingest a local file or URL into the research library.",
            "usage": "tool ingest <path_or_url> [--json]",
            "args": [
                {"name": "path_or_url", "type": "string", "required": True, "description": "File path or URL to ingest"}
            ],
            "flags": [
                {"name": "--json", "description": "Output as JSON"},
            ],
        },
        "summarize": {
            "description": "Summarize a stored resource with citations referencing local files and original URLs.",
            "usage": "tool summarize <resource_id> [--format md|json] [--json] [--provider ollama|gemini|openai|auto]",
            "args": [
                {"name": "resource_id", "type": "string", "required": True, "description": "Resource ID to summarize"}
            ],
            "flags": [
                {"name": "--format", "type": "string", "default": "md", "description": "Output format: md or json"},
                {"name": "--json", "description": "Output as JSON"},
                {"name": "--provider", "type": "string", "default": "auto", "description": "Force LLM provider"},
            ],
        },
        "query": {
            "description": "Answer a question using the local library (no live browsing by default). Use --live to re-search.",
            "usage": 'tool query "<question>" [--topk 5] [--live] [--json] [--provider ollama|gemini|openai|auto]',
            "args": [
                {"name": "question", "type": "string", "required": True, "description": "Question to answer"}
            ],
            "flags": [
                {"name": "--topk", "type": "int", "default": 5, "description": "Number of top resources to use"},
                {"name": "--live", "description": "Re-search the web before answering"},
                {"name": "--json", "description": "Output as JSON"},
                {"name": "--provider", "type": "string", "default": "auto", "description": "Force LLM provider"},
            ],
        },
        "show": {
            "description": "Display metadata, content, or snippets for a stored resource.",
            "usage": "tool show <resource_id> [--field meta|content|snippets] [--json]",
            "args": [
                {"name": "resource_id", "type": "string", "required": True, "description": "Resource ID to display"}
            ],
            "flags": [
                {"name": "--field", "type": "string", "default": "meta", "description": "What to show: meta, content, or snippets"},
                {"name": "--json", "description": "Output as JSON"},
            ],
        },
        "list": {
            "description": "List all resources stored in the local library.",
            "usage": "tool list [--json]",
            "args": [],
            "flags": [
                {"name": "--json", "description": "Output as JSON"},
            ],
        },
        "review": {
            "description": "Review an artifact (image/PDF/text) using Gemini multimodal AI. Returns structured, actionable feedback.",
            "usage": "tool review <path> [--rubric rubric.json] [--format json|md] [--model MODEL] [--thinking high|low] [--json]",
            "args": [
                {"name": "path", "type": "string", "required": True, "description": "Path to the artifact file (PNG, JPG, PDF, MD, TXT, etc.)"}
            ],
            "flags": [
                {"name": "--rubric", "type": "string", "default": None, "description": "Path to rubric JSON file. Uses general rubric if omitted."},
                {"name": "--format", "type": "string", "default": "json", "description": "Output format: json (default) or md"},
                {"name": "--model", "type": "string", "default": "gemini-2.0-flash", "description": "Gemini model to use"},
                {"name": "--thinking", "type": "string", "default": None, "description": "Thinking budget: high or low"},
                {"name": "--json", "description": "Raw JSON to stdout (machine-parseable)"},
            ],
        },
    },
    "agent_notes": {
        "onboarding": (
            "1. Run 'tool doctor --json' to check readiness.\n"
            "2. Run 'tool models --json' to see available local LLMs.\n"
            "3. Use 'tool search' to acquire sources, then 'tool list --json' to enumerate.\n"
            "4. Use 'tool summarize <id> --json' or 'tool query \"...\" --json' for analysis.\n"
            "5. Use 'tool review <file> --json' to review artifacts (images, PDFs, text).\n"
            "6. All JSON output is machine-parseable; human output uses Rich tables."
        ),
        "idempotency": "ingest and search deduplicate by content hash; safe to retry.",
        "citations": "summarize and query always include citations with resource_id, URL, local path, and capture time.",
        "review": (
            "The review command accepts any artifact file and returns structured feedback.\n"
            "Output schema: {overall_score, pass, summary, issues[], next_steps[]}.\n"
            "Each issue: {severity, title, location, evidence, fix}.\n"
            "Requires GEMINI_API_KEY in .env. Supports rubrics for domain-specific criteria."
        ),
    },
}
