"""Shared name-anonymization logic, used by every phaseN-*/ and phase6-history/ summarizer.

Every recording uses real-sounding TTS voice names as speaker labels
(e.g. "Sam", "Priya") that must never reach a transcript or summary as-is —
this is the one safety mechanism the project guarantees end-to-end, so it
lives in one place rather than being copy-pasted per scenario.
"""
import re


def person_labels(speaker_names):
    """speaker_names: {"A": "Sam", "B": "Priya"} -> {"Sam": "Person A", "Priya": "Person B"}"""
    return {name: f"Person {key}" for key, name in speaker_names.items()}


def redact_names(text, speaker_names=None, labels=None):
    labels = labels or person_labels(speaker_names)
    for name, label in labels.items():
        text = re.sub(rf"\b{re.escape(name)}\b", label, text, flags=re.IGNORECASE)
    return text
