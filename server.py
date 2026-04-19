from __future__ import annotations

import importlib.util
import json
import os
import sys
from email import policy
from email.parser import BytesParser
from functools import lru_cache
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ara_sdk import AraClient


PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = PROJECT_ROOT / "web"
APP_SCRIPT = PROJECT_ROOT / "app.py"
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from voice_research_agent.project_store import ProjectStore, summarize_project
from voice_research_agent.research import StarterResearcher
from voice_research_agent.workflows import (
    add_manual_memory,
    contradiction_report,
    generate_daily_brief,
    ingest_source,
)


DEFAULT_AGENT_ID = "voice-research-agent"
TEXT_FILE_SUFFIXES = {
    ".css",
    ".csv",
    ".html",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".py",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
MAX_ATTACHMENT_BYTES = 32768
MAX_ATTACHMENTS = 6
STORE = ProjectStore()


@lru_cache(maxsize=1)
def load_manifest() -> dict[str, Any]:
    if not APP_SCRIPT.exists():
        raise RuntimeError(f"Could not resolve Ara manifest from {APP_SCRIPT}")
    spec = importlib.util.spec_from_file_location("voice_research_frontend_app", APP_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load Ara app from {APP_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    automation = getattr(module, "automation", None)
    app = getattr(module, "app", None)
    manifest = None
    if app is not None and hasattr(app, "manifest"):
        manifest = getattr(app, "manifest")
    elif automation is not None and hasattr(automation, "app") and hasattr(automation.app, "manifest"):
        manifest = getattr(automation.app, "manifest")
    if manifest is None:
        raise RuntimeError("app.py must expose `automation = ara.Automation(...)`")
    if not isinstance(manifest, dict):
        raise RuntimeError("Could not resolve Ara manifest from app.py")
    return manifest


def _is_text_attachment(filename: str, content_type: str) -> bool:
    suffix = Path(filename or "").suffix.lower()
    return suffix in TEXT_FILE_SUFFIXES or content_type.startswith("text/") or content_type in {
        "application/json",
        "application/xml",
        "application/javascript",
    }


def _extract_attachment_text(raw_bytes: bytes, filename: str, content_type: str) -> dict[str, Any]:
    clipped = len(raw_bytes) > MAX_ATTACHMENT_BYTES
    snippet = raw_bytes[:MAX_ATTACHMENT_BYTES]
    try:
        text = snippet.decode("utf-8")
    except UnicodeDecodeError:
        text = snippet.decode("utf-8", errors="replace")
    text = text.strip()
    if not text:
        text = "[Attachment was empty after decoding.]"
    return {
        "filename": filename,
        "content_type": content_type or "application/octet-stream",
        "size_bytes": len(raw_bytes),
        "is_text": _is_text_attachment(filename, content_type),
        "text_preview": text,
        "clipped": clipped,
    }


def _normalize_attachments(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in files[:MAX_ATTACHMENTS]:
        filename = str(item.get("filename") or "attachment").strip() or "attachment"
        content_type = str(item.get("content_type") or "application/octet-stream").strip()
        raw_bytes = item.get("bytes")
        if not isinstance(raw_bytes, (bytes, bytearray)):
            continue
        normalized.append(_extract_attachment_text(bytes(raw_bytes), filename, content_type))
    return normalized


def _compose_prompt(prompt: str, attachments: list[dict[str, Any]], project: dict[str, Any] | None = None) -> str:
    sections = []
    if project:
        sections.extend(
            [
                f"Project: {project.get('name')}",
                f"Description: {project.get('description') or 'No description provided.'}",
            ]
        )
        recent_papers = [paper for paper in project.get("papers", []) if isinstance(paper, dict)][-3:]
        if recent_papers:
            sections.append(
                "Recent project papers:\n"
                + "\n".join(
                    f"- {paper.get('title')}: {((paper.get('extraction') or {}).get('claim') or '').strip()}"
                    for paper in reversed(recent_papers)
                )
            )
        recent_memories = [item for item in project.get("memories", []) if isinstance(item, dict)][-4:]
        if recent_memories:
            sections.append(
                "Project memory:\n"
                + "\n".join(f"- {str(item.get('content') or '').strip()}" for item in reversed(recent_memories))
            )
    sections.append(prompt.strip())

    if attachments:
        attachment_lines = ["Attached files:"]
        for attachment in attachments:
            attachment_lines.append(
                f"- {attachment['filename']} ({attachment['content_type']}, {attachment['size_bytes']} bytes)"
            )
            if attachment["is_text"]:
                attachment_lines.append(attachment["text_preview"])
            else:
                attachment_lines.append("Binary or unsupported preview format. Use filename and type as context.")
            if attachment["clipped"]:
                attachment_lines.append("Note: content preview truncated for size.")
        sections.append("\n".join(attachment_lines))

    return "\n\n".join(section for section in sections if section).strip()


def _looks_like_generic_fallback(output_text: str) -> bool:
    lowered = output_text.lower()
    markers = (
        "there was an issue generating the research brief",
        "it seems there was an issue generating the research brief",
        "there was an issue retrieving the research information",
        "it seems there was an issue retrieving the research information",
        "however, i can provide",
        "however, i can still provide",
        "please provide a concise research prompt",
        "please provide a research prompt",
        "please provide a prompt",
        "what specific topic or question",
    )
    return any(marker in lowered for marker in markers)


def _markdown_list(title: str, items: list[str]) -> str:
    lines = [f"### {title}"]
    if not items:
        lines.append("1. None yet.")
        return "\n".join(lines)
    for index, item in enumerate(items, start=1):
        lines.append(f"{index}. {item}")
    return "\n".join(lines)


def build_ingest_markdown(paper: dict[str, Any], comparisons: list[dict[str, Any]]) -> str:
    extraction = paper.get("extraction") if isinstance(paper.get("extraction"), dict) else {}
    project_relation = paper.get("project_relation") if isinstance(paper.get("project_relation"), dict) else {}
    sections = [
        "### Paper Intake",
        f"Stored **{paper.get('title')}** as a {paper.get('source_type')} source.",
        "",
        "### Structured Extraction",
        f"1. **Claim**: {extraction.get('claim') or 'Not captured yet.'}",
        f"2. **Evidence**: {extraction.get('evidence') or 'Not captured yet.'}",
        f"3. **Gap**: {extraction.get('gap') or 'Not captured yet.'}",
        f"4. **Limitation**: {extraction.get('limitation') or 'Not captured yet.'}",
        f"5. **Relevance to project**: {extraction.get('relevance_to_project') or 'Not captured yet.'}",
        "",
        "### Project Fit",
        f"{str(project_relation.get('relation') or 'unclear').title()}: {project_relation.get('reasoning') or 'No reasoning available.'}",
    ]
    if comparisons:
        sections.extend(["", "### Cross-Paper Comparisons"])
        for index, comparison in enumerate(comparisons[:4], start=1):
            sections.append(
                f"{index}. **{str(comparison.get('relation') or 'unclear').title()}** vs "
                f"{comparison.get('other_paper_title')}: {comparison.get('reasoning')}"
            )
    return "\n".join(sections)


def build_compare_markdown(project: dict[str, Any], comparisons: list[dict[str, Any]]) -> str:
    if not comparisons:
        return "### Comparison Review\n1. Add at least two papers to compare project evidence."
    lines = [
        "### Comparison Review",
        f"Latest project evidence for **{project.get('name')}** compared against stored papers:",
    ]
    for index, comparison in enumerate(comparisons[:6], start=1):
        lines.append(
            f"{index}. **{str(comparison.get('relation') or 'unclear').title()}** between "
            f"{comparison.get('paper_title')} and {comparison.get('other_paper_title')}: {comparison.get('reasoning')}"
        )
    return "\n".join(lines)


def build_contradiction_markdown(report: dict[str, Any]) -> str:
    lines = [
        "### Contradiction Finder",
        report.get("summary") or "No contradictions yet.",
    ]
    for index, item in enumerate(report.get("items", []), start=1):
        lines.append(
            f"{index}. **{item.get('paper')}** vs **{item.get('other_paper')}**: {item.get('reasoning')}"
        )
    return "\n".join(lines)


def build_brief_markdown(brief: dict[str, Any]) -> str:
    sections = [
        "### Daily What Matters Brief",
        brief.get("summary") or "No summary generated.",
        "",
        _markdown_list("What Matters", [str(item) for item in brief.get("what_matters", [])]),
        "",
        _markdown_list(
            "Actionable Next Steps",
            [str(item) for item in brief.get("actionable_next_steps", [])],
        ),
        "",
        _markdown_list(
            "Unresolved Questions",
            [str(item) for item in brief.get("unresolved_questions", [])],
        ),
    ]
    return "\n".join(sections)


def run_prompt(
    prompt: str,
    attachments: list[dict[str, Any]],
    project: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_attachments = _normalize_attachments(attachments)
    composed_prompt = _compose_prompt(prompt, normalized_attachments, project=project)
    used_local_fallback = False
    raw_result: dict[str, Any] = {}
    output_text = ""
    run_error = ""

    try:
        manifest = load_manifest()
        client = AraClient.from_env(manifest=manifest, cwd=str(PROJECT_ROOT))
        raw_result = client.run(
            agent_id=os.getenv("ARA_AGENT_ID", DEFAULT_AGENT_ID).strip() or DEFAULT_AGENT_ID,
            input_payload={
                "message": composed_prompt,
                "prompt": composed_prompt,
                "query": composed_prompt,
                "transcript": composed_prompt,
                "channel": "web-ui",
                "source": "local-frontend",
                "project_name": project.get("name") if project else None,
                "attachments": normalized_attachments,
            },
        )
        if isinstance(raw_result, dict):
            result = raw_result.get("result") if isinstance(raw_result.get("result"), dict) else {}
            output_text = str(result.get("output_text") or "").strip()
        if not output_text or _looks_like_generic_fallback(output_text):
            raise RuntimeError("Ara returned a generic fallback response.")
    except Exception as exc:  # noqa: BLE001
        run_error = str(exc)
        used_local_fallback = True
        output_text = StarterResearcher().run(prompt).to_markdown()

    return {
        "ok": True,
        "used_local_fallback": used_local_fallback,
        "output_text": output_text,
        "raw_result": raw_result,
        "run_error": run_error,
        "attachments": normalized_attachments,
    }


def _parse_json_request(body: str) -> dict[str, Any]:
    payload = json.loads(body or "{}")
    if not isinstance(payload, dict):
        return {}
    return payload


def _parse_multipart_request(handler: SimpleHTTPRequestHandler, body: bytes) -> dict[str, Any]:
    content_type = handler.headers.get("Content-Type", "")
    header_bytes = (
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body
    )
    message = BytesParser(policy=policy.default).parsebytes(header_bytes)

    payload: dict[str, Any] = {}
    files: list[dict[str, Any]] = []
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        field_name = str(part.get_param("name", header="content-disposition") or "").strip()
        filename = part.get_filename()
        raw_bytes = part.get_payload(decode=True) or b""
        item_content_type = part.get_content_type()
        if filename:
            files.append(
                {
                    "filename": filename,
                    "content_type": item_content_type,
                    "bytes": raw_bytes,
                }
            )
        elif field_name:
            payload[field_name] = raw_bytes.decode("utf-8", errors="replace")
    payload["files"] = files
    return payload


def _read_request_payload(handler: SimpleHTTPRequestHandler) -> dict[str, Any]:
    content_length = int(handler.headers.get("Content-Length", "0") or "0")
    body_bytes = handler.rfile.read(content_length)
    content_type = handler.headers.get("Content-Type", "")
    if content_type.startswith("multipart/form-data"):
        return _parse_multipart_request(handler, body_bytes)
    return _parse_json_request(body_bytes.decode("utf-8", errors="replace"))


def _project_or_404(project_id: str) -> dict[str, Any]:
    project = STORE.get_project(project_id)
    if project is None:
        raise KeyError(f"Project {project_id} was not found.")
    return project


def _save_project(project: dict[str, Any]) -> dict[str, Any]:
    return STORE.update_project(str(project.get("id") or ""), project)


def _coerce_files(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return payload.get("files") if isinstance(payload.get("files"), list) else []


class VoiceResearchHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        segments = [segment for segment in parsed.path.split("/") if segment]
        if parsed.path == "/":
            self.path = "/index.html"
            super().do_GET()
            return

        if parsed.path == "/api/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "app_script": str(APP_SCRIPT),
                    "frontend_dir": str(FRONTEND_DIR),
                    "project_count": len(STORE.list_projects()),
                },
            )
            return

        if segments == ["api", "projects"]:
            self._send_json(HTTPStatus.OK, {"ok": True, "projects": STORE.list_projects()})
            return

        if len(segments) == 3 and segments[:2] == ["api", "projects"]:
            try:
                project = _project_or_404(segments[2])
                self._send_json(HTTPStatus.OK, {"ok": True, "project": project, "summary": summarize_project(project)})
            except KeyError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": str(exc)})
            return

        if len(segments) == 4 and segments[:2] == ["api", "projects"] and segments[3] == "contradictions":
            try:
                project = _project_or_404(segments[2])
                report = contradiction_report(project)
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "project": project,
                        "summary": summarize_project(project),
                        "contradictions": report,
                        "output_text": build_contradiction_markdown(report),
                    },
                )
            except KeyError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": str(exc)})
            return

        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        segments = [segment for segment in parsed.path.split("/") if segment]

        try:
            if parsed.path == "/api/research":
                payload = _read_request_payload(self)
                prompt = str(payload.get("prompt") or "").strip()
                if not prompt:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Prompt is required."})
                    return
                response = run_prompt(prompt, _coerce_files(payload))
                self._send_json(HTTPStatus.OK, response)
                return

            if segments == ["api", "projects"]:
                payload = _read_request_payload(self)
                name = str(payload.get("name") or "").strip()
                description = str(payload.get("description") or "").strip()
                if not name:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Project name is required."})
                    return
                project = STORE.create_project(name, description)
                self._send_json(HTTPStatus.CREATED, {"ok": True, "project": project, "summary": summarize_project(project)})
                return

            if len(segments) == 4 and segments[:2] == ["api", "projects"]:
                project_id = segments[2]
                action = segments[3]
                project = _project_or_404(project_id)
                payload = _read_request_payload(self)

                if action == "ingest":
                    title = str(payload.get("title") or "").strip()
                    pasted_text = str(payload.get("pasted_text") or payload.get("text") or "").strip()
                    link = str(payload.get("link") or "").strip()
                    transcript = str(payload.get("transcript") or "").strip()
                    attachments = _normalize_attachments(_coerce_files(payload))
                    if not any([pasted_text, link, transcript, attachments]):
                        self._send_json(
                            HTTPStatus.BAD_REQUEST,
                            {"ok": False, "error": "Provide pasted text, a link, a transcript, or an attachment."},
                        )
                        return
                    paper, comparisons, memories = ingest_source(
                        project,
                        title=title,
                        pasted_text=pasted_text,
                        link=link,
                        transcript=transcript,
                        attachments=attachments,
                    )
                    project.setdefault("papers", []).append(paper)
                    project.setdefault("comparisons", []).extend(comparisons)
                    project.setdefault("memories", []).extend(memories)
                    project = _save_project(project)
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "ok": True,
                            "result_type": "ingest",
                            "project": project,
                            "summary": summarize_project(project),
                            "paper": paper,
                            "comparisons": comparisons,
                            "new_memories": memories,
                            "output_text": build_ingest_markdown(paper, comparisons),
                        },
                    )
                    return

                if action == "compare":
                    papers = [paper for paper in project.get("papers", []) if isinstance(paper, dict)]
                    if len(papers) < 2:
                        self._send_json(
                            HTTPStatus.BAD_REQUEST,
                            {"ok": False, "error": "Add at least two papers before comparing project evidence."},
                        )
                        return
                    latest_paper = papers[-1]
                    comparisons = [
                        item
                        for item in (project.get("comparisons") if isinstance(project.get("comparisons"), list) else [])
                        if str(item.get("paper_id") or "") == str(latest_paper.get("id") or "")
                    ]
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "ok": True,
                            "result_type": "compare",
                            "project": project,
                            "summary": summarize_project(project),
                            "paper": latest_paper,
                            "comparisons": comparisons,
                            "output_text": build_compare_markdown(project, comparisons),
                        },
                    )
                    return

                if action == "brief":
                    brief = generate_daily_brief(project)
                    project.setdefault("briefs", []).append(brief)
                    project = _save_project(project)
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "ok": True,
                            "result_type": "brief",
                            "project": project,
                            "summary": summarize_project(project),
                            "brief": brief,
                            "output_text": build_brief_markdown(brief),
                        },
                    )
                    return

                if action == "memory":
                    content = str(payload.get("content") or "").strip()
                    if not content:
                        self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Memory content is required."})
                        return
                    memory = add_manual_memory(project, content)
                    project.setdefault("memories", []).append(memory)
                    project = _save_project(project)
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "ok": True,
                            "result_type": "memory",
                            "project": project,
                            "summary": summarize_project(project),
                            "memory": memory,
                            "output_text": f"### Memory Saved\n1. {memory.get('content')}",
                        },
                    )
                    return

                if action == "ask":
                    prompt = str(payload.get("prompt") or "").strip()
                    if not prompt:
                        self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Prompt is required."})
                        return
                    response = run_prompt(prompt, _coerce_files(payload), project=project)
                    response["project"] = project
                    response["summary"] = summarize_project(project)
                    response["result_type"] = "ask"
                    self._send_json(HTTPStatus.OK, response)
                    return

            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Route not found."})
        except json.JSONDecodeError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Invalid JSON body."})
        except KeyError as exc:
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    host = "127.0.0.1"
    port = int(os.getenv("PORT", "8000") or "8000")
    server = ThreadingHTTPServer((host, port), VoiceResearchHandler)
    print(f"Voice Research Agent UI running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
