"""Deterministic reasoning helpers for the Research Brain demo."""

import ara_sdk as ara


@ara.tool
def generate_insight(parsed: dict) -> dict:
    """Generate a concise insight, counterargument, and next step from parsed text."""
    parsed = parsed or {}

    claim = str(parsed.get("claim") or "").strip()
    gap = str(parsed.get("gap") or "").strip()
    evidence = str(parsed.get("evidence") or "").strip()

    if claim and gap:
        insight = f"The main claim is {claim}, but the strongest research opportunity is addressing {gap}."
        counterargument = f"This interpretation is limited because {gap} may weaken confidence in the claim."
        next_step = f"Design a focused validation step that tests whether {gap} changes the strength of the claim."
    elif claim:
        insight = f"The central research signal is the claim that {claim}."
        if evidence:
            counterargument = f"The claim depends on evidence described as {evidence}, which may be incomplete or preliminary."
        else:
            counterargument = "The claim is promising, but the supporting evidence is not yet clearly specified."
        next_step = "Collect one stronger piece of evidence or replication result to stress-test the claim."
    elif gap:
        insight = f"The clearest takeaway is an unresolved gap: {gap}."
        counterargument = "A gap alone does not establish which hypothesis or intervention is most credible."
        next_step = f"Prioritize an experiment or literature check that directly resolves {gap}."
    else:
        insight = "The transcript does not yet contain enough structured research detail for a strong conclusion."
        counterargument = "Without a clear claim or gap, any interpretation risks being too speculative."
        next_step = "Capture a more explicit claim, supporting evidence, and unresolved gap before drawing conclusions."

    return {
        "insight": insight,
        "counterargument": counterargument,
        "next_step": next_step,
    }
