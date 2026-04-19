from __future__ import annotations

import re
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib import error, request
from urllib.parse import urlparse

from voice_research_agent.project_store import new_id, now_iso


STOPWORDS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "using",
    "with",
    "your",
}
CONTRADICTION_AXES = [
    ({"edge", "offline", "ondevice", "local"}, {"cloud", "server", "hosted", "remote"}),
    ({"quantized", "tiny", "small", "lightweight"}, {"large", "heavy", "foundation"}),
    ({"wakeword", "wake", "alwayslistening"}, {"pushtotalk", "manual", "button"}),
    ({"privacy", "private"}, {"tracking", "surveillance", "centralized"}),
]


def split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if not normalized:
        return []
    parts = re.split(r"(?<=[.!?])\s+", normalized)
    return [part.strip() for part in parts if part.strip()]


def keyword_set(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z0-9]+", (text or "").lower())
    normalized: set[str] = set()
    for word in words:
        compact = word.replace("-", "")
        if len(compact) < 4 or compact in STOPWORDS:
            continue
        normalized.add(compact)
    return normalized


def choose_sentence(sentences: list[str], *, keywords: tuple[str, ...]) -> str:
    lowered_keywords = tuple(keyword.lower() for keyword in keywords)
    for sentence in sentences:
        lowered = sentence.lower()
        if any(keyword in lowered for keyword in lowered_keywords):
            return sentence
    return ""


def choose_sentence_by_priority(sentences: list[str], *, keyword_groups: tuple[tuple[str, ...], ...]) -> str:
    for keyword_group in keyword_groups:
        candidate = choose_sentence(sentences, keywords=keyword_group)
        if candidate:
            return candidate
    return ""


def build_title(
    *,
    title: str,
    link: str,
    source_type: str,
    transcript: str,
    raw_text: str,
    attachments: list[dict[str, Any]],
) -> str:
    if title.strip():
        return title.strip()
    if link.strip():
        parsed = urlparse(link.strip())
        tail = (parsed.path.rstrip("/").split("/")[-1] or parsed.netloc or "linked-source").replace("-", " ")
        return tail.strip().title() or "Linked Source"
    if attachments:
        filename = str(attachments[0].get("filename") or "Attached Source").strip()
        return Path(filename).stem.replace("-", " ").replace("_", " ").title()
    if transcript.strip():
        return "Voice Note"
    first_sentence = split_sentences(raw_text)
    if first_sentence:
        return first_sentence[0][:80]
    return f"{source_type.replace('_', ' ').title()} Source"


def infer_source_type(link: str, attachments: list[dict[str, Any]], transcript: str, raw_text: str) -> str:
    normalized_link = link.strip().lower()
    if transcript.strip():
        return "voice_note"
    if normalized_link:
        if "drive.google.com" in normalized_link:
            return "google_drive"
        if "github.com" in normalized_link:
            return "repo_link"
        return "link"
    if attachments:
        content_type = str(attachments[0].get("content_type") or "").lower()
        filename = str(attachments[0].get("filename") or "").lower()
        if filename.endswith(".pdf") or content_type == "application/pdf":
            return "pdf"
        if filename.endswith((".wav", ".mp3", ".m4a", ".ogg")) or content_type.startswith("audio/"):
            return "voice_note"
    return "text" if raw_text.strip() else "unknown"


def extract_attachment_text(attachments: list[dict[str, Any]]) -> str:
    previews: list[str] = []
    for attachment in attachments:
        if attachment.get("is_text") and attachment.get("text_preview"):
            previews.append(str(attachment["text_preview"]))
    return "\n\n".join(previews).strip()


def fetch_link_text(link: str) -> str:
    if not link.strip():
        return ""
    req = request.Request(
        link.strip(),
        headers={"User-Agent": "VoiceResearchAgent/0.1 (+https://ara.so)"},
    )
    try:
        with request.urlopen(req, timeout=8) as response:
            raw = response.read(65536)
            content_type = response.headers.get_content_type()
    except (error.URLError, ValueError):
        return ""

    if content_type == "application/pdf":
        return ""

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    if "html" in content_type:
        text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
        text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def build_relevance(project: dict[str, Any], title: str, raw_text: str) -> str:
    project_context = f"{project.get('name') or ''} {project.get('description') or ''}"
    shared = keyword_set(project_context) & keyword_set(f"{title} {raw_text}")
    if shared:
        return (
            "This source is relevant because it overlaps with the project focus on "
            f"{', '.join(sorted(shared)[:4])}."
        )
    return (
        "This source is directionally useful as background research, but it needs a clearer tie to "
        "the project's current scope."
    )


