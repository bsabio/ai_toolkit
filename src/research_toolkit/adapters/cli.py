"""CLI adapter – parses arguments, dispatches to use cases, formats output."""

from __future__ import annotations

import argparse
import json
import sys
import textwrap

from research_toolkit.adapters.command_spec import COMMAND_SPEC
from research_toolkit.adapters import presenters


# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------
HELP_TEXT = textwrap.dedent("""\
    Research Toolkit – search, store, summarize, query with citations.
    Uses Ollama (local LLM) by default; falls back to Gemini or OpenAI.

    Usage:
      tool <command> [options]

    Commands:
      help [cmd]      Show help (or help for a specific command)
      spec            Output machine-readable command spec (JSON)
      doctor          Validate environment, storage, connectivity
      models          List available Ollama models
      search          Search the web and store results
      ingest          Ingest a local file or URL
      summarize       Summarize a stored resource
      query           Answer a question from the local library
      show            Show details / content for a resource
      list            List all stored resources
      reindex         Rebuild index & fix titles
      review          Review an artifact (image/PDF/text) with Gemini

    Examples:
      tool doctor
      tool models
      tool search "quantum computing breakthroughs" --max 5
      tool search "AI safety" --recency 7d
      tool ingest https://example.com/article
      tool list
      tool show abc123def456
      tool summarize abc123def456
      tool query "What are the risks of AGI?" --topk 3
      tool query "latest news" --live
      tool review screenshot.png --rubric rubrics/ui.json --json
      tool review report.pdf --format md

    LLM provider (set LLM_PROVIDER in .env or pass --provider):
      auto   → prefer Ollama if running, then Gemini, then OpenAI  (default)
      ollama → local only (requires Ollama daemon)
      gemini → Google Gemini cloud (requires GEMINI_API_KEY)
      openai → OpenAI cloud (requires OPENAI_API_KEY)

    For detailed help:  tool help <command>
""")

COMMAND_HELP: dict[str, str] = {
    "help": "Usage: tool help [<command>]\n\nShow general help or help for a specific command.",
    "spec": "Usage: tool spec\n\nOutputs the full machine-readable command spec as JSON.\nUseful for agent onboarding.",
    "doctor": (
        "Usage: tool doctor [--json]\n\n"
        "Runs diagnostic checks:\n"
        "  - Environment variables (without revealing values)\n"
        "  - Storage directory permissions\n"
        "  - Search provider connectivity\n"
        "  - LLM provider availability (Ollama / OpenAI)\n"
        "  - Index/registry health"
    ),
    "models": (
        "Usage: tool models [--json]\n\n"
        "List all models available on the local Ollama instance.\n"
        "  --json   Output as JSON"
    ),
    "search": (
        'Usage: tool search "<query>" [--recency 30d] [--max 10] [--json]\n\n'
        "Search the web, snapshot results, and store them in the local library.\n"
        "  --recency   Only show results from the last N days (e.g. 7d, 30d)\n"
        "  --max       Maximum number of results to fetch (default: 10)\n"
        "  --json      Output as JSON"
    ),
    "ingest": (
        "Usage: tool ingest <path_or_url> [--json]\n\n"
        "Ingest a file or URL into the library.\n"
        "  path_or_url  A local file path or http(s) URL\n"
        "  --json       Output as JSON"
    ),
    "summarize": (
        "Usage: tool summarize <resource_id> [--format md|json] [--json]\n\n"
        "Generate a summary with citations for a stored resource.\n"
        "  resource_id  The ID of the resource (shown by 'tool list')\n"
        "  --format     Output format: md (default) or json\n"
        "  --json       Raw JSON output"
    ),
    "query": (
        'Usage: tool query "<question>" [--topk 5] [--live] [--json]\n\n'
        "Answer a question using the local library.\n"
        "  --topk   Number of top sources to consider (default: 5)\n"
        "  --live   Search the web first, then answer\n"
        "  --json   Output as JSON"
    ),
    "show": (
        "Usage: tool show <resource_id> [--field meta|content|snippets] [--json]\n\n"
        "Display stored data for a resource.\n"
        "  --field  Which part to show: meta (default), content, snippets\n"
        "  --json   Output as JSON"
    ),
    "list": (
        "Usage: tool list [--json]\n\n"
        "List all resources stored in the local library.\n"
        "  --json   Output as JSON"
    ),
    "reindex": (
        "Usage: tool reindex [--json]\n\n"
        "Rebuild library.jsonl and fix resource titles.\n"
        "Useful after updating title extraction logic.\n"
        "  --json   Output as JSON"
    ),
    "review": (
        "Usage: tool review <path> [--rubric rubric.json] [--format json|md] "
        "[--model MODEL] [--thinking high|low] [--json]\n\n"
        "Review an artifact file using Gemini multimodal AI.\n"
        "Supported formats: PNG, JPG, PDF, Markdown, text, JSON, CSV, HTML.\n\n"
        "  path       Path to the artifact file\n"
        "  --rubric   Path to a rubric JSON file (optional, has sensible defaults)\n"
        "  --format   Output format: json (default) or md\n"
        "  --model    Gemini model to use (default: gemini-2.0-flash)\n"
        "  --thinking Thinking budget: high or low (optional)\n"
        "  --json     Raw JSON output to stdout"
    ),
}


