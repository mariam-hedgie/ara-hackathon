from ara_sdk import App, cron, run_cli, sandbox, runtime

app = App(
    "Ara Research Copilot",
    project_name="ara-research-copilot",
    description="Web research, synthesis into markdown briefs, and quizzes to lock in what you've learned.",
)


@app.subagent(
    id="research-assistant",
    instructions="""You are a research assistant with browser automation and file access.
When the user gives you a topic:
1. Search the web and read relevant pages.
2. Synthesize findings into a structured markdown brief.
3. Save the brief to the sandbox filesystem for future reference.
4. Track what the user has asked about — build a running knowledge base.
When asked to review or quiz, hand off to the quiz-master with the saved brief.""",
    handoff_to=["quiz-master"],
    sandbox=sandbox(max_concurrency=2),
    runtime=runtime(python_packages=["beautifulsoup4", "requests"]),
)
def research_assistant(event=None):
    """Web research, synthesis, and knowledge management."""


@app.subagent(
    id="quiz-master",
    instructions="""You quiz the user based on their saved research briefs.
Generate 3-5 questions per topic. Mix multiple choice, short answer, and scenario-based.
Track scores over time in a JSON file on the sandbox filesystem.
Be encouraging but honest about gaps.""",
    sandbox=sandbox(),
)
def quiz_master(event=None):
    """Quiz users on their research topics."""


@app.hook(
    id="daily-research-digest",
    event="scheduler.research",
    schedule=cron("0 9 * * *"),
)
def daily_research_digest():
    """Morning digest of new findings on tracked topics."""


@app.local_entrypoint()
def local(input_payload):
    return {"ok": True, "app": "ara-research-copilot", "input": input_payload}


if __name__ == "__main__":
    run_cli(app)
