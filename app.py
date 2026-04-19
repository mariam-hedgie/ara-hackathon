from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import ara_sdk as ara


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from voice_research_agent.research import StarterResearcher


researcher = StarterResearcher()


@ara.tool
def utc_now() -> dict:
    return {"utc_time": datetime.now(timezone.utc).isoformat()}


@ara.tool
def draft_research_brief(query: str) -> dict:
    """Generate a structured starter research response for a spoken query."""
    return researcher.run(query).to_dict()


@ara.tool
def answer_research_question(query: str) -> str:
    """Return the final user-facing research answer for a spoken or typed query."""
    return researcher.run(query).to_markdown()


@ara.tool
def draft_submission_summary() -> dict:
    """Return a concise project summary suitable for hackathon submission drafting."""
    return {
        "project_name": "Voice Research Agent",
        "one_liner": (
            "A voice-activated AI research assistant that turns spoken questions into "
            "structured findings and next-step recommendations."
        ),
        "highlights": [
            "Accepts natural spoken research prompts.",
            "Separates retrieval from synthesis for clearer answers.",
            "Designed for fast follow-up questions and iterative exploration.",
        ],
    }


automation = ara.Automation(
    "voice-research-agent",
    system_instructions=(
        "You are a voice research assistant. The active user request may arrive through run "
        "input fields such as message, prompt, query, or transcript. Treat that input as the "
        "user's current question. When you receive a research question, always call "
        "answer_research_question first using the actual user query text. Return that tool "
        "output directly with no preamble, no apology, and no mention of internal errors or "
        "tool failures. Never say phrases like 'It seems there was an issue', 'There was an "
        "issue generating the research brief', 'There was an issue retrieving the research "
        "information', or 'However, I can help'. Do not mention fallback behavior, missing "
        "retrieval, or tool problems. Return only the final research answer content. Use "
        "draft_submission_summary only when the user asks for pitch or submission copy. Use "
        "utc_now only when time context matters. If no question is present, ask the user for "
        "one concise research prompt."
    ),
    tools=[utc_now, draft_research_brief, answer_research_question, draft_submission_summary],
)

app = automation.app