# ---------------------------------------------------------------------------
# Parse recency string like "7d" -> int days
# ---------------------------------------------------------------------------
def _parse_recency(value: str | None) -> int | None:
    if value is None:
        return None
    value = value.strip().lower()
    if value.endswith("d"):
        return int(value[:-1])
    return int(value)


# ---------------------------------------------------------------------------
# Build container (lazy import to avoid circular deps)
# ---------------------------------------------------------------------------
def _build_container(provider_override: str | None = None) -> dict:
    """Build the dependency container from config.

    *provider_override* can be ``"ollama"``, ``"openai"``, or ``None``
    (which respects the ``LLM_PROVIDER`` env-var / ``auto`` default).
    """
    from research_toolkit.infrastructure.config import load_config
    from research_toolkit.infrastructure.logger import ConsoleLogger
    from research_toolkit.infrastructure.clock import WallClock
    from research_toolkit.infrastructure.filesystem_store import FilesystemStore
    from research_toolkit.infrastructure.jsonl_indexer import JsonlIndexer
    from research_toolkit.infrastructure.html_snapshotter import HtmlSnapshotter

    config = load_config()
    logger = ConsoleLogger()
    clock = WallClock()
    store = FilesystemStore("research")
    store.ensure_dirs()
    indexer = JsonlIndexer("research/library.jsonl")
    snapshotter = HtmlSnapshotter()

    # Search provider (pick first available)
    search_provider = None
    if config.get("BRAVE_API_KEY"):
        from research_toolkit.infrastructure.web_search_provider import BraveSearchProvider
        search_provider = BraveSearchProvider(config["BRAVE_API_KEY"])  # type: ignore[arg-type]
    elif config.get("GOOGLE_API_KEY") and config.get("GOOGLE_CX"):
        from research_toolkit.infrastructure.web_search_provider import GoogleSearchProvider
        search_provider = GoogleSearchProvider(config["GOOGLE_API_KEY"], config["GOOGLE_CX"])  # type: ignore[arg-type]
    elif config.get("SERPAPI_KEY"):
        from research_toolkit.infrastructure.web_search_provider import SerpAPISearchProvider
        search_provider = SerpAPISearchProvider(config["SERPAPI_KEY"])  # type: ignore[arg-type]

    # ── LLM provider (Ollama-first, Gemini, then OpenAI fallback) ────
    preference = provider_override or config.get("LLM_PROVIDER", "auto")
    llm_provider = None
    llm_provider_name = "none"

    if preference in ("ollama", "auto"):
        from research_toolkit.infrastructure.ollama_provider import OllamaProvider

        ollama_host = config.get("OLLAMA_HOST") or OllamaProvider.DEFAULT_HOST
        if OllamaProvider.is_available(ollama_host):
            model = config.get("OLLAMA_MODEL") or "qwen2.5:3b"
            llm_provider = OllamaProvider(
                model=model,  # type: ignore[arg-type]
                host=ollama_host,  # type: ignore[arg-type]
            )
            llm_provider_name = f"ollama ({model})"
            logger.info(f"LLM: Ollama → {model}")
        elif preference == "ollama":
            logger.error("Ollama requested but daemon not reachable at " + str(ollama_host))

    if llm_provider is None and preference in ("gemini", "auto"):
        gemini_key = config.get("GEMINI_API_KEY")
        if gemini_key:
            from research_toolkit.infrastructure.gemini_provider import GeminiProvider

            gemini_model = config.get("GEMINI_MODEL") or "gemini-2.0-flash"
            llm_provider = GeminiProvider(
                api_key=gemini_key,
                model=gemini_model,
            )
            llm_provider_name = f"gemini ({gemini_model})"
            logger.info(f"LLM: Gemini → {gemini_model}")
        elif preference == "gemini":
            logger.error("Gemini requested but GEMINI_API_KEY not set in .env")

    if llm_provider is None and preference in ("openai", "auto"):
        if config.get("OPENAI_API_KEY"):
            from research_toolkit.infrastructure.openai_provider import OpenAIProvider

            llm_provider = OpenAIProvider(
                api_key=config["OPENAI_API_KEY"],  # type: ignore[arg-type]
                model=config.get("OPENAI_MODEL") or "gpt-4o-mini",  # type: ignore[arg-type]
            )
            llm_provider_name = f"openai ({config.get('OPENAI_MODEL', 'gpt-4o-mini')})"
            logger.info(f"LLM: OpenAI → {config.get('OPENAI_MODEL', 'gpt-4o-mini')}")

    return {
        "config": config,
        "logger": logger,
        "clock": clock,
        "store": store,
        "indexer": indexer,
        "snapshotter": snapshotter,
        "search_provider": search_provider,
        "llm_provider": llm_provider,
        "llm_provider_name": llm_provider_name,
    }


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------
def cmd_help(args: argparse.Namespace) -> None:
    if args.command:
        text = COMMAND_HELP.get(args.command)
        if text:
            print(text)
        else:
            print(f"Unknown command: {args.command}")
            print(HELP_TEXT)
    else:
        print(HELP_TEXT)


