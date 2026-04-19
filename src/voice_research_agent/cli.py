from __future__ import annotations

import argparse

from voice_research_agent.pipeline import ResearchAgent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Voice Research Agent from the terminal.")
    parser.add_argument("--text", help="Optional typed prompt to skip interactive input.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    ResearchAgent().run(args.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
