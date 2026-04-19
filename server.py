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

from voice_research_agent.research import StarterResearcher


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
        preview = _extract_attachment_text(bytes(raw_bytes), filename, content_type)
        normalized.append(preview)
    return normalized


def _compose_prompt(prompt: str, attachments: list[dict[str, Any]]) -> str:
    if not attachments:
        return prompt.strip()

    sections = [prompt.strip(), "", "Attached files:"]
    for attachment in attachments:
        header = (
            f"- {attachment['filename']} ({attachment['content_type']}, "
            f"{attachment['size_bytes']} bytes)"
        )
        sections.append(header)
        if attachment["is_text"]:
            sections.append(attachment["text_preview"])
        else:
            sections.append("Binary or unsupported preview format. Use filename and type as context.")
        if attachment["clipped"]:
            sections.append("Note: content preview truncated for size.")
        sections.append("")
    return "\n".join(section for section in sections if section is not None).strip()


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


def run_prompt(prompt: str, attachments: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_attachments = _normalize_attachments(attachments)
    composed_prompt = _compose_prompt(prompt, normalized_attachments)
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
        content_type = part.get_content_type()
        if filename:
            files.append(
                {
                    "filename": filename,
                    "content_type": content_type,
                    "bytes": raw_bytes,
                }
            )
        elif field_name:
            payload[field_name] = raw_bytes.decode("utf-8", errors="replace")
    payload["files"] = files
    return payload


class VoiceResearchHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.path = "/index.html"
        elif parsed.path == "/api/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "app_script": str(APP_SCRIPT),
                    "frontend_dir": str(FRONTEND_DIR),
                },
            )
            return
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/research":
            self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Route not found."})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            body_bytes = self.rfile.read(content_length)
            content_type = self.headers.get("Content-Type", "")
            if content_type.startswith("multipart/form-data"):
                payload = _parse_multipart_request(self, body_bytes)
            else:
                payload = _parse_json_request(body_bytes.decode("utf-8", errors="replace"))

            prompt = str(payload.get("prompt") or "").strip()
            if not prompt:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Prompt is required."})
                return

            response = run_prompt(prompt, payload.get("files") if isinstance(payload.get("files"), list) else [])
            self._send_json(HTTPStatus.OK, response)
        except json.JSONDecodeError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Invalid JSON body."})
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