def cmd_spec(_args: argparse.Namespace) -> None:
    print(json.dumps(COMMAND_SPEC, indent=2))


def cmd_doctor(args: argparse.Namespace) -> None:
    c = _build_container(getattr(args, "provider", None))
    from research_toolkit.application.use_cases.doctor_checks import DoctorChecks

    uc = DoctorChecks(
        store=c["store"],
        indexer=c["indexer"],
        search_provider=c["search_provider"],
        llm_provider=c["llm_provider"],
        logger=c["logger"],
    )
    resp = uc.execute()
    presenters.present_doctor(resp, as_json=getattr(args, "json", False))


def cmd_search(args: argparse.Namespace) -> None:
    c = _build_container(getattr(args, "provider", None))
    if c["search_provider"] is None:
        print("ERROR: No search provider configured. Set a search API key in .env", file=sys.stderr)
        sys.exit(1)

    from research_toolkit.application.use_cases.run_search import RunSearch, RunSearchRequest

    uc = RunSearch(
        search_provider=c["search_provider"],
        snapshotter=c["snapshotter"],
        store=c["store"],
        indexer=c["indexer"],
        clock=c["clock"],
        logger=c["logger"],
    )
    req = RunSearchRequest(
        query=args.query,
        max_results=args.max,
        recency_days=_parse_recency(args.recency),
    )
    resp = uc.execute(req)
    presenters.present_search(resp, as_json=args.json)


