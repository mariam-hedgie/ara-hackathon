"""Higher-level research workflow tools for project-aware assistance."""

from datetime import date

import ara_sdk as ara

from tools.memory import retrieve_project_notes, store_project_note
from tools.paper_parser import parse_text
from tools.reasoning import generate_insight


def _normalize_text(value: str) -> str:
    return str(value or "").strip()


def _extract_claim(note: dict) -> str:
    parsed = note.get("parsed") if isinstance(note.get("parsed"), dict) else {}
    return _normalize_text(parsed.get("claim") or note.get("summary") or "")


def _classify_relationship(text: str, prior_claims: list[str]) -> tuple[str, str]:
    """Compare a new paper against prior claims with simple lexical overlap."""
    if not prior_claims:
        return (
            "insufficient_context",
            "There is not enough saved project context yet to decide support versus contradiction.",
        )

    lowered_text = text.lower()
    contradiction_markers = ("contradict", "conflict", "fails", "inconsistent", "no benefit", "does not replicate")
    if any(marker in lowered_text for marker in contradiction_markers):
        return (
            "contradicts",
            "The paper uses language that suggests a limitation, disagreement, or conflicting result.",
        )

    overlap_hits = 0
    for claim in prior_claims:
        claim_words = {word for word in claim.lower().split() if len(word) > 4}
        if claim_words and any(word in lowered_text for word in claim_words):
            overlap_hits += 1

    if overlap_hits:
        return (
            "supports",
            "The paper overlaps with existing project claims and does not signal an obvious contradiction.",
        )

    return (
        "mixed",
        "The paper does not clearly align or conflict with existing project notes based on the available text.",
    )


def _recent_project_questions(project_notes: list[dict], limit: int = 3) -> list[str]:
    questions: list[str] = []
    for note in reversed(project_notes):
        parsed = note.get("parsed") if isinstance(note.get("parsed"), dict) else {}
        raw_questions = parsed.get("questions") if isinstance(parsed.get("questions"), list) else []
        for question in raw_questions:
            question_text = _normalize_text(question)
            if question_text and question_text not in questions:
                questions.append(question_text)
            if len(questions) >= limit:
                return questions
    return questions


def _normalize_timeframe(timeframe: str) -> str:
    """Resolve relative timeframe text into a clearer demo-friendly label."""
    raw = _normalize_text(timeframe)
    if not raw:
        return "the upcoming cycle"

    lowered = raw.lower()
    if lowered == "next month":
        today = date.today()
        year = today.year + (1 if today.month == 12 else 0)
        month = 1 if today.month == 12 else today.month + 1
        return date(year, month, 1).strftime("%B %Y")
    return raw


@ara.tool
def ingest_paper(project: str, title: str, text: str) -> dict:
    """Parse a paper, generate insight, compare it with project memory, and store it."""
    project_name = _normalize_text(project) or "general"
    paper_title = _normalize_text(title) or "untitled paper"
    paper_text = _normalize_text(text)

    parsed = parse_text(text=paper_text) or {}
    reasoning = generate_insight(parsed=parsed) or {}
    existing_notes = retrieve_project_notes(project=project_name) or []
    prior_claims = [_extract_claim(note) for note in existing_notes if _extract_claim(note)]
    relationship, rationale = _classify_relationship(paper_text, prior_claims)

    note = {
        "type": "paper",
        "title": paper_title,
        "text": paper_text,
        "parsed": parsed,
        "reasoning": reasoning,
        "comparison": {
            "relationship": relationship,
            "rationale": rationale,
        },
    }
    store_project_note(project=project_name, note=note)

    return {
        "project": project_name,
        "title": paper_title,
        "parsed": parsed,
        "reasoning": reasoning,
        "comparison": {
            "relationship": relationship,
            "rationale": rationale,
            "project_note_count": len(existing_notes) + 1,
        },
    }


@ara.tool
def compare_paper_to_project(project: str, text: str, title: str = "") -> dict:
    """Compare a candidate paper against the saved direction of one project."""
    project_name = _normalize_text(project) or "general"
    paper_text = _normalize_text(text)
    paper_title = _normalize_text(title) or "candidate paper"

    project_notes = retrieve_project_notes(project=project_name) or []
    prior_claims = [_extract_claim(note) for note in project_notes if _extract_claim(note)]
    relationship, rationale = _classify_relationship(paper_text, prior_claims)

    return {
        "project": project_name,
        "title": paper_title,
        "relationship": relationship,
        "rationale": rationale,
        "reference_claims": prior_claims[:3],
        "project_note_count": len(project_notes),
    }


@ara.tool
def plan_submission(project: str, venue: str, timeframe: str = "") -> dict:
    """Generate a practical submission checklist from saved project context."""
    project_name = _normalize_text(project) or "general"
    venue_name = _normalize_text(venue) or "target venue"
    timeframe_text = _normalize_timeframe(timeframe)
    project_notes = retrieve_project_notes(project=project_name) or []
    open_questions = _recent_project_questions(project_notes)

    today = date.today().isoformat()
    checklist = [
        f"Confirm the {venue_name} author guidelines and submission category.",
        f"Turn the strongest project claim into a one-sentence positioning statement by {today}.",
        "Lock the main figure/table set and verify the evidence supports the claim.",
        "Resolve the top open methodological concern before final writing.",
        "Prepare abstract, related work, and limitation sections in parallel.",
        "Run a final formatting and coauthor review pass one week before submission.",
    ]

    risks = open_questions or [
        "The project memory does not yet contain explicit unresolved questions.",
    ]

    return {
        "project": project_name,
        "venue": venue_name,
        "timeframe": timeframe_text,
        "priority_actions": checklist,
        "open_risks": risks,
        "next_step": f"Create a dated internal checklist for {venue_name} and assign owners this week.",
    }


@ara.tool
def generate_morning_brief(project: str = "", field: str = "") -> dict:
    """Summarize saved research progress and near-term actions for the morning."""
    project_name = _normalize_text(project)
    field_name = _normalize_text(field)
    notes = retrieve_project_notes(project=project_name) or []

    titles: list[str] = []
    next_steps: list[str] = []
    for note in reversed(notes):
        title = _normalize_text(note.get("title") or note.get("transcript") or "")
        reasoning = note.get("reasoning") if isinstance(note.get("reasoning"), dict) else {}
        next_step = _normalize_text(reasoning.get("next_step") or "")
        if title and title not in titles:
            titles.append(title)
        if next_step and next_step not in next_steps:
            next_steps.append(next_step)
        if len(titles) >= 3 and len(next_steps) >= 3:
            break

    summary_lines = [
        f"Tracked notes: {len(notes)}.",
        f"Active project: {project_name or 'all projects'}.",
    ]
    if field_name:
        summary_lines.append(
            f"Field focus: {field_name}. This brief summarizes saved research memory rather than external news."
        )

    return {
        "project": project_name or "all-projects",
        "field": field_name,
        "summary": " ".join(summary_lines),
        "recent_items": titles[:3],
        "todos": next_steps[:3],
        "note": "This morning brief is generated from stored project notes, not live web updates.",
    }