def extract_structured_insights(project: dict[str, Any], title: str, raw_text: str) -> dict[str, str]:
    sentences = split_sentences(raw_text)
    claim = sentences[0] if sentences else f"{title} frames a potentially useful idea for the project."
    evidence = (
        choose_sentence_by_priority(
            sentences[1:],
            keyword_groups=(
                ("result", "show", "found", "benchmark", "accuracy", "evidence"),
                ("latency", "because"),
            ),
        )
        or (sentences[1] if len(sentences) > 1 else "Evidence still needs to be validated with concrete benchmarks.")
    )
    gap = (
        choose_sentence_by_priority(
            sentences,
            keyword_groups=(
                ("however", "gap", "missing", "future work", "challenge"),
                ("open question", "unclear"),
            ),
        )
        or "A remaining gap is how this source translates into a concrete project decision or implementation step."
    )
    limitation = (
        choose_sentence_by_priority(
            sentences,
            keyword_groups=(
                ("limitation", "constraint", "network dependency", "small dataset"),
                ("cost", "tradeoff", "noise", "latency"),
            ),
        )
        or "The main limitation is that the source does not fully de-risk real-world deployment conditions yet."
    )
    relevance = build_relevance(project, title, raw_text)
    return {
        "claim": claim,
        "evidence": evidence,
        "gap": gap,
        "limitation": limitation,
        "relevance_to_project": relevance,
    }


def detect_relation(left_text: str, right_text: str) -> tuple[str, str]:
    left_keywords = keyword_set(left_text)
    right_keywords = keyword_set(right_text)
    overlap = left_keywords & right_keywords

    for positive_axis, negative_axis in CONTRADICTION_AXES:
        left_positive = bool(left_keywords & positive_axis)
        right_positive = bool(right_keywords & positive_axis)
        left_negative = bool(left_keywords & negative_axis)
        right_negative = bool(right_keywords & negative_axis)
        if (left_positive and right_negative) or (left_negative and right_positive):
            shared_context = ", ".join(sorted(overlap)[:4]) or "the same design area"
            return (
                "contradict",
                f"These sources push in different directions around {shared_context}.",
            )

    if len(overlap) >= 3:
        shared_context = ", ".join(sorted(overlap)[:4])
        return ("support", f"These sources reinforce each other around {shared_context}.")

    return ("unclear", "The overlap is weak, so the relationship needs more interpretation.")


def compare_to_project(project: dict[str, Any], extraction: dict[str, str]) -> dict[str, str]:
    project_context = f"{project.get('name') or ''} {project.get('description') or ''}"
    combined = " ".join(extraction.values())
    relation, reasoning = detect_relation(project_context, combined)
    return {"relation": relation, "reasoning": reasoning}


def compare_papers(project: dict[str, Any], paper: dict[str, Any], other_paper: dict[str, Any]) -> dict[str, Any]:
    left = " ".join(
        [
            paper.get("title") or "",
            paper.get("raw_text") or "",
            *(paper.get("extraction") or {}).values(),
        ]
    )
    right = " ".join(
        [
            other_paper.get("title") or "",
            other_paper.get("raw_text") or "",
            *(other_paper.get("extraction") or {}).values(),
        ]
    )
    relation, reasoning = detect_relation(left, right)
    return {
        "id": new_id("comparison"),
        "paper_id": paper.get("id"),
        "other_paper_id": other_paper.get("id"),
        "paper_title": paper.get("title"),
        "other_paper_title": other_paper.get("title"),
        "relation": relation,
        "reasoning": reasoning,
        "created_at": now_iso(),
    }


def build_memory_entries(paper: dict[str, Any]) -> list[dict[str, Any]]:
    extraction = paper.get("extraction") if isinstance(paper.get("extraction"), dict) else {}
    out: list[dict[str, Any]] = []
    for kind in ("claim", "gap", "relevance_to_project"):
        content = str(extraction.get(kind) or "").strip()
        if not content:
            continue
        out.append(
            {
                "id": new_id("memory"),
                "kind": kind,
                "paper_id": paper.get("id"),
                "paper_title": paper.get("title"),
                "content": content,
                "created_at": now_iso(),
            }
        )
    return out


