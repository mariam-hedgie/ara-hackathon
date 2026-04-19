from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ResearchFinding:
    title: str
    summary: str
    source_hint: str

    def to_dict(self) -> dict[str, str]:
        return {
            "title": self.title,
            "summary": self.summary,
            "source_hint": self.source_hint,
        }


@dataclass
class ResearchResponse:
    query: str
    answer: str
    next_steps: list[str] = field(default_factory=list)
    findings: list[ResearchFinding] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "query": self.query,
            "answer": self.answer,
            "next_steps": list(self.next_steps),
            "findings": [finding.to_dict() for finding in self.findings],
        }

    def to_markdown(self) -> str:
        sections = [
            "### Short Summary",
            self.answer,
            "",
            "### Key Findings",
        ]
        for index, finding in enumerate(self.findings, start=1):
            sections.append(f"{index}. **{finding.title}**: {finding.summary}")
        sections.extend(["", "### Practical Next Steps"])
        for index, next_step in enumerate(self.next_steps, start=1):
            sections.append(f"{index}. {next_step}")
        return "\n".join(sections)
