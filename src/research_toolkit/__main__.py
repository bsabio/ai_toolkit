"""Entry point for the Research Toolkit CLI.

Usage:
    python -m research_toolkit <command> [args...]
    tool <command> [args...]          (after pip install -e .)
"""

from research_toolkit.adapters.cli import run_cli


def main() -> None:
    run_cli()


if __name__ == "__main__":
    main()
