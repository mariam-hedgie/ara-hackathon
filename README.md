# Ara Research Copilot

Single-agent example from the [Ara Hackathon Tour 2026](https://github.com/cyu60/ara-ai-computer) — a chat-based research copilot running on the [Ara](https://ara.so) agentic operating system.

**Links:** [Ara docs](https://docs.ara.so/introduction) · [Ara Hackathon Tour](https://github.com/cyu60/ara-ai-computer) · [DayDreamers](https://daydreamers.live)

Part of the **Aragrams** — reference projects built by [DayDreamers](https://daydreamers.live) to show what's possible with agent-first development.

## What it does

Web research, synthesis into markdown briefs, and quizzes to lock in what you've learned. Give the agent a topic or a URL and it:

- Searches the web and reads the relevant pages via browser automation
- Synthesizes findings into a structured markdown brief on the sandbox filesystem
- Builds a running knowledge base across every topic you've asked about
- Hands off to a quiz-master that grills you with 3-5 mixed-format questions per brief and tracks scores over time
- Runs a daily research digest hook every morning at 9 AM UTC, surfacing new findings on topics you're tracking

No tabs, no highlighters, no flashcard app — text the agent like a research partner who remembers everything you've read.

## Architecture

```
Browser (index.html)
   ↓
/api/run (Vercel serverless function)
   ↓
Ara API (api.ara.so) — Bearer ARA_RUNTIME_KEY
   ↓
research-assistant subagent running in a sandboxed Python runtime
   ↕ handoff
quiz-master subagent
```

## Local dev

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install ara-sdk
export ARA_ACCESS_TOKEN=<your_token>

python3 app.py setup                           # registers the app → returns APP_ID
python3 app.py deploy --on-existing update     # pushes the agent definition
python3 app.py run --workflow research-assistant --message "Research the latest on AI agents"
```

## Deploy

This repo is wired to Vercel. On push to `main`:

1. Vercel builds the static frontend + `api/run.js` edge function.
2. The function proxies `/api/run` calls to `https://api.ara.so/v1/apps/<APP_ID>/run` using `ARA_RUNTIME_KEY`.
3. The Ara runtime spins up the `research-assistant` sandbox on demand.

## License

MIT
