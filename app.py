"""Ara orchestration entrypoint for the Research Brain demo."""

import ara_sdk as ara

from tools.memory import retrieve_notes, store_note
from tools.paper_parser import parse_text
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
        "You are a scientific research assistant. Prefer structured output and be concise. "
        "Use the run_pipeline tool to process research transcript input into parsed scientific "
        "components, a concise insight, and one key limitation or counterpoint. "
        "Keep responses brief, clear, and demo-friendly."
    ),
    tools=[
        transcribe_audio,
        parse_text,
        generate_insight,
        store_note,
        retrieve_notes,
        run_pipeline,
    ],
)
