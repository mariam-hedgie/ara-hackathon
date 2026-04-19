"""In-process memory tools for the Research Brain demo."""

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


@ara.tool
def store_project_note(project: str, note: dict) -> str:
    """Store a note scoped to a research project."""
    project_name = str(project or "").strip() or "general"
    payload = dict(note or {})
    payload["project"] = project_name
    _NOTES.append(payload)
    return f"stored note for {project_name}"


@ara.tool
def retrieve_project_notes(project: str = "") -> list:
    """Return notes for one project, or all notes when no project is provided."""
    project_name = str(project or "").strip()
    if not project_name:
        return list(_NOTES)
    return [note for note in _NOTES if str(note.get("project") or "").strip() == project_name]