def cmd_ingest(args: argparse.Namespace) -> None:
    c = _build_container(getattr(args, "provider", None))
    from research_toolkit.application.use_cases.ingest_resource import IngestResource, IngestRequest

    uc = IngestResource(
        snapshotter=c["snapshotter"],
        store=c["store"],
        indexer=c["indexer"],
        clock=c["clock"],
        logger=c["logger"],
    )
    resp = uc.execute(IngestRequest(path_or_url=args.path_or_url))
    presenters.present_ingest(resp.resource, resp.already_existed, as_json=args.json)


def cmd_summarize(args: argparse.Namespace) -> None:
    c = _build_container(getattr(args, "provider", None))
    if c["llm_provider"] is None:
        print(
            "ERROR: No LLM provider available.\n"
            "  • Start Ollama (ollama serve) for local inference, OR\n"
            "  • Set OPENAI_API_KEY in .env for cloud inference.",
            file=sys.stderr,
        )
        sys.exit(1)

    from research_toolkit.application.use_cases.summarize_resource import SummarizeResource, SummarizeRequest

    uc = SummarizeResource(
        store=c["store"],
        indexer=c["indexer"],
        llm=c["llm_provider"],
        logger=c["logger"],
    )
    resp = uc.execute(SummarizeRequest(resource_id=args.resource_id, format=args.format))
    presenters.present_summarize(resp, as_json=args.json)


def cmd_query(args: argparse.Namespace) -> None:
    c = _build_container(getattr(args, "provider", None))
    if c["llm_provider"] is None:
        print(
            "ERROR: No LLM provider available.\n"
            "  • Start Ollama (ollama serve) for local inference, OR\n"
            "  • Set OPENAI_API_KEY in .env for cloud inference.",
            file=sys.stderr,
        )
        sys.exit(1)

    from research_toolkit.application.use_cases.query_library import QueryLibrary, QueryRequest

    uc = QueryLibrary(
        store=c["store"],
        indexer=c["indexer"],
        llm=c["llm_provider"],
        search_provider=c["search_provider"] or _null_search_provider(),
        snapshotter=c["snapshotter"],
        clock=c["clock"],
        logger=c["logger"],
    )
    req = QueryRequest(question=args.question, top_k=args.topk, live=args.live)
    resp = uc.execute(req)
    presenters.present_query(resp, as_json=args.json)


def cmd_list(args: argparse.Namespace) -> None:
    c = _build_container(getattr(args, "provider", None))
    from research_toolkit.application.use_cases.list_resources import ListResources

    uc = ListResources(indexer=c["indexer"], logger=c["logger"])
    resp = uc.execute()
    presenters.present_list(resp, as_json=args.json)


def cmd_reindex(args: argparse.Namespace) -> None:
    """Rebuild library index and fix titles (e.g. after frontmatter fix)."""
    c = _build_container(getattr(args, "provider", None))
    from research_toolkit.application.use_cases.reindex import Reindex

    uc = Reindex(store=c["store"], indexer=c["indexer"], logger=c["logger"])
    result = uc.execute()

    if getattr(args, "json", False):
        print(json.dumps({
            "total": result.total,
            "titles_fixed": result.titles_fixed,
            "errors": result.errors,
        }, indent=2))
    else:
        print(f"Reindexed {result.total} resources. Titles fixed: {result.titles_fixed}.")
        if result.errors:
            for e in result.errors:
                print(f"  ERROR: {e}", file=sys.stderr)


