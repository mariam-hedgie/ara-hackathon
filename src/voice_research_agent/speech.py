from __future__ import annotations

from typing import Protocol


class PromptSource(Protocol):
    def capture(self) -> str: ...


class Speaker(Protocol):
    def speak(self, text: str) -> None: ...


class TerminalPromptSource:
    def capture(self) -> str:
        return input("What would you like to research? ")


class ConsoleSpeaker:
    def speak(self, text: str) -> None:
        print(text)
