# Voice Research Agent

Voice Research Agent is the earlier Ara-based hackathon prototype: a lightweight Python app, a local browser UI, and a small deterministic fallback researcher for fast demos.

## What it does

- deploys an Ara automation from `app.py`
- serves a local browser UI from `server.py`
- accepts typed prompts, dictation, and file attachments
- renders markdown answers and can read them aloud
- falls back to the local research helper when Ara returns a generic response

## Setup

```bash
cd "/Users/joshuadayal/Documents/Codex/2026-04-19-how-do-i-acess-the-terminal/voice-research-agent"
python3 -m pip install -e .
ara deploy app.py
python3 server.py
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

If you prefer environment-based auth instead of `ara auth login`, copy `.env.example` and add your Ara API key.

## Project layout

- `app.py`: Ara automation entry point
- `server.py`: local web server and Ara bridge
- `web/`: browser UI
- `src/voice_research_agent/`: fallback research logic and CLI

## CLI smoke test

```bash
python3 -m voice_research_agent --text "Research lightweight wake-word detection for edge AI devices."
```
