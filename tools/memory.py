"""Simple in-process memory tools for the Research Brain demo."""

import ara_sdk as ara


_NOTES: list[dict] = []


@ara.tool
def store_note(note: dict) -> str:
    """Store a note in memory and return a short status message."""
    _NOTES.append(dict(note or {}))
    return f"stored note {_NOTES.__len__()}"


@ara.tool
def retrieve_notes() -> list:
    """Return all stored notes."""
    return list(_NOTES)
