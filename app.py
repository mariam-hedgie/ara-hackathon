"""Ara orchestration entrypoint for the Research Brain demo."""

import sys
from pathlib import Path

import ara_sdk as ara

# Ensure local tool modules resolve when Ara loads this file directly.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.memory import retrieve_notes, retrieve_project_notes, store_note, store_project_note
from tools.paper_parser import parse_text
from tools.research_manager import (
    compare_paper_to_project,
    generate_morning_brief,
    ingest_paper,
    plan_submission,
)
from tools.reasoning import generate_insight
from tools.transcribe import transcribe_audio


@ara.tool
def run_pipeline() -> dict:
    """Run the end-to-end research pipeline and return structured demo output."""
    transcript = transcribe_audio() or {}
    transcript_text = str(transcript.get("text") or "").strip()

    parsed = parse_text(text=transcript_text) or {}
    reasoning = generate_insight(parsed=parsed) or {}

    # Persist the full pipeline result so the demo can show memory growth.
    note = {
        "transcript": transcript_text,
        "parsed": parsed,
        "reasoning": reasoning,
    }
    store_note(note)

    memory = retrieve_notes() or []
    return {
        "parsed": parsed,
        "reasoning": reasoning,
        "memory_size": len(memory),
    }


app = ara.Automation(
    "research-brain",
    system_instructions=(
        "You are a scientific research assistant. Prefer concise, structured output. "
        "Use run_pipeline for transcript-based research capture. Use ingest_paper when the user "
        "pastes a new paper or abstract. Use compare_paper_to_project to judge whether a paper "
        "supports or contradicts an existing project. Use plan_submission for venue planning and "
        "generate_morning_brief for project summaries and todos. Include one key limitation or "
        "counterpoint when giving research advice."
    ),
    tools=[
        transcribe_audio,
        parse_text,
        generate_insight,
        store_note,
        retrieve_notes,
        store_project_note,
        retrieve_project_notes,
        ingest_paper,
        compare_paper_to_project,
        plan_submission,
        generate_morning_brief,
        run_pipeline,
    ],
)