def cmd_review(args: argparse.Namespace) -> None:
    """Review an artifact file with Gemini multimodal AI."""
    from research_toolkit.infrastructure.config import load_config
    from research_toolkit.infrastructure.gemini_multimodal_provider import GeminiMultimodalProvider
    from research_toolkit.infrastructure.logger import ConsoleLogger
    from research_toolkit.infrastructure.clock import WallClock
    from research_toolkit.infrastructure.filesystem_store import FilesystemStore
    from research_toolkit.application.use_cases.review_artifact import ReviewArtifact, ReviewRequest

    config = load_config()
    gemini_key = config.get("GEMINI_API_KEY")
    if not gemini_key:
        print(
            "ERROR: GEMINI_API_KEY not set.\n"
            "  The review command requires a Gemini API key.\n"
            "  Add GEMINI_API_KEY=... to your .env file.",
            file=sys.stderr,
        )
        sys.exit(1)

    model = getattr(args, "model", None) or config.get("GEMINI_MODEL") or "gemini-2.0-flash"
    logger = ConsoleLogger()
    clock = WallClock()
    store = FilesystemStore("research")
    store.ensure_dirs()

    llm = GeminiMultimodalProvider(api_key=gemini_key, model=model)

    uc = ReviewArtifact(llm=llm, store=store, clock=clock, logger=logger)
    req = ReviewRequest(
        artifact_path=args.path,
        rubric_path=getattr(args, "rubric", None),
        output_format=getattr(args, "format", "json"),
        model=model,
        thinking=getattr(args, "thinking", None),
    )

    resp = uc.execute(req)
    as_md = getattr(args, "format", "json") == "md" and not getattr(args, "json", False)
    presenters.present_review(resp, as_json=getattr(args, "json", False), as_md=as_md)


def cmd_models(args: argparse.Namespace) -> None:
    """List models available on the local Ollama instance."""
    from research_toolkit.infrastructure.ollama_provider import OllamaProvider
    from research_toolkit.infrastructure.config import load_config

    config = load_config()
    host = config.get("OLLAMA_HOST") or OllamaProvider.DEFAULT_HOST

    if not OllamaProvider.is_available(host):
        print(f"ERROR: Ollama is not reachable at {host}. Is the daemon running?", file=sys.stderr)
        sys.exit(1)

    models = OllamaProvider.list_models(host)
    if getattr(args, "json", False):
        print(json.dumps({"models": models, "host": host}, indent=2))
        return

    from rich.console import Console
    from rich.table import Table

    console = Console()
    console.print(f"\n[bold]Ollama models[/bold] ({host})\n")
    table = Table(show_lines=True)
    table.add_column("Name", style="cyan")
    table.add_column("Family")
    table.add_column("Params")
    table.add_column("Quant")
    table.add_column("Size")
    for m in models:
        table.add_row(m["name"], m["family"], m["params"], m["quant"], m["size"])
    console.print(table)


def cmd_show(args: argparse.Namespace) -> None:
    """Show metadata, content, or snippets for a stored resource."""
    c = _build_container(getattr(args, "provider", None))
    from research_toolkit.domain.value_objects import ResourceId

    rid = ResourceId(args.resource_id)
    store = c["store"]
    resource = store.load_resource(rid)
    if resource is None:
        print(f"ERROR: Resource {args.resource_id} not found.", file=sys.stderr)
        sys.exit(1)

    field = getattr(args, "field", "meta")
    as_json = getattr(args, "json", False)

    if field == "content":
        content = store.load_content(rid) or ""
        if as_json:
            print(json.dumps({"resource_id": str(rid), "content": content}))
        else:
            print(content)
    elif field == "snippets":
        snippets = store.load_snippets(rid)
        if as_json:
            print(json.dumps({"resource_id": str(rid), "snippets": snippets}, indent=2))
        else:
            if not snippets:
                print("No snippets stored for this resource.")
            for i, s in enumerate(snippets, 1):
                print(f"[{i}] {s}")
    else:
        data = resource.to_dict()
        if as_json:
            print(json.dumps(data, indent=2))
        else:
            from rich.console import Console
            console = Console()
            for k, v in data.items():
                console.print(f"  [bold]{k}:[/bold] {v}")


