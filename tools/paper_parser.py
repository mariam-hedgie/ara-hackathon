"""Minimal structured parser for research transcript text."""

import re

import ara_sdk as ara


def _first_sentence(text: str) -> str:
    """Return the first sentence-like segment from the input text."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)
    return parts[0].strip() if parts and parts[0].strip() else text.strip()


@ara.tool
def parse_text(text: str) -> dict:
    """Convert raw research text into a small structured representation."""
    content = str(text or "").strip()
    if not content:
        return {
            "claim": "",
            "evidence": "",
            "gap": "No transcript content was provided.",
            "questions": ["What is the main research claim?"],
        }

    first_sentence = _first_sentence(content)
    lower_content = content.lower()

    if "but" in lower_content:
        gap = "The transcript describes a tradeoff or unresolved limitation."
    elif "however" in lower_content:
        gap = "The transcript signals a limitation that needs clarification."
    else:
        gap = "The transcript does not state a clear limitation or open question."

    evidence = ""
    if any(token in lower_content for token in ("because", "data", "result", "study", "experiment")):
        evidence = first_sentence

    return {
        "claim": first_sentence,
        "evidence": evidence,
        "gap": gap,
        "questions": [
            "What evidence best supports this claim?",
            "What experiment would reduce the main uncertainty?",
        ],
    }