def ingest_source(
    project: dict[str, Any],
    *,
    title: str,
    pasted_text: str,
    link: str,
    transcript: str,
    attachments: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    attachment_text = extract_attachment_text(attachments)
    linked_text = fetch_link_text(link) if link.strip() else ""
    raw_text = "\n\n".join(
        part for part in (pasted_text.strip(), transcript.strip(), attachment_text, linked_text) if part
    ).strip()
    source_type = infer_source_type(link, attachments, transcript, raw_text)
    resolved_title = build_title(
        title=title,
        link=link,
        source_type=source_type,
        transcript=transcript,
        raw_text=raw_text,
        attachments=attachments,
    )
    extraction = extract_structured_insights(project, resolved_title, raw_text)
    project_fit = compare_to_project(project, extraction)

    paper = {
        "id": new_id("paper"),
        "title": resolved_title,
        "source_type": source_type,
        "source_url": link.strip() or None,
        "raw_text": raw_text,
        "transcript": transcript.strip() or None,
        "attachments": attachments,
        "created_at": now_iso(),
        "extraction": extraction,
        "project_relation": project_fit,
    }

    comparisons: list[dict[str, Any]] = []
    for existing_paper in project.get("papers", []):
        if not isinstance(existing_paper, dict):
            continue
        comparisons.append(compare_papers(project, paper, existing_paper))
    memories = build_memory_entries(paper)
    return paper, comparisons, memories


def add_manual_memory(project: dict[str, Any], content: str, kind: str = "note") -> dict[str, Any]:
    return {
        "id": new_id("memory"),
        "kind": kind,
        "paper_id": None,
        "paper_title": None,
        "content": content.strip(),
        "created_at": now_iso(),
    }


def contradiction_report(project: dict[str, Any]) -> dict[str, Any]:
    contradictions = [
        comparison
        for comparison in (project.get("comparisons") if isinstance(project.get("comparisons"), list) else [])
        if str(comparison.get("relation") or "") == "contradict"
    ]
    grouped = []
    for item in contradictions:
        grouped.append(
            {
                "paper": item.get("paper_title"),
                "other_paper": item.get("other_paper_title"),
                "reasoning": item.get("reasoning"),
            }
        )
    return {
        "count": len(contradictions),
        "items": grouped,
        "summary": (
            "No major contradictions stored yet."
            if not grouped
            else f"Found {len(grouped)} stored contradictions that need follow-up."
        ),
    }


def generate_daily_brief(project: dict[str, Any]) -> dict[str, Any]:
    papers = [paper for paper in project.get("papers", []) if isinstance(paper, dict)]
    recent_papers = list(reversed(papers[-3:]))
    contradictions = contradiction_report(project)
    memories = [item for item in project.get("memories", []) if isinstance(item, dict)]
    recent_memories = list(reversed(memories[-4:]))

    what_matters = [
        f"{paper.get('title')}: {((paper.get('extraction') or {}).get('claim') or '').strip()}"
        for paper in recent_papers
        if (paper.get("extraction") or {}).get("claim")
    ][:3]
    if contradictions["count"]:
        what_matters.append(contradictions["summary"])

    actionable_next_steps = [
        f"Resolve gap from {paper.get('title')}: {((paper.get('extraction') or {}).get('gap') or '').strip()}"
        for paper in recent_papers
        if (paper.get("extraction") or {}).get("gap")
    ][:3]
    if not actionable_next_steps:
        actionable_next_steps.append("Ingest a new paper or repo link to refresh the project signal.")

    unresolved_questions = [
        f"{paper.get('title')}: {((paper.get('extraction') or {}).get('limitation') or '').strip()}"
        for paper in recent_papers
        if (paper.get("extraction") or {}).get("limitation")
    ][:3]

    if recent_memories:
        what_matters.append(f"Memory trend: {recent_memories[0].get('content')}")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return {
        "id": new_id("brief"),
        "created_at": now_iso(),
        "summary": (
            f"{timestamp} brief for {project.get('name')}: {len(papers)} papers tracked, "
            f"{contradictions['count']} contradictions, and {len(memories)} memory items."
        ),
        "what_matters": what_matters,
        "actionable_next_steps": actionable_next_steps,
        "unresolved_questions": unresolved_questions,
    }
