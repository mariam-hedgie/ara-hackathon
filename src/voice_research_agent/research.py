from __future__ import annotations

from voice_research_agent.models import ResearchFinding, ResearchResponse


class StarterResearcher:
    """Small deterministic research helper for the hackathon prototype."""

    def run(self, query: str) -> ResearchResponse:
        normalized = query.strip().lower()
        if "wake-word" in normalized or "wake word" in normalized:
            return self._wake_word_response(query)
        if "speech-to-text" in normalized or "speech to text" in normalized or "stt" in normalized:
            return self._speech_to_text_response(query)
        return self._general_response(query)

    def _general_response(self, query: str) -> ResearchResponse:
        findings = [
            ResearchFinding(
                title="Capture spoken intent",
                summary=(
                    "Turn microphone audio into a clean text query and detect a wake phrase "
                    "before running expensive tools."
                ),
                source_hint="product architecture",
            ),
            ResearchFinding(
                title="Separate retrieval from synthesis",
                summary=(
                    "Use one step to gather notes, sources, and snippets, then a second step "
                    "to produce a concise spoken answer."
                ),
                source_hint="agent workflow",
            ),
            ResearchFinding(
                title="Design for quick follow-ups",
                summary=(
                    "Voice interfaces feel better when the user can ask clarifying questions "
                    "without restarting the full session."
                ),
                source_hint="conversation design",
            ),
        ]
        return ResearchResponse(
            query=query,
            answer=(
                f'For "{query}", the strongest MVP is a pipeline that listens for a wake phrase, '
                "transcribes the spoken question, gathers a handful of focused research results, "
                "and responds with a short spoken summary plus suggested follow-up questions."
            ),
            next_steps=[
                "Integrate microphone capture and wake-word detection.",
                "Connect a retrieval source such as web search or paper search.",
                "Add citations to the spoken and displayed answer.",
            ],
            findings=findings,
        )

    def _wake_word_response(self, query: str) -> ResearchResponse:
        findings = [
            ResearchFinding(
                title="Depthwise CNNs are a strong edge baseline",
                summary=(
                    "Compact architectures such as DS-CNN, TC-ResNet, or small CRNN variants "
                    "usually hit the best tradeoff for wake-word detection on microcontrollers "
                    "and low-power SBCs."
                ),
                source_hint="model choice",
            ),
            ResearchFinding(
                title="Streaming audio features matter as much as the model",
                summary=(
                    "Most practical systems use log-mel or MFCC features over short sliding "
                    "windows, which keeps latency low and reduces the amount of raw audio the "
                    "model must process."
                ),
                source_hint="signal pipeline",
            ),
            ResearchFinding(
                title="Quantization and threshold tuning drive deployability",
                summary=(
                    "INT8 quantization, pruning, and careful false-accept versus false-reject "
                    "threshold tuning are usually what make a wake-word model viable on-device."
                ),
                source_hint="deployment optimization",
            ),
        ]
        return ResearchResponse(
            query=query,
            answer=(
                "For lightweight wake-word detection on edge AI devices, the best MVP path is a "
                "small streaming model built around MFCC or log-mel features, deployed with INT8 "
                "quantization, and tuned aggressively for low latency and low false-trigger rates "
                "on your actual target hardware."
            ),
            next_steps=[
                "Prototype with a DS-CNN or TC-ResNet style model in TensorFlow Lite Micro or TensorFlow Lite.",
                "Benchmark latency, RAM use, and false-trigger rate on the exact edge device you want to demo.",
                "Record a small wake-word dataset with noise, distance, and accent variation to tune thresholds realistically.",
            ],
            findings=findings,
        )

    def _speech_to_text_response(self, query: str) -> ResearchResponse:
        findings = [
            ResearchFinding(
                title="Model size determines whether fully on-device is realistic",
                summary=(
                    "Tiny or distillation-based speech models are easier to demo locally, while "
                    "larger models often need a stronger edge box or a hybrid local-plus-cloud fallback."
                ),
                source_hint="deployment constraint",
            ),
            ResearchFinding(
                title="Streaming partial transcripts improve UX",
                summary=(
                    "Even if final accuracy is imperfect, streaming partial text quickly makes the "
                    "product feel much more responsive."
                ),
                source_hint="product UX",
            ),
            ResearchFinding(
                title="Noise handling is a demo-critical differentiator",
                summary=(
                    "Background suppression, microphone choice, and push-to-talk or wake-word "
                    "gating can matter more than small model accuracy gains in hackathon conditions."
                ),
                source_hint="demo reliability",
            ),
        ]
        return ResearchResponse(
            query=query,
            answer=(
                "For on-device speech-to-text in a hackathon MVP, prioritize a model small enough "
                "to run locally with acceptable latency, then shape the UX around fast partial "
                "transcripts and strong noise handling."
            ),
            next_steps=[
                "Choose one local STT path and benchmark real-time latency before adding product polish.",
                "Add a streaming transcript view so users see progress immediately.",
                "Test in noisy rooms with the exact microphone setup you plan to demo.",
            ],
            findings=findings,
        )
