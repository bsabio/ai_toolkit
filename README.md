# Research Toolkit

A CLI toolkit that enables AI agents to autonomously **search → store → summarize → query** web information with verifiable citations.

## Quick Start

```bash
# 1. Create .env from example
cp .env.example .env
# Edit .env and add your API keys

# 2. Install
pip install -e .

# 3. Verify setup
tool doctor

# 4. Search & store
tool search "latest advances in quantum computing" --max 5

# 5. List stored resources
tool list

# 6. Summarize a resource
tool summarize <resource_id>

# 7. Query your local library
tool query "What are the main challenges in quantum computing?"

# 8. Query with live search fallback
tool query "What happened today?" --live
```

## Commands

| Command | Description |
|---------|-------------|
| `tool help` | Show help for all commands |
| `tool help <cmd>` | Show help for a specific command |
| `tool spec` | Output machine-readable command spec (JSON) |
| `tool doctor` | Validate environment, storage, connectivity |
| `tool search "<query>"` | Search web, store results locally |
| `tool ingest <path_or_url>` | Ingest a local file or URL into library |
| `tool summarize <id>` | Summarize a stored resource with citations |
| `tool query "<question>"` | Answer from local library with citations |
| `tool list` | List all stored resources |
| `tool review <path>` | Multimodal artifact review via Gemini |

## Architecture

Clean Architecture (Uncle Bob):

```
domain/          Pure entities & value objects (no IO)
application/     Use cases & port interfaces
adapters/        CLI parsing & presenters
infrastructure/  OpenAI, web search, filesystem, indexer
```

Dependencies point inward: infrastructure → application → domain.

## Documentation

- [docs/COMMANDS.md](docs/COMMANDS.md) — Full CLI reference for every command
- [docs/AGENT_ONBOARDING.md](docs/AGENT_ONBOARDING.md) — Architecture guide for agents & contributors
```
