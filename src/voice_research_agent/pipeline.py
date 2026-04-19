from __future__ import annotations

from voice_research_agent.models import ResearchResponse
from voice_research_agent.research import StarterResearcher
from voice_research_agent.speech import ConsoleSpeaker, Speaker, TerminalPromptSource, PromptSource


class ResearchAgent:
    def __init__(
        self,
        prompt_source: PromptSource | None = None,
        researcher: StarterResearcher | None = None,
        speaker: Speaker | None = None,
    ) -> None:
        self.prompt_source = prompt_source or TerminalPromptSource()
        self.researcher = researcher or StarterResearcher()
        self.speaker = speaker or ConsoleSpeaker()

    def run(self, query: str | None = None) -> ResearchResponse:
        resolved_query = query or self.prompt_source.capture()
        response = self.researcher.run(resolved_query)
        self.speaker.speak(response.to_markdown())
        return response
