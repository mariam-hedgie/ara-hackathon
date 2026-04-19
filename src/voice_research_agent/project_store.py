from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
STORE_PATH = DATA_DIR / "research_workspace.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def summarize_project(project: dict[str, Any]) -> dict[str, Any]:
    papers = project.get("papers") if isinstance(project.get("papers"), list) else []
    memories = project.get("memories") if isinstance(project.get("memories"), list) else []
    contradictions = [
        item
        for item in (project.get("comparisons") if isinstance(project.get("comparisons"), list) else [])
        if str(item.get("relation") or "") == "contradict"
    ]
    briefs = project.get("briefs") if isinstance(project.get("briefs"), list) else []
    return {
        "id": project.get("id"),
        "name": project.get("name"),
        "description": project.get("description") or "",
        "created_at": project.get("created_at"),
        "updated_at": project.get("updated_at"),
        "paper_count": len(papers),
        "memory_count": len(memories),
        "contradiction_count": len(contradictions),
        "brief_count": len(briefs),
    }


class ProjectStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or STORE_PATH

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"projects": []}
        try:
            parsed = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"projects": []}
        if not isinstance(parsed, dict):
            return {"projects": []}
        projects = parsed.get("projects")
        if not isinstance(projects, list):
            parsed["projects"] = []
        return parsed

    def save(self, data: dict[str, Any]) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp_path.replace(self.path)

    def list_projects(self) -> list[dict[str, Any]]:
        data = self.load()
        projects = data.get("projects") if isinstance(data.get("projects"), list) else []
        summaries = [summarize_project(project) for project in projects if isinstance(project, dict)]
        return sorted(summaries, key=lambda item: str(item.get("updated_at") or ""), reverse=True)

    def create_project(self, name: str, description: str = "") -> dict[str, Any]:
        data = self.load()
        project = {
            "id": new_id("project"),
            "name": name.strip(),
            "description": description.strip(),
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "papers": [],
            "comparisons": [],
            "memories": [],
            "briefs": [],
        }
        projects = data.get("projects") if isinstance(data.get("projects"), list) else []
        projects.append(project)
        data["projects"] = projects
        self.save(data)
        return project

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        data = self.load()
        for project in data.get("projects", []):
            if isinstance(project, dict) and str(project.get("id") or "") == project_id:
                return project
        return None

    def update_project(self, project_id: str, project: dict[str, Any]) -> dict[str, Any]:
        data = self.load()
        projects = data.get("projects") if isinstance(data.get("projects"), list) else []
        updated_projects: list[dict[str, Any]] = []
        updated = False
        for existing in projects:
            if isinstance(existing, dict) and str(existing.get("id") or "") == project_id:
                project["updated_at"] = now_iso()
                updated_projects.append(project)
                updated = True
            else:
                updated_projects.append(existing)
        if not updated:
            raise KeyError(f"Project {project_id} not found.")
        data["projects"] = updated_projects
        self.save(data)
        return project