# ---------------------------------------------------------------------------
# Null search provider (for --live when no provider is set)
# ---------------------------------------------------------------------------
def _null_search_provider():
    from research_toolkit.application.ports import SearchProvider
    from research_toolkit.domain.entities import SearchResult

    class NullSearch(SearchProvider):
        def search(self, query: str, *, max_results: int = 10, recency_days: int | None = None) -> list[SearchResult]:
            return []

    return NullSearch()


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tool",
        description="Research Toolkit CLI",
        add_help=False,
    )
    sub = parser.add_subparsers(dest="command")

    # help
    p_help = sub.add_parser("help", add_help=False)
    p_help.add_argument("command", nargs="?", default=None)
    p_help.set_defaults(func=cmd_help)

    # spec
    p_spec = sub.add_parser("spec", add_help=False)
    p_spec.set_defaults(func=cmd_spec)

    # doctor
    p_doctor = sub.add_parser("doctor", add_help=False)
    p_doctor.add_argument("--json", action="store_true", default=False)
    p_doctor.add_argument("--provider", type=str, default=None, choices=["ollama", "gemini", "openai", "auto"])
    p_doctor.set_defaults(func=cmd_doctor)

    # models
    p_models = sub.add_parser("models", add_help=False)
    p_models.add_argument("--json", action="store_true", default=False)
    p_models.set_defaults(func=cmd_models)

    # search
    p_search = sub.add_parser("search", add_help=False)
    p_search.add_argument("query", type=str)
    p_search.add_argument("--recency", type=str, default=None)
    p_search.add_argument("--max", type=int, default=10)
    p_search.add_argument("--json", action="store_true", default=False)
    p_search.set_defaults(func=cmd_search)

    # ingest
    p_ingest = sub.add_parser("ingest", add_help=False)
    p_ingest.add_argument("path_or_url", type=str)
    p_ingest.add_argument("--json", action="store_true", default=False)
    p_ingest.set_defaults(func=cmd_ingest)

    # summarize
    p_summarize = sub.add_parser("summarize", add_help=False)
    p_summarize.add_argument("resource_id", type=str)
    p_summarize.add_argument("--format", type=str, default="md", choices=["md", "json"])
    p_summarize.add_argument("--json", action="store_true", default=False)
    p_summarize.add_argument("--provider", type=str, default=None, choices=["ollama", "gemini", "openai", "auto"])
    p_summarize.set_defaults(func=cmd_summarize)

    # query
    p_query = sub.add_parser("query", add_help=False)
    p_query.add_argument("question", type=str)
    p_query.add_argument("--topk", type=int, default=5)
    p_query.add_argument("--live", action="store_true", default=False)
    p_query.add_argument("--json", action="store_true", default=False)
    p_query.add_argument("--provider", type=str, default=None, choices=["ollama", "gemini", "openai", "auto"])
    p_query.set_defaults(func=cmd_query)

    # show
    p_show = sub.add_parser("show", add_help=False)
    p_show.add_argument("resource_id", type=str)
    p_show.add_argument("--field", type=str, default="meta", choices=["meta", "content", "snippets"])
    p_show.add_argument("--json", action="store_true", default=False)
    p_show.set_defaults(func=cmd_show)

    # list
    p_list = sub.add_parser("list", add_help=False)
    p_list.add_argument("--json", action="store_true", default=False)
    p_list.set_defaults(func=cmd_list)

    # reindex
    p_reindex = sub.add_parser("reindex", add_help=False)
    p_reindex.add_argument("--json", action="store_true", default=False)
    p_reindex.set_defaults(func=cmd_reindex)

    # review
    p_review = sub.add_parser("review", add_help=False)
    p_review.add_argument("path", type=str)
    p_review.add_argument("--rubric", type=str, default=None)
    p_review.add_argument("--format", type=str, default="json", choices=["json", "md"])
    p_review.add_argument("--model", type=str, default=None)
    p_review.add_argument("--thinking", type=str, default=None, choices=["high", "low"])
    p_review.add_argument("--json", action="store_true", default=False)
    p_review.set_defaults(func=cmd_review)

    return parser


def run_cli(argv: list[str] | None = None) -> None:
    """Parse args and dispatch to the appropriate command handler."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        print(HELP_TEXT)
        return

    if hasattr(args, "func"):
        try:
            args.func(args)
        except Exception as exc:
            from research_toolkit.infrastructure.config import redact_secrets
            print(f"ERROR: {redact_secrets(str(exc))}", file=sys.stderr)
            sys.exit(1)
    else:
        print(HELP_TEXT)
