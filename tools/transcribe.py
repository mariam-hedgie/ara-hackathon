import os
from pathlib import Path

import ara_sdk as ara
from openai import OpenAI


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_AUDIO_PATH = _PROJECT_ROOT / "demo" / "sample_audio.wav"
_DEFAULT_MODEL = "gpt-4o-mini-transcribe"
_SUPPORTED_AUDIO_SUFFIXES = {
    ".flac",
    ".m4a",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpga",
    ".ogg",
    ".wav",
    ".webm",
}


def _resolve_audio_path(audio_path: str) -> Path:
    requested_path = audio_path.strip() or os.getenv("TRANSCRIBE_AUDIO_PATH", "").strip()

    if requested_path:
        candidate = Path(requested_path).expanduser()
        if not candidate.is_absolute():
            candidate = (_PROJECT_ROOT / candidate).resolve()
        else:
            candidate = candidate.resolve()
    else:
        candidate = _DEFAULT_AUDIO_PATH

    if not candidate.exists():
        raise FileNotFoundError(f"Audio file not found: {candidate}")

    if candidate.suffix.lower() not in _SUPPORTED_AUDIO_SUFFIXES:
        supported = ", ".join(sorted(_SUPPORTED_AUDIO_SUFFIXES))
        raise ValueError(f"Unsupported audio format '{candidate.suffix}'. Use one of: {supported}")

    return candidate


@ara.tool(
    parameters={
        "type": "object",
        "properties": {
            "audio_path": {
                "type": "string",
                "description": "Local path to an audio file. Defaults to TRANSCRIBE_AUDIO_PATH or demo/sample_audio.wav.",
            },
            "language": {
                "type": "string",
                "description": "Optional ISO-639-1 language code such as 'en'.",
            },
            "model": {
                "type": "string",
                "description": "Speech-to-text model to use.",
                "default": _DEFAULT_MODEL,
            },
        },
    },
    required_env=["OPENAI_API_KEY"],
)
def transcribe(audio_path: str = "", language: str = "en", model: str = _DEFAULT_MODEL) -> dict:
    """Transcribe a local audio file into text with the OpenAI Audio API."""
    try:
        resolved_audio_path = _resolve_audio_path(audio_path)
        client = OpenAI()

        selected_model = model or _DEFAULT_MODEL

        with resolved_audio_path.open("rb") as audio_file:
            if language:
                response = client.audio.transcriptions.create(
                    file=audio_file,
                    model=selected_model,
                    language=language,
                )
            else:
                response = client.audio.transcriptions.create(
                    file=audio_file,
                    model=selected_model,
                )

        text = getattr(response, "text", "").strip()
        if not text:
            raise RuntimeError("The transcription API returned empty text.")

        return {
            "text": text,
            "ok": True,
            "audio_path": str(resolved_audio_path),
            "model": selected_model,
        }
    except Exception as exc:
        message = f"Transcription unavailable: {exc}"
        return {"text": message, "ok": False, "error": str(exc)}
