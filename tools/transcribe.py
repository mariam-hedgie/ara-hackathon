from pathlib import Path

import ara_sdk as ara


_DEMO_SAMPLE_PATH = Path(__file__).resolve().parent.parent / "demo" / "sample_audio.txt"
_FALLBACK_TEXT = "Hello from the transcription fallback."


@ara.tool
def transcribe() -> dict:
    """Return non-empty transcription text from the demo file or a fallback."""
    text = ""

    try:
        text = _DEMO_SAMPLE_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        text = ""

    if not text:
        text = _FALLBACK_TEXT

    return {"text": text}
